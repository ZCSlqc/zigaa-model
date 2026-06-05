"""分片上传管理 — 大文件切片存储、拼接、清理"""
import fcntl
import json
import logging
import os
import shutil
import time
from core.config import UPLOAD_TMP_DIR, CLEANUP_STALE_HOURS

logger = logging.getLogger("zigaa")

CHUNK_UPLOADS_DIR = os.path.join(UPLOAD_TMP_DIR, "upload-chunks")


def _chunk_dir(upload_id: str) -> str:
    return os.path.join(CHUNK_UPLOADS_DIR, upload_id)


def _meta_path(upload_id: str) -> str:
    return os.path.join(CHUNK_UPLOADS_DIR, f"{upload_id}.json")


def _chunk_file_path(upload_id: str, index: int) -> str:
    return os.path.join(_chunk_dir(upload_id), str(index))


def _write_meta_lock(meta_path: str, meta: dict):
    """原子写入 meta JSON（文件锁防并发覆盖）"""
    tmp_path = meta_path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(meta, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, meta_path)


def _read_meta_lock(meta_path: str) -> dict:
    """带文件锁读取 meta JSON"""
    with open(meta_path, "r") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            meta = json.load(f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return meta


def init_upload(upload_id: str, filename: str, total_size: int, total_chunks: int, chunk_size: int, owner_id: str) -> dict:
    """初始化分片会话，返回元数据（含已存在分片列表）"""
    chunk_path = _chunk_dir(upload_id)
    meta_path = _meta_path(upload_id)

    if os.path.exists(meta_path):
        meta = _read_meta_lock(meta_path)
        if meta["filename"] == filename and meta["total_size"] == total_size:
            meta["uploaded_chunks"] = meta.get("uploaded_chunks", [])
            # 验证缓存列表准确性（恢复场景检查缺失文件）
            if meta.get("uploading"):
                raise ValueError("上传进行中，请勿重复初始化")
            return meta

    shutil.rmtree(chunk_path, ignore_errors=True)
    os.makedirs(chunk_path, exist_ok=True)

    meta = {
        "upload_id": upload_id,
        "filename": filename,
        "total_size": total_size,
        "total_chunks": total_chunks,
        "chunk_size": chunk_size,
        "created_at": time.time(),
        "owner_id": owner_id,
        "uploaded_chunks": [],
        "uploading": False,
    }
    _write_meta_lock(meta_path, meta)
    return meta


def save_chunk(upload_id: str, chunk_index: int, data: bytes) -> bool:
    """幂等保存分片，新写返回 True，已存在且大小一致返回 False"""
    path = _chunk_file_path(upload_id, chunk_index)
    already = os.path.exists(path) and os.path.getsize(path) == len(data)
    if already:
        return False
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)
    _update_uploaded_chunks(upload_id, chunk_index)
    return True


def _update_uploaded_chunks(upload_id: str, new_index: int):
    """带文件锁更新 uploaded_chunks 列表"""
    meta_path = _meta_path(upload_id)
    if not os.path.exists(meta_path):
        return
    with open(meta_path, "r+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            meta = json.load(f)
            chunks = meta.get("uploaded_chunks", [])
            if new_index not in chunks:
                chunks.append(new_index)
                meta["uploaded_chunks"] = chunks
            f.seek(0)
            f.truncate()
            json.dump(meta, f)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def get_upload_status(upload_id: str) -> dict | None:
    """返回分片上传状态，不存在返回 None。使用缓存的 uploaded_chunks 列表，不再扫描文件系统。"""
    meta_path = _meta_path(upload_id)
    if not os.path.exists(meta_path):
        return None
    return _read_meta_lock(meta_path)


def set_uploading(upload_id: str, uploading: bool) -> dict:
    """设置 uploading 标记，返回 meta。用于 upload-complete 互斥。"""
    meta_path = _meta_path(upload_id)
    if not os.path.exists(meta_path):
        raise ValueError("上传会话不存在")
    with open(meta_path, "r+") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            meta = json.load(f)
            if uploading and meta.get("uploading"):
                raise ValueError("上传处理进行中，请勿重复提交")
            meta["uploading"] = uploading
            f.seek(0)
            f.truncate()
            json.dump(meta, f)
            return meta
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def assemble_upload(upload_id: str) -> str:
    """按序拼接分片为 assembled.zip，返回路径。缺片或大小不符抛 ValueError"""
    meta = get_upload_status(upload_id)
    if meta is None:
        raise ValueError("上传会话不存在")

    for i in range(meta["total_chunks"]):
        if i not in meta.get("uploaded_chunks", []):
            raise ValueError(f"分片 {i} 缺失")

    output = os.path.join(_chunk_dir(upload_id), "assembled.zip")
    total = 0
    with open(output, "wb") as out:
        for i in range(meta["total_chunks"]):
            path = _chunk_file_path(upload_id, i)
            total += os.path.getsize(path)
            with open(path, "rb") as f:
                shutil.copyfileobj(f, out, length=16 * 1024 * 1024)

    if total != meta["total_size"]:
        os.remove(output)
        raise ValueError(f"文件大小不匹配: 期望 {meta['total_size']}，实际 {total}")

    return output


def cleanup_upload(upload_id: str):
    """删除分片目录和元数据"""
    shutil.rmtree(_chunk_dir(upload_id), ignore_errors=True)
    meta = _meta_path(upload_id)
    if os.path.exists(meta):
        os.remove(meta)


def cleanup_user_uploads(owner_id: str) -> int:
    """删除指定用户所有未完成的分片会话，返回清理数量"""
    if not os.path.exists(CHUNK_UPLOADS_DIR):
        return 0
    count = 0
    for name in os.listdir(CHUNK_UPLOADS_DIR):
        if not name.endswith(".json"):
            continue
        meta_path = os.path.join(CHUNK_UPLOADS_DIR, name)
        try:
            meta = _read_meta_lock(meta_path)
            if meta.get("owner_id") == owner_id and not meta.get("uploading"):
                upload_id = meta.get("upload_id", name.replace(".json", ""))
                cleanup_upload(upload_id)
                count += 1
        except (json.JSONDecodeError, OSError):
            # 损坏的 meta 也删掉
            upload_id = name.replace(".json", "")
            cleanup_upload(upload_id)
            count += 1
    return count


def cleanup_stale_uploads():
    """清理过期的分片上传：以 meta 文件为入口，清理超时上传 + 孤儿目录"""
    if not os.path.exists(CHUNK_UPLOADS_DIR):
        return
    now = time.time()
    max_age = CLEANUP_STALE_HOURS * 3600
    cleaned = 0

    # 以 meta 文件为入口，清理超时的上传
    valid_ids = set()
    for name in os.listdir(CHUNK_UPLOADS_DIR):
        if not name.endswith(".json"):
            continue
        meta_path = os.path.join(CHUNK_UPLOADS_DIR, name)
        try:
            if now - os.path.getmtime(meta_path) > max_age:
                upload_id = name[:-5]
                cleanup_upload(upload_id)
                cleaned += 1
            else:
                valid_ids.add(name[:-5])
        except OSError:
            pass

    # 清理孤儿分片目录（无对应 meta）
    for name in os.listdir(CHUNK_UPLOADS_DIR):
        if name.endswith(".json"):
            continue
        if os.path.isdir(os.path.join(CHUNK_UPLOADS_DIR, name)) and name not in valid_ids:
            try:
                shutil.rmtree(os.path.join(CHUNK_UPLOADS_DIR, name), ignore_errors=True)
                cleaned += 1
            except OSError:
                pass

    if cleaned:
        logger.info(f"清理过期分片上传: {cleaned}")
