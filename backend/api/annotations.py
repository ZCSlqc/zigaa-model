"""单图标注 API

路径前缀: /api/annotations
每张图片一个同名 JSON，存于 original/ 目录。
test 类型且 test_status 为 success 时，JSON 从 upload_path/test/ 读取。
"""
import json
import os
import shutil
from PIL import Image
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import DataPackage
from core.auth import get_current_user, check_model_owner
from services.directory import get_resource_dir
from services.helper import is_supported_image, get_image_size
from services.validator import validate_annotation_json
from services.resource import (
    update_single_image_error,
    update_model_status,
    update_image_msg,
)

router = APIRouter()

# ── 目录常量 ─────────────────────────────────────────────

LAYERS = ("compress", "preview")


# ── 工具函数 ─────────────────────────────────────────────


def _get_test_dir(model_id: str, db: Session) -> str | None:
    """测试类型：返回 upload_path/test/，仅 test_status 为 success"""
    from core.models import ModelInfo
    m = db.query(ModelInfo).filter(ModelInfo.id == model_id).first()
    if m and m.upload_path:
        test_st = m.status.get("test_status", {}) if m.status else {}
        if isinstance(test_st, dict) and test_st.get("status") == "success":
            path = os.path.join(m.upload_path, "test")
            if os.path.isdir(path):
                return path
    return None


def _get_annotation_path(model_id: str, resource_type: str, image_path: str,
                         db: Session | None = None) -> str:
    if resource_type == "test" and db:
        test_dir = _get_test_dir(model_id, db)
        if test_dir:
            return os.path.join(test_dir, os.path.splitext(image_path)[0] + ".json")
    original_dir = os.path.join(get_resource_dir(model_id, resource_type), "original")
    return os.path.join(original_dir, os.path.splitext(image_path)[0] + ".json")


def _delete_file_safe(path: str):
    if os.path.exists(path):
        os.remove(path)


def _sync_rmdir_layers(resource_dir: str, rel_path: str):
    """同步删除 compress/preview 侧的目录（已存在时）。"""
    for layer in LAYERS:
        layer_dir = os.path.join(resource_dir, layer, rel_path)
        if os.path.exists(layer_dir):
            os.rmdir(layer_dir)


def _find_top_empty_dir(dir_path: str, safe_stop: str) -> str | None:
    """从 dir_path 开始向上查找最顶层连续空目录，依次删除。

    dir_path: 已删除的文件/目录路径
    safe_stop: 安全边界，到达此层停止
    返回: safe_stop（全部清空到边界）或最后删除的子目录，或 None
    """
    current = os.path.abspath(dir_path)
    safe_stop = os.path.abspath(safe_stop)
    last_deleted = current

    while True:
        parent = os.path.dirname(current)
        if parent == current:
            return None  # 根目录

        try:
            if os.path.isdir(parent) and os.listdir(parent):
                # 父目录不空，停止
                return None if not os.path.isdir(current) else last_deleted
        except FileNotFoundError:
            pass

        # 父目录为空，删除
        try:
            os.rmdir(parent)
        except FileNotFoundError:
            pass
        last_deleted = parent

        if parent == safe_stop:
            return safe_stop

        current = parent


def _cleanup_and_update_ledger(model_id: str, resource_type: str, resource_dir: str,
                               image_rels: list[str], db: Session) -> dict:
    """物理删除后的台账清理。

    当 resource_dir 为空时删除整个 DataPackage 记录。
    否则精准更新 errors/msg 计数。
    """
    dp = db.query(DataPackage).filter(
        DataPackage.model_id == model_id,
        DataPackage.resource_type == resource_type,
    ).first()
    if not dp:
        return {}

    # resource_dir 空了就删台账
    try:
        if not os.listdir(resource_dir):
            db.delete(dp)
            update_model_status(model_id, db)
            return {}
    except FileNotFoundError:
        db.delete(dp)
        update_model_status(model_id, db)
        return {}

    # 精准更新：从 errors 和 msgs 移除被删的图片
    old_errors = dict(dp.errors or {})
    old_msgs = dict(dp.msgs or {})
    removed_errors = 0

    for rel in image_rels:
        if old_errors.pop(rel, None) is not None:
            removed_errors += 1
    dp.errors = old_errors

    for rel in image_rels:
        old_msgs.pop(rel, None)
    dp.msgs = old_msgs

    removed_passed = len(image_rels) - removed_errors
    dp.passed_count = max(0, dp.passed_count - removed_passed)
    dp.failed_count = max(0, dp.failed_count - removed_errors)
    update_model_status(model_id, db)
    return {"deleted_count": len(image_rels)}


# ── 路由 ─────────────────────────────────────────────


@router.get("/{model_id}/{resource_type}/{image_path:path}/download")
def download_image(model_id: str, resource_type: str, image_path: str,
                   db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """Download image + annotation JSON as base64 blobs in one response."""
    import base64
    from fastapi.responses import Response
    check_model_owner(model_id, user["user_id"], db)
    resource_dir = get_resource_dir(model_id, resource_type)
    orig_path = os.path.join(resource_dir, "original", image_path)
    if not os.path.isfile(orig_path):
        raise HTTPException(status_code=404, detail="File not found")

    with open(orig_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("ascii")

    annotation_b64 = None
    ann_path = _get_annotation_path(model_id, resource_type, image_path, db)
    if os.path.exists(ann_path):
        with open(ann_path, "rb") as f:
            annotation_b64 = base64.b64encode(f.read()).decode("ascii")

    payload = {"image": image_b64, "annotation": annotation_b64}
    return Response(content=json.dumps(payload), media_type="application/json")


@router.get("/{model_id}/{resource_type}/{image_path:path}")
def get_annotation(model_id: str, resource_type: str, image_path: str,
                   db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """获取单图标注，不存在返回空 va[] 模板"""
    check_model_owner(model_id, user["user_id"], db)

    ann_path = _get_annotation_path(model_id, resource_type, image_path, db)
    if os.path.exists(ann_path):
        with open(ann_path, "r", encoding="utf-8") as f:
            return json.load(f)

    img_path = os.path.join(get_resource_dir(model_id, resource_type), "original", image_path)
    width, height = 0, 0
    if os.path.exists(img_path):
        try:
            img = Image.open(img_path)
            width, height = img.size
        except Exception:
            pass

    return {"va": [], "width": width, "height": height, "wl": 0, "ww": 0}


@router.put("/{model_id}/{resource_type}/{image_path:path}")
def save_annotation(model_id: str, resource_type: str, image_path: str, data: dict,
                    db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """保存单图标注"""
    check_model_owner(model_id, user["user_id"], db)

    resource_dir = get_resource_dir(model_id, resource_type)
    ann_path = _get_annotation_path(model_id, resource_type, image_path, db)

    # 静默清理坏点
    va = data.get("va", [])
    if va:
        cleaned = []
        for e in va:
            if not isinstance(e, dict):
                continue
            good_pts = [p for p in e.get("pts", []) if isinstance(p, dict) and "x" in p and "y" in p]
            if len(good_pts) >= 3:
                cleaned.append({**e, "pts": good_pts})
        data["va"] = cleaned

    if not data.get("va"):
        _delete_file_safe(ann_path)
    else:
        orig_path = os.path.join(resource_dir, "original", image_path)
        actual_w, actual_h = (0, 0)
        if os.path.exists(orig_path):
            actual_w, actual_h = get_image_size(orig_path)

        result = validate_annotation_json(json.dumps(data), actual_w, actual_h)
        if not result["valid"]:
            raise HTTPException(status_code=400, detail=result["error"])

        os.makedirs(os.path.dirname(ann_path), exist_ok=True)
        with open(ann_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    update_single_image_error(model_id, resource_type, image_path, db, "save")
    db.commit()
    return {"success": True}


@router.delete("/{model_id}/{resource_type}/folder/{folder_path:path}")
def delete_folder(model_id: str, resource_type: str, folder_path: str,
                  db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """删除文件夹及其下所有内容，同步清理台账"""
    check_model_owner(model_id, user["user_id"], db)

    resource_dir = get_resource_dir(model_id, resource_type)
    orig_base = os.path.join(resource_dir, "original")

    orig_folder = os.path.join(orig_base, folder_path)
    if not os.path.isdir(orig_folder):
        raise HTTPException(status_code=404, detail="文件夹不存在")

    image_rels = []
    for root, _dirs, files in os.walk(orig_folder):
        for fname in files:
            if is_supported_image(fname):
                image_rels.append(os.path.relpath(os.path.join(root, fname), orig_base))

    shutil.rmtree(orig_folder)

    for layer in LAYERS:
        layer_folder = os.path.join(resource_dir, layer, folder_path)
        if os.path.isdir(layer_folder):
            shutil.rmtree(layer_folder)

    top_dir = _find_top_empty_dir(orig_folder, orig_base)
    if top_dir is not None:
        rel = os.path.relpath(top_dir, orig_base)
        _sync_rmdir_layers(resource_dir, rel)

    result = _cleanup_and_update_ledger(model_id, resource_type, resource_dir, image_rels, db)
    db.commit()
    result["success"] = True
    return result


@router.delete("/{model_id}/{resource_type}/{image_path:path}")
def delete_image(model_id: str, resource_type: str, image_path: str,
                 db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """删除图片：原图 + compress/preview 图 + 标注 JSON"""
    check_model_owner(model_id, user["user_id"], db)

    resource_dir = get_resource_dir(model_id, resource_type)
    orig_base = os.path.join(resource_dir, "original")
    orig_path = os.path.join(orig_base, image_path)

    # 删除 original 侧（图片 + 标注 JSON）
    _delete_file_safe(orig_path)
    _delete_file_safe(os.path.splitext(orig_path)[0] + ".json")

    # compress / preview 同步删除
    base = os.path.splitext(image_path)[0] + ".jpg"
    for layer in LAYERS:
        _delete_file_safe(os.path.join(resource_dir, layer, base))

    # 查找并删除 original 侧连续空目录
    top_dir = _find_top_empty_dir(orig_path, orig_base)
    if top_dir is not None:
        rel = os.path.relpath(top_dir, orig_base)
        _sync_rmdir_layers(resource_dir, rel)

    # 台账清理
    _cleanup_and_update_ledger(model_id, resource_type, resource_dir, [image_path], db)
    db.commit()
    return {"success": True}



@router.patch("/{model_id}/{resource_type}/msg/{image_path:path}")
def update_image_msg_api(model_id: str, resource_type: str, image_path: str, data: dict,
                         db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """更新单张图片的 msgs 元信息（category 等）"""
    check_model_owner(model_id, user["user_id"], db)

    valid_keys = {"category"}
    update_data = {k: v for k, v in data.items() if k in valid_keys}
    if not update_data:
        raise HTTPException(status_code=400, detail="无效的字段")

    update_image_msg(model_id, resource_type, image_path, update_data, db)
    db.commit()
    dp = db.query(DataPackage).filter(
        DataPackage.model_id == model_id,
        DataPackage.resource_type == resource_type,
    ).first()
    return {"success": True, "msgs": dict(dp.msgs) if dp else {}}
