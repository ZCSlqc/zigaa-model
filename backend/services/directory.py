"""目录工具 — 路径获取、目录遍历、建树"""
import os
from core.config import UPLOAD_DIR
from services.helper import is_supported_image


def get_model_dir(model_id: str) -> str:
    return os.path.join(UPLOAD_DIR, model_id)


def get_resource_dir(model_id: str, resource_type: str) -> str:
    return os.path.join(get_model_dir(model_id), resource_type)


def get_resource_url(model_id: str, resource_type: str) -> str:
    return f"/uploads/{model_id}/{resource_type}"


def build_resource_tree(model_id: str, resource_type: str) -> dict:
    """构建资源目录树，只遍历 original/"""
    original_dir = os.path.join(get_resource_dir(model_id, resource_type), "original")
    if not os.path.exists(original_dir):
        return {"name": resource_type, "children": []}

    res_base = get_resource_url(model_id, resource_type)

    def _walk(dir_path: str) -> list:
        result = []
        try:
            entries = sorted(os.scandir(dir_path), key=lambda e: e.name)
        except OSError:
            return result
        for entry in entries:
            rel = os.path.relpath(entry.path, original_dir)
            if entry.is_dir():
                result.append({
                    "name": entry.name,
                    "path": f"{res_base}/original/{rel}",
                    "children": _walk(entry.path),
                })
            else:
                rel_noext = os.path.splitext(rel)[0]
                info = {
                    "name": entry.name,
                    "size": entry.stat().st_size,
                    "path": f"{res_base}/original/{rel}",
                }
                if is_supported_image(entry.name):
                    info["compress_path"] = f"{res_base}/compress/{rel_noext}.jpg"
                    info["preview_path"] = f"{res_base}/preview/{rel_noext}.jpg"
                result.append(info)
        return result

    return {"name": resource_type, "children": [{"name": "original", "children": _walk(original_dir)}]}
