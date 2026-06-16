"""模型 API — CRUD / 训练 / 下载 / 状态轮询

路径前缀: /api/models
"""
import datetime
import json
import logging
import os
import shutil
import time
import zipfile
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import ModelInfo, DataPackage
from core.auth import get_current_user, check_model_owner
from core.config import UPLOAD_TMP_DIR, TRAINING_DIR
from services.directory import get_model_dir, get_resource_dir
from services.resource import (
    get_file_status as _file_st,
    set_file_status as _set_file_status,
    get_training_status as _training_st,
    get_test_status as _test_st,
    set_training_status as _set_training_status,
    set_test_status as _set_test_status,
    _ensure_status_dict as _norm_status,
    clear_model,
)
from services.chunk_download import (
    create_download_session,
    get_chunk as get_download_chunk,
    delete_session,
    CHUNK_SIZE as DOWNLOAD_CHUNK_SIZE,
)
from services.helper import sanitize_dir_name

logger = logging.getLogger("zigaa")

router = APIRouter()


# ── 请求/响应模型 ─────────────────────────────────────────


class CreateModelRequest(BaseModel):
    name: str
    description: str = ""


class UpdateModelRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class ModelOut(BaseModel):
    id: str
    name: str
    description: str
    project_id: str
    status: dict | None
    upload_path: str | None
    created_at: str

    class Config:
        from_attributes = True


# ── 辅助函数 ─────────────────────────────────────────────


def _build_resource_paths(dest_dir: str, include_test: bool = True) -> dict:
    """扫描传输目录，构建资源路径字典"""
    paths = {}
    resources = ("good", "defect", "test", "template") if include_test else ("good", "defect", "template")
    for subdir in resources:
        sub = os.path.join(dest_dir, subdir)
        if os.path.isdir(sub):
            paths[subdir] = f"{dest_dir}/{subdir}"
    if os.path.isfile(os.path.join(dest_dir, "parameter.json")):
        paths["parameter"] = f"{dest_dir}/parameter.json"
    paths["model"] = f"{dest_dir}/model"
    paths["log_training"] = f"{dest_dir}/log/training"
    if include_test:
        paths["log_test"] = f"{dest_dir}/log/test"
    return paths


def _read_product_type(model_id: str) -> str:
    """从 parameter.json 读取 product_type，失败返回 common"""
    param_path = os.path.join(get_model_dir(model_id), "parameter.json")
    if os.path.isfile(param_path):
        try:
            with open(param_path, "r", encoding="utf-8") as f:
                return json.load(f).get("product_type", "common") or "common"
        except (json.JSONDecodeError, KeyError):
            pass
    return "common"


def _transfer_model_data(model_id: str, user: dict) -> str:
    """执行数据传输，返回 dest_dir。"""
    t0 = time.time()

    model_dir = get_model_dir(model_id)
    if not os.path.isdir(model_dir):
        raise HTTPException(status_code=400, detail="模型目录不存在")

    product_type = _read_product_type(model_id)
    username = sanitize_dir_name(user.get("username", "unknown"))
    dest_dir = os.path.join(TRAINING_DIR, product_type, username, model_id)

    logger.info(f"本地传输开始 model={model_id} dest={dest_dir}")

    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir)

    try:
        for resource_type in ("good", "defect", "template"):
            original_dir = os.path.join(get_resource_dir(model_id, resource_type), "original")
            if not os.path.isdir(original_dir):
                continue
            dst = os.path.join(dest_dir, resource_type)
            if os.path.exists(dst):
                shutil.rmtree(dst)
            shutil.copytree(original_dir, dst)

        param_path = os.path.join(model_dir, "parameter.json")
        if os.path.isfile(param_path):
            shutil.copy2(param_path, os.path.join(dest_dir, "parameter.json"))
        os.makedirs(os.path.join(dest_dir, "model"), exist_ok=True)
        os.makedirs(os.path.join(dest_dir, "log", "training"), exist_ok=True)
    except Exception as e:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"复制失败: {e}")

    elapsed = time.time() - t0
    logger.info(f"本地传输完成 model={model_id} 耗时={elapsed:.1f}s")
    return dest_dir


def _create_model_zip(model_dir: str) -> str:
    import tempfile
    tmp_zip = tempfile.NamedTemporaryFile(suffix=".zip", delete=False, dir=UPLOAD_TMP_DIR)
    tmp_zip.close()
    with zipfile.ZipFile(tmp_zip.name, "w", zipfile.ZIP_STORED) as zf:
        for root, _dirs, files in os.walk(model_dir, followlinks=False):
            for fname in files:
                fpath = os.path.join(root, fname)
                arcname = os.path.relpath(fpath, model_dir)
                zf.write(fpath, arcname)
    return tmp_zip.name


# ── 模型 CRUD ────────────────────────────────────────────


@router.get("/")
def list_models(project_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    from core.models import Project
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p or p.owner_id != user["user_id"]:
        raise HTTPException(status_code=404, detail="项目不存在或无权限")

    models = (
        db.query(ModelInfo)
        .filter(ModelInfo.project_id == project_id)
        .order_by(ModelInfo.created_at.desc())
        .all()
    )

    # Single query for all package counts instead of N+1
    model_ids = [m.id for m in models]
    counts_map = {}
    if model_ids:
        from sqlalchemy import func
        rows = (
            db.query(DataPackage.model_id, func.count(DataPackage.id))
            .filter(DataPackage.model_id.in_(model_ids))
            .group_by(DataPackage.model_id)
            .all()
        )
        counts_map = {mid: cnt for mid, cnt in rows}

    result = []
    for m in models:
        d = ModelOut.model_validate(m).model_dump()
        d["status"] = _norm_status(m.status)
        d["package_count"] = counts_map.get(m.id, 0)
        result.append(d)
    return result


@router.post("/")
def create_model(req: CreateModelRequest, project_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    from core.models import Project
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p or p.owner_id != user["user_id"]:
        raise HTTPException(status_code=404, detail="项目不存在或无权限")
    if not req.name.strip():
        raise HTTPException(status_code=400, detail="模型名称不能为空")
    m = ModelInfo(
        name=req.name.strip(),
        description=req.description.strip(),
        project_id=project_id,
        status={"file_status": {"status": "idle"}, "training_status": {"status": "idle"}, "test_status": {"status": "idle"}},
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return ModelOut.model_validate(m)


@router.get("/{model_id}")
def get_model(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    m = check_model_owner(model_id, user["user_id"], db)
    packages = db.query(DataPackage).filter(DataPackage.model_id == model_id).all()
    d = ModelOut.model_validate(m).model_dump()
    d["status"] = _norm_status(m.status)
    d["packages"] = [
        {
            "id": pkg.id,
            "resource_type": pkg.resource_type,
            "passed_count": pkg.passed_count,
            "failed_count": pkg.failed_count,
            "errors": pkg.errors or {},
            "msgs": pkg.msgs or {},
            "uploaded_at": pkg.uploaded_at,
        }
        for pkg in packages
    ]
    return d


@router.put("/{model_id}")
def update_model(model_id: str, req: UpdateModelRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    m = check_model_owner(model_id, user["user_id"], db)
    if req.name is not None:
        m.name = req.name.strip()
    if req.description is not None:
        m.description = req.description.strip()
    db.commit()
    return {"message": "更新成功"}


@router.delete("/{model_id}")
def delete_model(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    m = check_model_owner(model_id, user["user_id"], db)
    clear_model(model_id)
    db.delete(m)
    db.commit()
    return {"message": "删除成功"}


# ── 训练 ─────────────────────────────────────────────


@router.post("/{model_id}/train")
def train_model(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """触发训练：清理旧传输 → 新传输 → 写注册索引 + status.json"""
    m = check_model_owner(model_id, user["user_id"], db)

    if user["role"] == "user":
        raise HTTPException(status_code=403, detail="普通用户无权训练模型")

    if _file_st(m) != "ready":
        raise HTTPException(status_code=400, detail="数据不完整或有错误，请先完善数据")

    if _training_st(m) == "training":
        raise HTTPException(status_code=400, detail="模型正在训练中")

    # 清理旧的传输目录
    old_path = m.upload_path
    if old_path and os.path.isdir(old_path):
        shutil.rmtree(old_path, ignore_errors=True)
        m.upload_path = None

    # 执行传输
    dest_dir = _transfer_model_data(model_id, user)
    m.upload_path = dest_dir

    # 写 status.json
    status_path = os.path.join(dest_dir, "status.json")
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump({"training_status": {"status": "training"}, "test_status": {"status": "idle"}}, f, ensure_ascii=False, indent=2)

    # 写训练日志占位
    training_log_dir = os.path.join(dest_dir, "log", "training")
    os.makedirs(training_log_dir, exist_ok=True)
    log_path = os.path.join(training_log_dir, "training.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 模型开始训练，请等待\n")

    # 写注册索引
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    training_index_dir = os.path.normpath(os.path.join(dest_dir, "..", "..", "training"))
    os.makedirs(training_index_dir, exist_ok=True)
    username = sanitize_dir_name(user.get("username", "unknown"))
    index_file = os.path.join(training_index_dir, f"{timestamp}_{username}_{model_id}.json")
    index_data = {
        "status": f"{dest_dir}/status.json",
        "detail": f"{username}_{m.project_id}_{sanitize_dir_name(m.name)}",
        **_build_resource_paths(dest_dir, include_test=False),
    }
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    _set_training_status(m, "training")
    _set_test_status(m, "idle")
    db.commit()

    logger.info(f"训练触发 model={model_id} index={index_file}")
    return {"success": True, "index_file": index_file}


@router.post("/{model_id}/stop-training")
def stop_training(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """终止训练"""
    m = check_model_owner(model_id, user["user_id"], db)

    if _training_st(m) != "training":
        raise HTTPException(status_code=400, detail="只有 training 状态的模型才能终止")

    dest_dir = m.upload_path
    if not dest_dir:
        raise HTTPException(status_code=400, detail="未找到传输目录")
    status_path = os.path.join(dest_dir, "status.json")
    if os.path.isfile(status_path):
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                current = json.load(f)
            current["training_status"] = {"status": "failure", "error": "manual stop"}
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    _set_training_status(m, "failure", error="manual stop")
    db.commit()
    return {"success": True, "message": "训练已终止"}


# ── 测试生成 ─────────────────────────────────────────────


@router.post("/{model_id}/run-test")
def run_test(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """触发测试生成：删除旧 test 目录 → 从最新上传复制 → 写注册索引"""
    m = check_model_owner(model_id, user["user_id"], db)

    if user["role"] == "user":
        raise HTTPException(status_code=403, detail="普通用户无权执行测试")

    if _training_st(m) != "success":
        raise HTTPException(status_code=400, detail="模型未训练成功，无法生成测试")

    dest_dir = m.upload_path
    if not dest_dir or not os.path.isdir(dest_dir):
        raise HTTPException(status_code=400, detail="未找到传输目录，请先训练模型")

    test_status = _test_st(m)
    if test_status == "generating":
        raise HTTPException(status_code=400, detail="测试生成进行中")

    # 检查台账是否有 test 数据
    dp = db.query(DataPackage).filter(
        DataPackage.model_id == model_id,
        DataPackage.resource_type == "test",
    ).first()
    if not dp:
        raise HTTPException(status_code=400, detail="未上传测试数据")

    # 删除旧 test 和 log/test
    test_dir = os.path.join(dest_dir, "test")
    test_log_dir = os.path.join(dest_dir, "log", "test")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir, ignore_errors=True)
    if os.path.exists(test_log_dir):
        shutil.rmtree(test_log_dir, ignore_errors=True)

    # 从最新上传复制 test
    original_dir = os.path.join(get_resource_dir(model_id, "test"), "original")
    if not os.path.isdir(original_dir):
        raise HTTPException(status_code=400, detail="测试数据目录不存在")
    shutil.copytree(original_dir, test_dir)
    os.makedirs(test_log_dir, exist_ok=True)
    log_path = os.path.join(test_log_dir, "test.log")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 测试开始生成，请等待\n")

    # 更新 status.json
    status_path = os.path.join(dest_dir, "status.json")
    if os.path.isfile(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            current = json.load(f)
    else:
        current = {}
    current["test_status"] = {"status": "generating"}
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    # 写注册索引
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    test_index_dir = os.path.normpath(os.path.join(dest_dir, "..", "..", "test"))
    os.makedirs(test_index_dir, exist_ok=True)
    username = sanitize_dir_name(user.get("username", "unknown"))
    index_file = os.path.join(test_index_dir, f"{timestamp}_{username}_{model_id}.json")
    index_data = {
        "status": f"{dest_dir}/status.json",
        "detail": f"{username}_{m.project_id}_{sanitize_dir_name(m.name)}",
        **_build_resource_paths(dest_dir, include_test=True),
    }
    with open(index_file, "w", encoding="utf-8") as f:
        json.dump(index_data, f, ensure_ascii=False, indent=2)

    _set_test_status(m, "generating")
    db.commit()

    logger.info(f"测试生成触发 model={model_id} index={index_file}")
    return {"success": True, "index_file": index_file}


@router.post("/{model_id}/stop-test")
def stop_test(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """终止测试生成"""
    m = check_model_owner(model_id, user["user_id"], db)

    if _test_st(m) != "generating":
        raise HTTPException(status_code=400, detail="只有 generating 状态的测试才能终止")

    dest_dir = m.upload_path
    if not dest_dir:
        raise HTTPException(status_code=400, detail="未找到传输目录")
    status_path = os.path.join(dest_dir, "status.json")
    if os.path.isfile(status_path):
        try:
            with open(status_path, "r", encoding="utf-8") as f:
                current = json.load(f)
            current["test_status"] = {"status": "failure", "error": "manual stop"}
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    _set_test_status(m, "failure", error="manual stop")
    db.commit()
    return {"success": True, "message": "测试已终止"}


@router.get("/{model_id}/log/training")
def get_logs(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """获取训练日志"""
    m = check_model_owner(model_id, user["user_id"], db)

    if _training_st(m) not in ("training", "success", "failure"):
        raise HTTPException(status_code=400, detail="无可用日志")

    dest_dir = m.upload_path
    if not dest_dir:
        return {"log": None}
    log_dir = os.path.join(dest_dir, "log", "training")
    if not os.path.isdir(log_dir):
        return {"log": None}

    log_files = sorted(f for f in os.listdir(log_dir) if f.endswith(".log"))
    if not log_files:
        return {"log": None}

    try:
        with open(os.path.join(log_dir, log_files[-1]), "r", encoding="utf-8") as f:
            lines = f.readlines()
            log_text = "".join(lines[-100:])
    except Exception:
        log_text = None

    return {"log": log_text}


@router.get("/{model_id}/log/test")
def get_test_logs(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """获取测试日志"""
    m = check_model_owner(model_id, user["user_id"], db)

    if _test_st(m) not in ("generating", "success", "failure"):
        raise HTTPException(status_code=400, detail="无可用日志")

    dest_dir = m.upload_path
    if not dest_dir:
        return {"log": None}
    log_dir = os.path.join(dest_dir, "log", "test")
    if not os.path.isdir(log_dir):
        return {"log": None}

    log_files = sorted(f for f in os.listdir(log_dir) if f.endswith(".log"))
    if not log_files:
        return {"log": None}

    try:
        with open(os.path.join(log_dir, log_files[-1]), "r", encoding="utf-8") as f:
            lines = f.readlines()
            log_text = "".join(lines[-100:])
    except Exception:
        log_text = None

    return {"log": log_text}


# ── 训练状态轮询 ─────────────────────────────────────────


@router.get("/{model_id}/poll-status")
def poll_status(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """读取 status.json 并同步 training_status 和 test_status 到数据库"""
    m = check_model_owner(model_id, user["user_id"], db)

    if not m.upload_path:
        return {
            "data_status": _file_st(m),
            "training_status": _training_st(m),
            "test_status": _test_st(m),
        }

    status_path = os.path.join(m.upload_path, "status.json")
    if not os.path.isfile(status_path):
        _set_training_status(m, "failure", error="status lost")
        if _test_st(m) == "generating":
            _set_test_status(m, "failure", error="status lost")
        db.commit()
        return {"data_status": _file_st(m), "training_status": "failure", "test_status": _test_st(m)}

    try:
        with open(status_path, "r", encoding="utf-8") as f:
            file_status = json.load(f)
        train_obj = file_status.get("training_status", {})
        test_obj = file_status.get("test_status", {})
        file_train = train_obj.get("status", _training_st(m)) if isinstance(train_obj, dict) else _training_st(m)
        file_train_error = train_obj.get("error") if isinstance(train_obj, dict) else None
        file_test = test_obj.get("status", _test_st(m)) if isinstance(test_obj, dict) else _test_st(m)
        file_test_error = test_obj.get("error") if isinstance(test_obj, dict) else None

        if file_train != _training_st(m):
            if file_train_error:
                _set_training_status(m, file_train, error=file_train_error)
            else:
                _set_training_status(m, file_train)
        if file_test != _test_st(m):
            if file_test_error:
                _set_test_status(m, file_test, error=file_test_error)
            else:
                _set_test_status(m, file_test)
        db.commit()
    except Exception:
        logger.warning(f"poll_status failed model={model_id}", exc_info=True)

    return {
        "data_status": _file_st(m),
        "training_status": _training_st(m),
        "test_status": _test_st(m),
    }


# ── 模型下载 ─────────────────────────────────────────────


@router.post("/{model_id}/model/download-init")
def model_download_init(model_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """初始化模型分片下载"""
    m = check_model_owner(model_id, user["user_id"], db)
    if not m.upload_path:
        raise HTTPException(status_code=404, detail="模型文件不存在")
    model_dir = os.path.join(m.upload_path, "model")
    if not os.path.isdir(model_dir) or not os.listdir(model_dir):
        raise HTTPException(status_code=404, detail="模型文件不存在")
    t0 = time.time()
    zip_path = _create_model_zip(model_dir)
    try:
        file_size = os.path.getsize(zip_path)
        session = create_download_session(zip_path, "model.zip", file_size, user["user_id"])
    except Exception:
        os.unlink(zip_path)
        raise
    elapsed = time.time() - t0
    logger.info(f"模型分片下载 ZIP 打包完成 model={model_id} 耗时={elapsed:.1f}s size={file_size}")
    return {
        "session_id": session["session_id"],
        "filename": session["filename"],
        "size": file_size,
        "total_chunks": session["total_chunks"],
        "chunk_size": DOWNLOAD_CHUNK_SIZE,
    }


@router.get("/{model_id}/model/download-chunk")
def model_download_chunk(model_id: str, session_id: str, chunk_index: int,
                         db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """获取模型分片下载的一个 chunk"""
    m = check_model_owner(model_id, user["user_id"], db)
    data, file_size = get_download_chunk(session_id, chunk_index)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={
            "Content-Length": str(len(data)),
            "Content-Range": f"bytes {chunk_index * DOWNLOAD_CHUNK_SIZE}-{min((chunk_index + 1) * DOWNLOAD_CHUNK_SIZE, file_size) - 1}/{file_size}",
        },
    )


@router.post("/{model_id}/model/download-cleanup")
def model_download_cleanup(model_id: str, session_id: str,
                           db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    """清理模型分片下载会话"""
    check_model_owner(model_id, user["user_id"], db)
    delete_session(session_id)
    return {"success": True}
