import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env 加载
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, raw_value = line.partition("=")
            key = key.strip()
            value = raw_value.strip()
            # 去除行内注释（不在引号内的 #）
            if value and value[0] in ('"', "'"):
                if value.endswith(value[0]) and len(value) >= 2:
                    value = value[1:-1]
            else:
                idx = value.find("#")
                if idx > 0:
                    value = value[:idx].strip()
            os.environ.setdefault(key, value)

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 1440  # 24 hours

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"mysql+pymysql://{os.environ.get('DB_USER', 'zigaa')}:{os.environ.get('DB_PASSWORD', 'zigaa123')}@"
    f"{os.environ.get('DB_HOST', '127.0.0.1')}:{os.environ.get('DB_PORT', '3306')}/"
    f"{os.environ.get('DB_NAME', 'zigaa_platform')}?charset=utf8mb4",
)

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
UPLOAD_TMP_DIR = os.environ.get("UPLOAD_TMP_DIR", "/data/tmp")
TRAINING_DIR = os.environ.get("TRAINING_DIR", "/data/zigaa")
CLEANUP_STALE_HOURS = int(os.environ.get("CLEANUP_STALE_HOURS", "48"))

CORS_HOST = os.environ.get("CORS_HOST", "")
CORS_PORT = os.environ.get("CORS_PORT", "3111")
_cors_origins = ["http://localhost:" + CORS_PORT, "http://127.0.0.1:" + CORS_PORT]
if CORS_HOST:
    _cors_origins.append("http://" + CORS_HOST + ":" + CORS_PORT)
CORS_ORIGINS = _cors_origins

SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
