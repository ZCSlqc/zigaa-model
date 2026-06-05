"""管理后台 API — 用户 CRUD + 重置密码 + 项目管理"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import User, Project, ModelInfo
from core.auth import hash_password, require_admin
from services.helper import validate_username, VALID_ROLES

router = APIRouter()


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class ResetPasswordRequest(BaseModel):
    password: str


class UpdateRoleRequest(BaseModel):
    role: str


# 排序权重：admin 最高，advanced 次之，user 最低
_ROLE_WEIGHT = {"admin": 0, "advanced": 1, "user": 2}


@router.get("/users")
def list_users(
    search: str = Query("", description="用户名搜索"),
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    users = db.query(User)

    if search:
        users = users.filter(User.username.ilike(f"%{search}%"))

    # 按角色权重排序，再按创建时间倒序
    users = users.order_by(User.created_at.desc()).all()
    users.sort(key=lambda u: _ROLE_WEIGHT.get(u.role, 99))

    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "created_at": u.created_at,
            "project_count": db.query(Project).filter(Project.owner_id == u.id).count(),
        }
        for u in users
    ]


@router.post("/users")
def create_user(req: CreateUserRequest, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    try:
        clean_name = validate_username(req.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if db.query(User).filter(User.username == clean_name).first():
        raise HTTPException(status_code=409, detail="用户名已存在")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少6位")
    if req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"角色必须是 {', '.join(VALID_ROLES)}")
    u = User(username=clean_name, password_hash=hash_password(req.password), role=req.role)
    db.add(u)
    db.commit()
    return {"message": "用户创建成功"}


@router.put("/users/{user_id}")
def update_user_role(user_id: str, req: UpdateRoleRequest, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    if req.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"角色必须是 {', '.join(VALID_ROLES)}")
    u.role = req.role
    db.commit()
    return {"message": "角色更新成功"}


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: str, req: ResetPasswordRequest, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少6位")
    u.password_hash = hash_password(req.password)
    db.commit()
    return {"message": "密码重置成功"}


@router.delete("/users/{user_id}")
def delete_user(user_id: str, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    u = db.query(User).filter(User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="用户不存在")
    if u.username == "zigaa":
        raise HTTPException(status_code=400, detail="不能删除默认管理员")
    db.delete(u)
    db.commit()
    return {"message": "用户已删除"}


@router.get("/projects")
def list_all_projects(
    project_name: str = Query("", description="按项目名称搜索"),
    owner_name: str = Query("", description="按所属用户名搜索"),
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    query = db.query(Project).join(User, Project.owner_id == User.id)

    if project_name:
        query = query.filter(Project.name.ilike(f"%{project_name}%"))
    if owner_name:
        query = query.filter(User.username.ilike(f"%{owner_name}%"))

    projects = query.order_by(Project.created_at.desc()).all()

    # Batch fetch all models for these projects instead of N+1
    project_ids = [p.id for p in projects]
    models_by_project: dict[str, list[ModelInfo]] = {}
    if project_ids:
        all_models = db.query(ModelInfo).filter(
            ModelInfo.project_id.in_(project_ids)
        ).order_by(ModelInfo.created_at.desc()).all()
        for mi in all_models:
            models_by_project.setdefault(mi.project_id, []).append(mi)

    # Cache owners
    owner_ids = [p.owner_id for p in projects]
    owner_cache = {u.id: u for u in db.query(User).filter(User.id.in_(owner_ids)).all()} if owner_ids else {}

    result = []
    for p in projects:
        owner = owner_cache.get(p.owner_id)
        models = models_by_project.get(p.id, [])

        result.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "owner_id": p.owner_id,
            "owner_name": owner.username if owner else "未知",
            "created_at": p.created_at,
            "models": [
                {
                    "id": m.id,
                    "name": m.name,
                    "status": m.status,
                    "created_at": m.created_at,
                }
                for m in models
            ],
        })

    return result


@router.delete("/projects/{project_id}")
def admin_delete_project(project_id: str, db: Session = Depends(get_db), _admin: dict = Depends(require_admin)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 清理项目下所有模型的上传文件
    models = db.query(ModelInfo).filter(ModelInfo.project_id == project_id).all()
    from services.resource import clear_project
    clear_project([m.id for m in models])

    db.delete(p)
    db.commit()
    return {"message": "项目已删除"}
