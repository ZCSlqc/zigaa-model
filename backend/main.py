from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from core.database import init_db, SessionLocal
from core.models import User
from core.auth import hash_password
from core.config import UPLOAD_DIR, UPLOAD_TMP_DIR, CORS_ORIGINS
import datetime
import os
import threading
import time
import logging
from services.chunk_upload import cleanup_stale_uploads
from services.chunk_download import cleanup_stale_downloads
from services.zip_queue import cleanup_stale_status

# Logger — output to stdout (redirected to /log/backend.log by start.sh)
logger = logging.getLogger("zigaa")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)

# 初始化目录
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(UPLOAD_TMP_DIR, exist_ok=True)

# 启动时清理过期缓存
cleanup_stale_uploads()
cleanup_stale_downloads()
cleanup_stale_status()

# 初始化数据库
init_db()


def seed_users():
    """注入种子用户"""
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.username == "zigaa").first():
            db.add(User(username="zigaa", password_hash=hash_password("zigaa123"), role="admin"))
        if not db.query(User).filter(User.username == "zigaatest").first():
            db.add(User(username="zigaatest", password_hash=hash_password("zigaa123"), role="user"))
        db.commit()
    finally:
        db.close()


seed_users()


def _daily_cleanup_worker():
    """每天凌晨清理过期缓存：分片上传 + 下载会话 + ZIP 状态"""
    while True:
        now = datetime.datetime.now()
        midnight = datetime.datetime(now.year, now.month, now.day) + datetime.timedelta(days=1)
        seconds_until = (midnight - now).total_seconds()
        time.sleep(seconds_until)
        try:
            cleanup_stale_uploads()
            cleanup_stale_downloads()
            cleanup_stale_status()
            logger.info("每日缓存清理完成")
        except Exception:
            logger.exception("每日缓存清理异常")


t = threading.Thread(target=_daily_cleanup_worker, daemon=True, name="daily-cleanup")
t.start()
logger.info("每日定时清理已启动")

app = FastAPI(title="ZIGAA 大模型云平台")


class RequestTimeMiddleware:
    """ASGI middleware — 在请求刚到达（body 未读取）时记录时间戳"""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            scope["start_time"] = time.time()
        await self.app(scope, receive, send)


app.add_middleware(RequestTimeMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False if CORS_ORIGINS == ["*"] else True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from api import auth, projects, models as models_api, resources, annotations, admin

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(models_api.router, prefix="/api/models", tags=["models"])
app.include_router(resources.router, prefix="/api/resources", tags=["resources"])
app.include_router(annotations.router, prefix="/api/annotations", tags=["annotations"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

# 挂载 uploads 静态文件，路径前缀 /uploads
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/")
def root():
    return {"message": "ZIGAA Backend API", "docs": "/docs"}
