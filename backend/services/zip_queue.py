"""ZIP 异步处理队列 — 按 (model_id, resource_type) 串行，状态文件持久化"""
import fcntl
import json
import logging
import os
import queue
import shutil
import threading
import tempfile
import time

from core.config import UPLOAD_TMP_DIR, CLEANUP_STALE_HOURS
from core.database import SessionLocal

logger = logging.getLogger("zigaa")

UPLOAD_STATUS_DIR = os.path.join(UPLOAD_TMP_DIR, "upload-status")
_lock = threading.Lock()
_queues: dict[tuple[str, str], "ProcessingQueue"] = {}


class ProcessingQueue:
    def __init__(self, model_id: str, resource_type: str):
        self.model_id = model_id
        self.resource_type = resource_type
        self.q: queue.Queue = queue.Queue()
        self.thread = threading.Thread(target=self._worker_loop, daemon=True, name=f"zip-{resource_type}")
        self.thread.start()

    def _worker_loop(self):
        while True:
            task = self.q.get()
            try:
                _process_one(task)
            except Exception:
                logger.exception("ZIP 处理工作线程异常 model=%s type=%s", self.model_id, self.resource_type)
            finally:
                self.q.task_done()


def _write_status(upload_id: str, data: dict):
    os.makedirs(UPLOAD_STATUS_DIR, exist_ok=True)
    path = os.path.join(UPLOAD_STATUS_DIR, f"{upload_id}.json")
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def _read_status(upload_id: str) -> dict | None:
    path = os.path.join(UPLOAD_STATUS_DIR, f"{upload_id}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def get_or_create_queue(model_id: str, resource_type) -> ProcessingQueue:
    key = (model_id, resource_type)
    with _lock:
        if key not in _queues:
            _queues[key] = ProcessingQueue(model_id, resource_type)
        return _queues[key]


def enqueue_assemble_and_process(model_id: str, resource_type: str, upload_id: str, filename: str = "", file_size: int = 0):
    """异步拼接分片 → 解压 → 清理分片 → 入队处理（传解压目录），不阻塞 API 响应"""
    def _background_assemble():
        import zipfile
        from services.chunk_upload import assemble_upload, cleanup_upload
        
        st = {
            "upload_id": upload_id,
            "model_id": model_id,
            "resource_type": resource_type,
            "filename": filename,
            "status": "processing",
            "progress": 0,
            "estimated_seconds": max(5, int(file_size / (1024 ** 3) * 6)),
            "result": None,
            "error": None,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        _write_status(upload_id, st)

        zip_path = None
        extract_dir = None
        try:
            zip_path = assemble_upload(upload_id)
            

            # 解压到临时目录
            extract_dir = tempfile.mkdtemp(dir=UPLOAD_TMP_DIR)
            with zipfile.ZipFile(zip_path, "r") as zf:
                for info in zf.infolist():
                    clean_name = info.filename.replace("\\", "/").lstrip("/")
                    target = os.path.realpath(os.path.join(extract_dir, clean_name))
                    if not target.startswith(os.path.realpath(extract_dir)):
                        raise ValueError(f"不安全的路径: {info.filename}")
                zf.extractall(extract_dir)
            elapsed = time.time() - st["created_at"]
            logger.info(f"分片拼接解压完成 resource={resource_type} model={model_id} 拼接解压总耗时={elapsed:.1f}s")

            # 入队处理 — 传解压目录
            pq = get_or_create_queue(model_id, resource_type)
            pq.q.put({
                "model_id": model_id,
                "resource_type": resource_type,
                "upload_id": upload_id,
                "extract_dir": extract_dir,
            })
            extract_dir = None  # 所有权移交，不在此清理
            logger.info(f"后端处理入队 model={model_id} type={resource_type} upload={upload_id}")
        except Exception as e:
            detail = str(e)
            if hasattr(e, "detail"):
                detail = e.detail
            st = _read_status(upload_id)
            if st:
                st["status"] = "failed"
                st["error"] = detail
                st["updated_at"] = time.time()
                _write_status(upload_id, st)
            logger.error(f"分片拼接/解压失败 model={model_id} type={resource_type} upload={upload_id} error={detail}")
        finally:
            # 清理分片 + ZIP
            cleanup_upload(upload_id)
            # 如果解压目录所有权未移交，清理它
            if extract_dir:
                shutil.rmtree(extract_dir, ignore_errors=True)

    t = threading.Thread(target=_background_assemble, daemon=True, name=f"assemble-{resource_type}")
    t.start()


def _process_one(task: dict):
    model_id = task["model_id"]
    resource_type = task["resource_type"]
    upload_id = task["upload_id"]
    is_reprocess = task.get("is_reprocess", False)
    user_id = task.get("user_id")
    extract_dir = task.get("extract_dir")

    from api.resources import _process_extracted_dir, _process_reprocess

    db = SessionLocal()
    try:
        if is_reprocess:
            # 重新入库：验证所有权后直接处理 original/ 目录（不复制）
            result = _process_reprocess(model_id, resource_type, db, user_id)
        else:
            result = _process_extracted_dir(model_id, resource_type, extract_dir, db)

        st = _read_status(upload_id)
        if st:
            st["status"] = "completed"
            st["progress"] = 100
            st["result"] = result
            st["updated_at"] = time.time()
            _write_status(upload_id, st)

        process_elapsed = time.time() - (st["created_at"] if st else time.time())
        total_images = result.get("passed_count", 0) + result.get("failed_count", 0)
        task_type = "重新入库" if is_reprocess else "后端处理"
        logger.info(f"{task_type}完成 resource={resource_type} model={model_id} 处理图片={total_images} 通过={result.get('passed_count', 0)} 失败={result.get('failed_count', 0)} 耗时={process_elapsed:.1f}s")
    except Exception as e:
        detail = str(e)
        if hasattr(e, "detail"):
            detail = e.detail
        st = _read_status(upload_id)
        if st:
            st["status"] = "failed"
            st["error"] = detail
            st["updated_at"] = time.time()
            _write_status(upload_id, st)
        logger.error(f"{task_type}失败 model={model_id} type={resource_type} upload={upload_id} error={detail}", exc_info=True)
        db.rollback()
    finally:
        if not is_reprocess:
            try:
                shutil.rmtree(extract_dir, ignore_errors=True)
            except Exception:
                pass
        db.close()


_reprocess_queues: dict[tuple[str, str], "ProcessingQueue"] = {}
_reprocess_lock = threading.Lock()


def enqueue_reprocess(model_id: str, resource_type: str, user_id: str) -> str:
    """将重新入库任务丢入串行队列，返回 status key。"""
    import uuid

    reprocess_id = f"reprocess-{uuid.uuid4().hex[:8]}"
    st = {
        "upload_id": reprocess_id,
        "model_id": model_id,
        "resource_type": resource_type,
        "filename": "",
        "status": "processing",
        "progress": 0,
        "estimated_seconds": 30,
        "result": None,
        "error": None,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    _write_status(reprocess_id, st)

    key = (model_id, resource_type)
    with _reprocess_lock:
        if key not in _reprocess_queues:
            _reprocess_queues[key] = ProcessingQueue(model_id, resource_type)
        _reprocess_queues[key].q.put({
            "model_id": model_id,
            "resource_type": resource_type,
            "upload_id": reprocess_id,  # reused as status key
            "is_reprocess": True,
            "user_id": user_id,
        })
    logger.info(f"重新入库入队 model={model_id} type={resource_type} id={reprocess_id}")
    return reprocess_id


def _delete_status(upload_id: str):
    """删除上传状态文件"""
    path = os.path.join(UPLOAD_STATUS_DIR, f"{upload_id}.json")
    try:
        os.remove(path)
    except OSError:
        pass


def get_upload_status(upload_id: str) -> dict | None:
    path = os.path.join(UPLOAD_STATUS_DIR, f"{upload_id}.json")
    if not os.path.exists(path):
        return None
    try:
        fd = os.open(path, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_SH)
            data = os.read(fd, 1024 * 1024)
            result = json.loads(data.decode())
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        return result
    except (json.JSONDecodeError, OSError):
        return None


def cleanup_stale_status():
    """清理过期的上传状态文件"""
    if not os.path.exists(UPLOAD_STATUS_DIR):
        return
    now = time.time()
    max_age = CLEANUP_STALE_HOURS * 3600
    removed = 0
    for fname in os.listdir(UPLOAD_STATUS_DIR):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(UPLOAD_STATUS_DIR, fname)
        if os.path.isfile(fpath) and now - os.path.getmtime(fpath) > max_age:
            try:
                os.remove(fpath)
                removed += 1
            except OSError:
                pass
    if removed:
        logger.info(f"清理过期上传状态文件: {removed}")
