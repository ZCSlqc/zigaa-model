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
from services.resource import update_single_image_error, update_model_status

router = APIRouter()


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


def _get_annotation_path(model_id: str, resource_type: str, image_path: str, db: Session | None = None) -> str:
    if resource_type == "test" and db:
        test_dir = _get_test_dir(model_id, db)
        if test_dir:
            return os.path.join(test_dir, os.path.splitext(image_path)[0] + ".json")
    original_dir = os.path.join(
        get_resource_dir(model_id, resource_type), "original"
    )
    return os.path.join(original_dir, os.path.splitext(image_path)[0] + ".json")


def _delete_file_safe(path: str):
    if os.path.exists(path):
        os.remove(path)


def _cleanup_empty_dirs(dir_path: str, safe_stop: str):
    """从 dir_path 向上递归删除空目录，到 safe_stop 停止"""
    safe_stop = os.path.abspath(safe_stop)
    current = os.path.abspath(dir_path)
    while current.startswith(safe_stop) and current != safe_stop:
        try:
            if not os.listdir(current):
                os.rmdir(current)
                current = os.path.dirname(current)
            else:
                break
        except OSError:
            break


def _cleanup_layers(resource_dir: str, rel_path: str):
    """original/compress/preview 三层同步向上清理空目录，safe_stop 到 resource_dir"""
    for layer in ("original", "compress", "preview"):
        layer_dir = os.path.join(resource_dir, layer)
        parent = os.path.join(layer_dir, os.path.dirname(rel_path))
        if os.path.exists(parent):
            _cleanup_empty_dirs(parent, resource_dir)


def _cleanup_and_update_ledger(model_id: str, resource_type: str, resource_dir: str,
                               image_rels: list[str], db: Session) -> dict:
    """物理删除后的台账清理。image_rels 为空表示整目录已空。"""
    dp = db.query(DataPackage).filter(
        DataPackage.model_id == model_id,
        DataPackage.resource_type == resource_type,
    ).first()
    if not dp:
        return {}

    # 资源目录空了就删台账
    try:
        if not os.listdir(resource_dir):
            db.delete(dp)
            update_model_status(model_id, db)
            return {}
    except FileNotFoundError:
        db.delete(dp)
        update_model_status(model_id, db)
        return {}

    # 精准更新：从 errors 移除被删的图片
    old_errors = list(dp.errors or [])
    image_bases = {os.path.splitext(r)[0] for r in image_rels}
    new_errors = [e for e in old_errors
                  if os.path.splitext(e.get("path", ""))[0] not in image_bases]
    removed_errors = len(old_errors) - len(new_errors)
    removed_passed = len(image_rels) - removed_errors
    dp.errors = new_errors
    dp.passed_count = max(0, dp.passed_count - removed_passed)
    dp.failed_count = max(0, dp.failed_count - removed_errors)
    update_model_status(model_id, db)
    return {"deleted_count": len(image_rels)}


@router.get("/{model_id}/{resource_type}/{image_path:path}")
def get_annotation(model_id: str, resource_type: str, image_path: str,
                   db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """获取单图标注，不存在返回空 va[] 模板"""
    check_model_owner(model_id, user["user_id"], db)

    ann_path = _get_annotation_path(model_id, resource_type, image_path, db)
    if os.path.exists(ann_path):
        with open(ann_path, "r", encoding="utf-8") as f:
            return json.load(f)

    img_path = os.path.join(
        get_resource_dir(model_id, resource_type), "original", image_path
    )
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
    original_dir = os.path.join(resource_dir, "original")

    orig_folder = os.path.join(original_dir, folder_path)
    if not os.path.isdir(orig_folder):
        raise HTTPException(status_code=404, detail="文件夹不存在")

    # 收集文件夹下所有图片相对路径
    image_rels = []
    for root, _dirs, files in os.walk(orig_folder):
        for fname in files:
            if is_supported_image(fname):
                rel = os.path.relpath(os.path.join(root, fname), original_dir)
                image_rels.append(rel)

    # 物理删除：original
    shutil.rmtree(orig_folder)

    # compress / preview 对应路径同步删除
    for layer in ("compress", "preview"):
        layer_folder = os.path.join(resource_dir, layer, folder_path)
        if os.path.isdir(layer_folder):
            shutil.rmtree(layer_folder)

    # 三层向上清理空目录
    _cleanup_layers(resource_dir, folder_path)

    # 清理台账
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
    orig_path = os.path.join(resource_dir, "original", image_path)

    # 删除 original 侧
    _delete_file_safe(orig_path)
    _delete_file_safe(os.path.splitext(orig_path)[0] + ".json")

    # compress / preview 同步删除
    base = os.path.splitext(image_path)[0] + ".jpg"
    for layer in ("compress", "preview"):
        _delete_file_safe(os.path.join(resource_dir, layer, base))

    # 三层向上清理空目录
    _cleanup_layers(resource_dir, image_path)

    # 清理台账
    _cleanup_and_update_ledger(model_id, resource_type, resource_dir, [image_path], db)
    db.commit()
    return {"success": True}
