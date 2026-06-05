"""分片下载管理 — 下载会话、临时 ZIP 管理、chunk 读取"""
import json
import os
import threading
import time
import uuid
from core.config import UPLOAD_TMP_DIR, CLEANUP_STALE_HOURS

CHUNK_DOWNLOADS_DIR = os.path.join(UPLOAD_TMP_DIR, "download-sessions")
CHUNK_SIZE = 8 * 1024 * 1024  # 8MB

# 线程级锁：flock 在同一进程内多线程不互斥，用 threading.Lock 保护
_meta_lock = threading.Lock()


def _meta_path(session_id: str) -> str:
    return os.path.join(CHUNK_DOWNLOADS_DIR, f"{session_id}.json")


def _atomic_write(path: str, data: dict):
    """原子写入 JSON（写临时文件 + rename）"""
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def create_download_session(zip_path: str, filename: str, file_size: int, owner_id: str) -> dict:
    """创建下载会话，ZIP 文件已存在，返回会话 metadata"""
    os.makedirs(CHUNK_DOWNLOADS_DIR, exist_ok=True)
    session_id = uuid.uuid4().hex
    meta = {
        "session_id": session_id,
        "zip_path": zip_path,
        "filename": filename,
        "file_size": file_size,
        "chunk_size": CHUNK_SIZE,
        "total_chunks": (file_size + CHUNK_SIZE - 1) // CHUNK_SIZE,
        "owner_id": owner_id,
        "created_at": time.time(),
        "last_accessed": time.time(),
    }
    _atomic_write(_meta_path(session_id), meta)
    return meta


def _read_meta(session_id: str) -> dict:
    meta_path = _meta_path(session_id)
    if not os.path.exists(meta_path):
        raise ValueError("下载会话不存在")
    with _meta_lock:
        with open(meta_path, "r") as f:
            content = f.read()
        if not content.strip():
            raise ValueError("下载会话元数据损坏")
        meta = json.loads(content)
        meta["last_accessed"] = time.time()
        _atomic_write(meta_path, meta)
    return meta


def get_chunk(session_id: str, chunk_index: int) -> tuple:
    """读取指定 chunk，返回 (bytes, file_size)"""
    meta = _read_meta(session_id)
    zip_path = meta["zip_path"]
    offset = chunk_index * meta["chunk_size"]
    if offset >= meta["file_size"]:
        raise ValueError("chunk 索引超出范围")

    try:
        with open(zip_path, "rb") as f:
            f.seek(offset)
            data = f.read(meta["chunk_size"])
    except FileNotFoundError:
        raise ValueError("临时文件不存在")
    return (data, meta["file_size"])


def delete_session(session_id: str):
    """删除会话和临时 ZIP"""
    meta_path = _meta_path(session_id)
    with _meta_lock:
        if not os.path.exists(meta_path):
            return
        zip_path = ""
        try:
            with open(meta_path, "r") as f:
                meta = json.load(f)
            zip_path = meta.get("zip_path", "")
        except (json.JSONDecodeError, OSError):
            pass
        try:
            os.unlink(meta_path)
        except OSError:
            pass
    if zip_path and os.path.exists(zip_path):
        try:
            os.unlink(zip_path)
        except OSError:
            pass


def cleanup_stale_downloads(max_age_seconds: int = int(CLEANUP_STALE_HOURS * 3600)):
    """清理过期的下载会话"""
    if not os.path.exists(CHUNK_DOWNLOADS_DIR):
        return
    now = time.time()
    to_delete = []
    with _meta_lock:
        for name in os.listdir(CHUNK_DOWNLOADS_DIR):
            if not name.endswith(".json"):
                continue
            meta_path = os.path.join(CHUNK_DOWNLOADS_DIR, name)
            try:
                with open(meta_path, "r") as f:
                    content = f.read()
                if not content.strip():
                    to_delete.append(meta_path)
                    continue
                meta = json.loads(content)
                if now - meta.get("last_accessed", 0) > max_age_seconds:
                    session_id = meta.get("session_id", name.replace(".json", ""))
                    to_delete.append((meta_path, meta.get("zip_path", "")))
            except (json.JSONDecodeError, OSError):
                to_delete.append(meta_path)
            # 删除操作在锁外
        for item in to_delete:
            if isinstance(item, tuple):
                meta_path, zip_path = item
            else:
                meta_path = item
                zip_path = ""
            try:
                os.unlink(meta_path)
            except OSError:
                pass
            if zip_path and os.path.exists(zip_path):
                try:
                    os.unlink(zip_path)
                except OSError:
                    pass
