"""三资源 API — 上传 / 下载 / 删除 / 编辑 / 状态 / 分片上传

路径前缀: /api/resources
"""
import json
import logging
import os
import shutil
import tempfile
import time
import zipfile
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import DataPackage
from core.auth import get_current_user, check_model_owner
from services.directory import get_model_dir, get_resource_dir, build_resource_tree
from services.helper import is_supported_image, process_images_parallel
from services.resource import (
    update_model_status,
    clear_resource,
    clear_parameter,
    validate_new_annotations,
)
from services.chunk_upload import (
    get_upload_status,
    init_upload,
    save_chunk,
    set_uploading,
)
from services.chunk_download import (
    create_download_session,
    get_chunk as get_download_chunk,
    delete_session,
    CHUNK_SIZE as DOWNLOAD_CHUNK_SIZE,
)
from services.zip_queue import enqueue_assemble_and_process, get_upload_status as get_zip_upload_status, _delete_status
from core.config import UPLOAD_DIR, UPLOAD_TMP_DIR

logger = logging.getLogger("zigaa")

router = APIRouter()


# ── 辅助函数 ─────────────────────────────────────────────


def _process_extracted_dir(model_id: str, resource_type: str, extract_dir: str, db: Session):
    """从已解压的目录处理：追加复制 + 图片处理 + DB 写入"""
    logger.info(f"ZIP后端处理开始 resource={resource_type} model={model_id}")
    t0 = time.time()

    original_dir = os.path.join(
        get_resource_dir(model_id, resource_type), "original"
    )
    os.makedirs(original_dir, exist_ok=True)
    extracted_items = os.listdir(extract_dir)
    if len(extracted_items) == 1 and os.path.isdir(os.path.join(extract_dir, extracted_items[0])):
        src_root = os.path.join(extract_dir, extracted_items[0])
    else:
        src_root = extract_dir

    # 每次上传创建一个时间戳子目录，天然隔离，无需重命名
    ts = time.strftime("%Y%m%d_%H%M%S")
    dst_root = os.path.join(original_dir, ts)
    shutil.copytree(src_root, dst_root, dirs_exist_ok=True)

    # 收集所有新图片相对路径
    new_image_rels = []
    for root, _dirs, files in os.walk(dst_root, followlinks=False):
        for fname in files:
            if is_supported_image(fname):
                rel = os.path.relpath(os.path.join(root, fname), original_dir)
                new_image_rels.append(rel)

    # 对新图片生成 compress/preview（并行）
    new_image_list = [(rel, None) for rel in new_image_rels]
    new_errors = process_images_parallel(model_id, resource_type, original_dir, new_image_list)

    # JSON 校验（仅 defect）
    if resource_type in ("defect"):
        new_errors.extend(
            validate_new_annotations(original_dir, new_image_rels)
        )

    new_passed = max(0, len(new_image_rels) - len(new_errors))

    # upsert 台账
    dp = db.query(DataPackage).filter(
        DataPackage.model_id == model_id,
        DataPackage.resource_type == resource_type,
    ).first()
    if dp:
        dp.passed_count += new_passed
        dp.failed_count += len(new_errors)
        existing_errors = list(dp.errors or [])
        existing_errors.extend(new_errors)
        dp.errors = existing_errors
    else:
        db.add(DataPackage(
            model_id=model_id,
            resource_type=resource_type,
            file_path=f"uploads/{model_id}/{resource_type}/",
            passed_count=new_passed,
            failed_count=len(new_errors),
            errors=new_errors,
        ))
    update_model_status(model_id, db)
    db.commit()

    return {"success": True, "passed_count": new_passed, "failed_count": len(new_errors), "errors": new_errors}


def _validate_resource_type(resource_type: str):
    if resource_type not in ("good", "defect", "test", "template"):
        raise HTTPException(status_code=400, detail="无效的资源类型")


def _check_disk_space() -> float:
    """返回磁盘剩余空间（GB），不再抛异常——前端按阈值分级提示"""
    try:
        disk_free = shutil.disk_usage(UPLOAD_DIR).free
    except OSError:
        disk_free = 0
    return disk_free / 1024 / 1024 / 1024


def _get_resource_src_dir(model_id: str, resource_type: str) -> str:
    original_dir = os.path.join(get_resource_dir(model_id, resource_type), "original")
    if not os.path.exists(original_dir):
        raise HTTPException(status_code=404, detail="资源不存在")
    return original_dir


def _create_zip_from_dir(src_dir: str) -> str:
    tmp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False, dir=UPLOAD_TMP_DIR)
    tmp_zip.close()
    with zipfile.ZipFile(tmp_zip.name, "w", zipfile.ZIP_STORED) as zf:
        for root, _dirs, files in os.walk(src_dir, followlinks=False):
            for fname in files:
                fpath = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, src_dir)
                zf.write(fpath, arcname)
    return tmp_zip.name


def _delete_resource(model_id: str, resource_type: str, db: Session, user_id: str):
    check_model_owner(model_id, user_id, db)
    clear_resource(model_id, resource_type)
    dp = db.query(DataPackage).filter(
        DataPackage.model_id == model_id,
        DataPackage.resource_type == resource_type,
    ).first()
    if dp:
        db.delete(dp)
    update_model_status(model_id, db)
    db.commit()
    return {"success": True}




# ── 目录树 ─────────────────────────────────────────────


@router.get("/tree")
def get_tree(
    model_id: str,
    resource_type: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_model_owner(model_id, user["user_id"], db)
    tree = build_resource_tree(model_id, resource_type)
    return {"tree": tree}


# ── 分片上传 ─────────────────────────────────────────────


@router.post("/{model_id}/{resource_type}/upload-init")
def chunk_upload_init(
    model_id: str,
    resource_type: str,
    data: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _validate_resource_type(resource_type)
    check_model_owner(model_id, user["user_id"], db)

    if not data.get("filename", "").lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="只支持 ZIP 文件")

    free_gb = _check_disk_space()
    if free_gb < 4:
        raise HTTPException(status_code=507, detail="磁盘空间不足（剩余 {:.1f}GB）".format(free_gb))

    meta = init_upload(
        upload_id=data["upload_id"],
        filename=data["filename"],
        total_size=data["total_size"],
        total_chunks=data["total_chunks"],
        chunk_size=data["chunk_size"],
        owner_id=user["user_id"],
    )
    logger.info(f"分片初始化 resource={resource_type} model={model_id} chunks={meta['total_chunks']} size={data['total_size'] / 1024 / 1024:.1f}MB")
    return {
        "upload_id": meta["upload_id"],
        "total_chunks": meta["total_chunks"],
        "uploaded_chunks": meta.get("uploaded_chunks", []),
    }


@router.post("/{model_id}/{resource_type}/upload-chunk")
def chunk_upload(
    model_id: str,
    resource_type: str,
    upload_id: str = Query(...),
    chunk_index: int = Query(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    _validate_resource_type(resource_type)

    # 从 meta 缓存校验 owner，避免每个分片都查 DB
    meta = get_upload_status(upload_id)
    if meta is None or meta.get("owner_id") != user["user_id"]:
        raise HTTPException(status_code=404, detail="上传会话不存在或无权限")

    chunk_data = file.file.read()
    is_new = save_chunk(upload_id, chunk_index, chunk_data)

    uploaded = len(meta.get("uploaded_chunks", []))
    total = meta["total_chunks"]
    logger.info(f"分片接收 resource={resource_type} model={model_id} chunk={chunk_index}/{total} new={is_new}")

    return {
        "upload_id": upload_id,
        "chunk_index": chunk_index,
        "new": is_new,
        "uploaded": uploaded,
        "total": total,
        "progress": round(uploaded / total * 100, 1),
    }


@router.post("/{model_id}/{resource_type}/upload-complete")
def chunk_upload_complete(
    model_id: str,
    resource_type: str,
    upload_id: str = Query(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _validate_resource_type(resource_type)
    check_model_owner(model_id, user["user_id"], db)

    free_gb = _check_disk_space()
    if free_gb < 4:
        raise HTTPException(status_code=507, detail="磁盘空间不足（剩余 {:.1f}GB）".format(free_gb))

    upload_status = get_upload_status(upload_id)
    upload_start = upload_status.get("created_at", time.time()) if upload_status else time.time()
    filename = upload_status.get("filename", "") if upload_status else ""
    file_size = upload_status.get("total_size", 0) if upload_status else 0

    # 互斥：防止并发/重入导致重复处理
    try:
        set_uploading(upload_id, True)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    transfer_elapsed = time.time() - upload_start
    logger.info(f"分片传输完成 resource={resource_type} model={model_id} 传输总耗时={transfer_elapsed:.1f}s")

    # 异步拼接 + 处理：立即返回，后台 worker 负责 assemble → 解压 → 清理
    enqueue_assemble_and_process(model_id, resource_type, upload_id, filename, file_size)
    return {"success": True, "upload_id": upload_id, "status": "processing"}


@router.get("/{model_id}/{resource_type}/upload-status/{upload_id}")
def get_upload_status_endpoint(
    model_id: str,
    resource_type: str,
    upload_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _validate_resource_type(resource_type)
    check_model_owner(model_id, user["user_id"], db)
    status = get_zip_upload_status(upload_id)
    if status is None:
        raise HTTPException(status_code=404, detail="上传任务不存在")
    if status.get("model_id") != model_id or status.get("resource_type") != resource_type:
        raise HTTPException(status_code=404, detail="上传任务不存在")
    if status.get("status") in ("completed", "failed"):
        _delete_status(upload_id)
    return status


# ── 磁盘空间检查 ─────────────────────────────────────────


@router.get("/{model_id}/{resource_type}/disk-check")
def disk_check(model_id: str, resource_type: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    _validate_resource_type(resource_type)
    check_model_owner(model_id, user["user_id"], db)
    free_gb = _check_disk_space()
    return {"free_gb": round(free_gb, 1)}


# ── 模型参数 ─────────────────────────────────────────────


@router.post("/{model_id}/parameter/upload")
def upload_parameter(model_id: str, file: UploadFile = File(...), db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    check_model_owner(model_id, user["user_id"], db)

    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="只支持 JSON 文件")

    content = file.file.read().decode("utf-8")
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON 格式错误: {e}")

    param_path = os.path.join(get_model_dir(model_id), "parameter.json")
    os.makedirs(os.path.dirname(param_path), exist_ok=True)
    with open(param_path, "w", encoding="utf-8") as f:
        f.write(content)

    existing = db.query(DataPackage).filter(
        DataPackage.model_id == model_id,
        DataPackage.resource_type == "parameter",
    ).first()
    if existing:
        db.delete(existing)
        db.commit()

    db.add(DataPackage(
        model_id=model_id,
        resource_type="parameter",
        file_path=f"uploads/{model_id}/parameter.json",
        passed_count=0,
        failed_count=0,
        errors=[],
    ))
    update_model_status(model_id, db)
    db.commit()
    return {"success": True}


@router.put("/{model_id}/parameter")
def edit_parameter(model_id: str, data: dict, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    check_model_owner(model_id, user["user_id"], db)

    param_path = os.path.join(get_model_dir(model_id), "parameter.json")
    os.makedirs(os.path.dirname(param_path), exist_ok=True)
    with open(param_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    existing = db.query(DataPackage).filter(
        DataPackage.model_id == model_id,
        DataPackage.resource_type == "parameter",
    ).first()
    if not existing:
        db.add(DataPackage(
            model_id=model_id,
            resource_type="parameter",
            file_path=f"uploads/{model_id}/parameter.json",
            passed_count=0,
            failed_count=0,
            errors=[],
        ))

    update_model_status(model_id, db)
    db.commit()
    return {"success": True}


@router.get("/{model_id}/parameter")
def get_parameter(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """获取模型参数内容（返回 JSON body）"""
    check_model_owner(model_id, user["user_id"], db)

    param_path = os.path.join(get_model_dir(model_id), "parameter.json")
    if not os.path.exists(param_path):
        raise HTTPException(status_code=404, detail="模型参数不存在")

    with open(param_path, "r", encoding="utf-8") as f:
        return {"data": json.load(f)}


@router.delete("/{model_id}/parameter/file")
def delete_parameter_file(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """删除模型参数文件"""
    check_model_owner(model_id, user["user_id"], db)

    param_path = os.path.join(get_model_dir(model_id), "parameter.json")
    if os.path.exists(param_path):
        os.remove(param_path)

    dp = db.query(DataPackage).filter(
        DataPackage.model_id == model_id,
        DataPackage.resource_type == "parameter",
    ).first()
    if dp:
        db.delete(dp)
    update_model_status(model_id, db)
    db.commit()
    return {"success": True}


@router.get("/{model_id}/parameter/download")
def download_parameter(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    check_model_owner(model_id, user["user_id"], db)

    param_path = os.path.join(get_model_dir(model_id), "parameter.json")
    if not os.path.exists(param_path):
        raise HTTPException(status_code=404, detail="模型参数不存在")

    from fastapi.responses import FileResponse
    return FileResponse(
        param_path,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="parameter.json"'},
    )


# ── 资源删除 ─────────────────────────────────────────────


@router.delete("/{model_id}/good")
def delete_good(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return _delete_resource(model_id, "good", db, user["user_id"])


@router.delete("/{model_id}/defect")
def delete_defect(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return _delete_resource(model_id, "defect", db, user["user_id"])


@router.delete("/{model_id}/test")
def delete_test(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    m = check_model_owner(model_id, user["user_id"], db)
    if m.status:
        test_st = m.status.get("test_status", {})
        if isinstance(test_st, dict) and test_st.get("status") == "generating":
            raise HTTPException(status_code=400, detail="测试生成中，不可删除")
    return _delete_resource(model_id, "test", db, user["user_id"])


@router.delete("/{model_id}/template")
def delete_template(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    return _delete_resource(model_id, "template", db, user["user_id"])


@router.delete("/{model_id}/parameter")
def delete_parameter(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    check_model_owner(model_id, user["user_id"], db)
    clear_parameter(model_id)
    dp = db.query(DataPackage).filter(
        DataPackage.model_id == model_id,
        DataPackage.resource_type == "parameter",
    ).first()
    if dp:
        db.delete(dp)
    update_model_status(model_id, db)
    db.commit()
    return {"success": True}


# ── 资源下载 ─────────────────────────────────────────────


@router.post("/{model_id}/{resource_type}/download-init")
def resource_download_init(model_id: str, resource_type: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """初始化分片下载：创建临时 ZIP，返回会话信息"""
    check_model_owner(model_id, user["user_id"], db)
    src_dir = _get_resource_src_dir(model_id, resource_type)
    t0 = time.time()
    zip_path = _create_zip_from_dir(src_dir)
    try:
        file_size = os.path.getsize(zip_path)
        session = create_download_session(zip_path, f"{resource_type}.zip", file_size, user["user_id"])
    except Exception:
        os.unlink(zip_path)
        raise
    elapsed = time.time() - t0
    logger.info(f"分片下载 ZIP 打包完成 resource={resource_type} model={model_id} 耗时={elapsed:.1f}s size={file_size}")
    return {
        "session_id": session["session_id"],
        "filename": session["filename"],
        "size": file_size,
        "total_chunks": session["total_chunks"],
        "chunk_size": DOWNLOAD_CHUNK_SIZE,
    }


@router.get("/{model_id}/{resource_type}/download-chunk")
def resource_download_chunk(model_id: str, resource_type: str, session_id: str, chunk_index: int,
                            db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """获取分片下载的一个 chunk"""
    check_model_owner(model_id, user["user_id"], db)
    data, file_size = get_download_chunk(session_id, chunk_index)
    from fastapi.responses import Response
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Length": str(len(data)),
            "Content-Range": f"bytes {chunk_index * DOWNLOAD_CHUNK_SIZE}-{min((chunk_index + 1) * DOWNLOAD_CHUNK_SIZE, file_size) - 1}/{file_size}",
        },
    )


@router.post("/{model_id}/{resource_type}/download-cleanup")
def resource_download_cleanup(model_id: str, resource_type: str, session_id: str,
                              db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """清理分片下载会话"""
    check_model_owner(model_id, user["user_id"], db)
    delete_session(session_id)
    return {"success": True}
