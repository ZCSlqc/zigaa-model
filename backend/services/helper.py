"""通用工具函数 — 用户名校验、目录名 sanitization、图片格式/处理、辅助工具"""
import os
import re
import cv2
import numpy as np
from core.config import UPLOAD_DIR, SUPPORTED_IMAGE_EXTS


VALID_ROLES = ("user", "advanced", "admin")


# ── 用户名/目录名 ─────────────────────────────────────


def sanitize_dir_name(name: str) -> str:
    """将字符串 sanitize 为安全的文件夹名"""
    name = name.replace("..", "")
    return re.sub(r'[/:*?"<>|\n\r\\]', '_', name)


# 只允许字母、数字、下划线、中文（含扩展区）
_USERNAME_RE = re.compile(r'^[\w一-鿿㐀-䶿\U00020000-\U0002a6df\U0002a700-\U0002b73f\U0002b740-\U0002b81f\U0002b820-\U0002ceaf豈-﫿\U0002f800-\U0002fa1f]+$')


def validate_username(username: str) -> str:
    """严格校验用户名。返回清理后的用户名，失败抛 ValueError。

    规则:
    - 1-32 字符
    - 只允许字母、数字、下划线、中文
    - 不能纯空白
    """
    if not username or not username.strip():
        raise ValueError("用户名不能为空")
    username = username.strip()
    if len(username) < 1 or len(username) > 32:
        raise ValueError("用户名长度 1-32 字符")
    if not _USERNAME_RE.match(username):
        raise ValueError("用户名只能包含字母、数字、下划线和中文字符")
    return username


# ── 图片工具 ──────────────────────────────────────────


def is_supported_image(filename: str) -> bool:
    ext = os.path.splitext(filename)[1].lower()
    return ext in SUPPORTED_IMAGE_EXTS


def get_image_size(image_path: str) -> tuple:
    """读取图片实际宽高，返回 (width, height)，失败返回 (0, 0)"""
    try:
        img = cv2.imread(image_path)
        if img is None:
            return 0, 0
        return img.shape[1], img.shape[0]
    except Exception:
        return 0, 0


def _process_image_worker(args: tuple) -> tuple[str, str | None, dict | None]:
    """Worker function — uses OpenCV for faster image processing.

    Returns: (rel_path, error_message | None, msg_entry | None)
    msg_entry contains {width, height, channels} for the image.
    """
    model_id, resource_type, rel_path, orig_path = args
    out_name = os.path.splitext(rel_path)[0] + ".jpg"
    resource_dir = os.path.join(UPLOAD_DIR, model_id, resource_type)

    try:
        raw = cv2.imread(orig_path, cv2.IMREAD_UNCHANGED)
        if raw is None:
            return (rel_path, "failed to decode image", None)

        # Get original dimensions and channels before any resize
        h, w = raw.shape[:2]
        channels = raw.shape[2] if len(raw.shape) == 3 else 1

        msg_entry = {"width": w, "height": h, "channels": channels}

        # Convert to 3-channel RGB for compress/preview.
        # OpenCV's cvtColor assumes BGR which is wrong for TIFF files
        # (TIFF stores RGB, not BGR). Use PIL for colour-correct conversion
        # for all 3/4 channel images, and GRAY2RGB for single channel.
        if channels == 1:
            img = cv2.cvtColor(raw, cv2.COLOR_GRAY2RGB)
        else:
            from PIL import Image as PILImage

            try:
                pil = PILImage.open(orig_path).convert("RGB")
                img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
            except Exception:
                return (rel_path, "failed to decode image with PIL", None)

        # preview: original size q95 JPEG
        preview_path = os.path.join(resource_dir, "preview", out_name)
        os.makedirs(os.path.dirname(preview_path), exist_ok=True)
        cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 95])[1].tofile(preview_path)

        # compress: 400px q60 JPEG
        if max(w, h) > 400:
            scale = 400 / max(w, h)
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

        compress_path = os.path.join(resource_dir, "compress", out_name)
        os.makedirs(os.path.dirname(compress_path), exist_ok=True)
        cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 60])[1].tofile(compress_path)

        return (rel_path, None, msg_entry)
    except Exception as e:
        return (rel_path, str(e), None)


def process_images_parallel(model_id: str, resource_type: str, original_dir: str, image_list: list[tuple[str, str]]) -> tuple[list[dict], dict]:
    """多线程并行处理图片（OpenCV 释放 GIL），返回 (errors_dict, msgs_dict)。

    errors_dict: {path: {type, message}} 处理出错的图片
    msgs_dict: {path: {width, height, channels}} 成功处理的图片元信息
    """
    if not image_list:
        return [], {}

    from concurrent.futures import ThreadPoolExecutor

    args = [(model_id, resource_type, rel, os.path.join(original_dir, rel)) for rel, _ in image_list]
    max_workers = min(4, os.cpu_count() or 4)
    errors = {}
    msgs = {}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for rel_path, err, msg_entry in pool.map(_process_image_worker, args):
            if err:
                errors[rel_path] = {"type": "process_error", "message": err}
            elif msg_entry:
                msgs[rel_path] = msg_entry

    return errors, msgs
