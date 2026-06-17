import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 自动加载 .env 文件
load_dotenv(os.path.join(BASE_DIR, ".env"))

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 1440  # 24 hours

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"mysql+pymysql://{os.environ.get('DB_USER', 'zigaa')}:{os.environ.get('DB_PASSWORD', 'zigaa123')}@"
    f"{os.environ.get('DB_HOST', '127.0.0.1')}:{os.environ.get('DB_PORT', '3306')}/"
    f"{os.environ.get('DB_NAME', 'zigaa_platform')}?charset=utf8mb4",
)

_UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "")
if _UPLOAD_DIR and os.path.isabs(_UPLOAD_DIR):
    UPLOAD_DIR = os.path.join(_UPLOAD_DIR, "uploads")
else:
    UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
_UPLOAD_TMP_DIR = os.environ.get("UPLOAD_TMP_DIR", "")
if _UPLOAD_TMP_DIR and os.path.isabs(_UPLOAD_TMP_DIR):
    UPLOAD_TMP_DIR = os.path.join(_UPLOAD_TMP_DIR, "tmp")
else:
    UPLOAD_TMP_DIR = os.path.join(BASE_DIR, "tmp")
TRAINING_DIR = os.environ.get("TRAINING_DIR", os.path.join(BASE_DIR, "training"))
CLEANUP_STALE_HOURS = int(os.environ.get("CLEANUP_STALE_HOURS", "48"))

CORS_HOST = os.environ.get("CORS_HOST", "")
CORS_PORT = os.environ.get("CORS_PORT", "3111")
_cors_origins = ["http://localhost:" + CORS_PORT, "http://127.0.0.1:" + CORS_PORT]
if CORS_HOST:
    _cors_origins.append("http://" + CORS_HOST + ":" + CORS_PORT)
CORS_ORIGINS = _cors_origins

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
