"""资源管理 — 标注校验 + 台账管理 + 文件系统清理 + 模型状态"""
import os
import shutil
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from core.models import ModelInfo, DataPackage
from services.directory import get_model_dir, get_resource_dir
from services.helper import get_image_size


def _get_pkg(model_id: str, resource_type: str, db: Session) -> DataPackage | None:
    return db.query(DataPackage).filter(
        DataPackage.model_id == model_id,
        DataPackage.resource_type == resource_type,
    ).first()


# ── 标注校验 ─────────────────────────────────────────


def validate_new_annotations(original_dir: str, new_image_rels: list[str]) -> dict:
    """校验新增图片的标注 JSON，返回 errors dict {path: {type, level, message}}"""
    from services.validator import validate_annotation_json

    errors = {}
    for rel in new_image_rels:
        img_path = os.path.join(original_dir, rel)
        json_path = os.path.splitext(img_path)[0] + ".json"
        if not os.path.exists(json_path):
            errors[rel] = {
                "type": "missing_json",
                "level": 1,
                "message": f"图片 {os.path.basename(rel)} 缺少同名标注 JSON",
            }
            continue
        # AI修改千万不要删除，临时取消校验标注 JSON
        # try:
        #     with open(json_path, "r", encoding="utf-8") as fh:
        #         text = fh.read()
        #     json_rel = os.path.relpath(json_path, original_dir)
        #     aw, ah = get_image_size(img_path)
        #     result = validate_annotation_json(text, aw, ah)
        #     if not result["valid"]:
        #         errors[json_rel] = {
        #             "type": "invalid_json",
        #             "level": result["level"],
        #             "message": f"标注 JSON 格式错误: {result['error']}",
        #         }
        # except Exception as e:
        #     json_rel = os.path.relpath(json_path, original_dir)
        #     errors[json_rel] = {
        #         "type": "invalid_json",
        #         "level": 2,
        #         "message": f"标注 JSON 读取失败: {e}",
        #     }
    return errors


# ── 台账管理 ─────────────────────────────────────────


def update_image_msg(model_id: str, resource_type: str, image_path: str, msg_data: dict, db: Session) -> None:
    """更新单张图片的 msgs 记录（添加/修改元信息）"""
    dp = _get_pkg(model_id, resource_type, db)
    if not dp:
        return
    dp.msgs = dict(dp.msgs or {})
    dp.msgs[image_path] = {**(dp.msgs.get(image_path) or {}), **msg_data}
    dp.uploaded_at = datetime.now(timezone.utc).isoformat()


def update_single_image_error(model_id: str, resource_type: str, image_path: str, db: Session, action: str) -> None:
    """单图变动后精准更新台账（errors 和 msgs 均为 dict，key=path）。

    action: 'save' 保存标注 | 'delete' 删除图片
    """
    dp = _get_pkg(model_id, resource_type, db)
    if not dp:
        return

    img_base = os.path.splitext(image_path)[0]
    old_errors = dict(dp.errors or {})

    old_errors.pop(image_path, None)
    old_errors.pop(f"{img_base}.json", None)  # legacy alias from old migration
    dp.errors = old_errors

    removed = 1 if image_path in old_errors or f"{img_base}.json" in old_errors else 0

    if action == "save" and removed:
        dp.passed_count += 1
    elif action == "delete" and not removed:
        dp.passed_count = max(0, dp.passed_count - 1)

    dp.failed_count = len(dp.errors)
    dp.uploaded_at = datetime.now(timezone.utc).isoformat()

    update_model_status(model_id, db)


def _ensure_status_dict(s: any) -> dict:
    """Ensure a status dict has all three keys. Works on raw dicts or model instances."""
    if isinstance(s, dict):
        d = dict(s)
    elif isinstance(s, str):
        d = {"file_status": {"status": s}}
    else:
        d = {}
    # Legacy: {"status": "ready"} → {"file_status": {"status": "ready"}}
    if "status" in d and "file_status" not in d:
        d["file_status"] = {"status": d["status"]}
    d.setdefault("file_status", {"status": "idle"})
    d.setdefault("training_status", {"status": "idle"})
    d.setdefault("test_status", {"status": "idle"})
    return d


def _ensure_status(model) -> dict:
    """Ensure model.status is a dict with all three keys."""
    return _ensure_status_dict(model.status)


def get_file_status(model) -> str:
    """Get file (data) status from model.status.file_status.status."""
    s = _ensure_status(model)
    if isinstance(s.get("file_status"), dict):
        return s["file_status"].get("status", "idle")
    return "idle"


def set_file_status(model, status: str, **extra) -> None:
    """Set file_status inside model.status."""
    s = _ensure_status(model)
    s["file_status"] = {"status": status, **extra}
    model.status = s


def get_training_status(model) -> str:
    """Get training status from model.status.training_status.status."""
    s = _ensure_status(model)
    if isinstance(s.get("training_status"), dict):
        return s["training_status"].get("status", "idle")
    return "idle"


def get_test_status(model) -> str:
    """Get test status from model.status.test_status.status."""
    s = _ensure_status(model)
    if isinstance(s.get("test_status"), dict):
        return s["test_status"].get("status", "idle")
    return "idle"


def set_training_status(model, status: str, **extra) -> None:
    """Set training_status inside model.status."""
    s = _ensure_status(model)
    s["training_status"] = {"status": status, **extra}
    model.status = s


def set_test_status(model, status: str, **extra) -> None:
    """Set test_status inside model.status."""
    s = _ensure_status(model)
    s["test_status"] = {"status": status, **extra}
    model.status = s


def update_model_status(model_id: str, db: Session) -> None:
    """根据 DataPackage 台账更新数据状态 (idle/ready/invalid)。"""
    db.flush()
    model = db.query(ModelInfo).filter(ModelInfo.id == model_id).first()
    if not model:
        return

    packages = {
        pkg.resource_type: pkg
        for pkg in db.query(DataPackage).filter(DataPackage.model_id == model_id).all()
    }

    if not packages:
        set_file_status(model, "idle")
        return

    param_ok = "parameter" in packages
    good_ok = packages.get("good") is not None and packages["good"].failed_count == 0
    defect_ok = packages.get("defect") is not None and packages["defect"].failed_count == 0

    set_file_status(model, "ready" if (param_ok and good_ok and defect_ok) else "invalid")


# ── 文件系统清理 ─────────────────────────────────────────


def clear_resource(model_id: str, resource_type: str) -> bool:
    resource_dir = get_resource_dir(model_id, resource_type)
    if os.path.exists(resource_dir):
        shutil.rmtree(resource_dir)
        return True
    return False


def clear_parameter(model_id: str) -> bool:
    param_path = os.path.join(get_model_dir(model_id), "parameter.json")
    if os.path.exists(param_path):
        os.remove(param_path)
        return True
    return False


def clear_model(model_id: str) -> bool:
    model_dir = get_model_dir(model_id)
    if os.path.exists(model_dir):
        shutil.rmtree(model_dir)
        return True
    return False


def clear_project(model_ids: list[str]) -> None:
    for mid in model_ids:
        clear_model(mid)
