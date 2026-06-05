from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import Project, ModelInfo
from core.auth import get_current_user
from services.resource import clear_project

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    owner_id: str
    created_at: str
    models: list = []

    class Config:
        from_attributes = True


@router.get("/")
def list_projects(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    projects = (
        db.query(Project)
        .filter(Project.owner_id == user["user_id"])
        .order_by(Project.created_at.desc())
        .all()
    )
    # 一次查询获取所有项目的模型数量
    model_counts = (
        db.query(ModelInfo.project_id, func.count(ModelInfo.id))
        .filter(ModelInfo.project_id.in_([p.id for p in projects]))
        .group_by(ModelInfo.project_id)
        .all()
    )
    counts_map = {pid: cnt for pid, cnt in model_counts}
    result = []
    for p in projects:
        d = ProjectOut.model_validate(p).model_dump()
        d["models"] = [{"count": counts_map.get(p.id, 0)}]
        result.append(d)
    return result


@router.post("/")
def create_project(req: CreateProjectRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="项目名称不能为空")
    if len(name) > 200:
        raise HTTPException(status_code=400, detail="项目名称不能超过200个字符")
    p = Project(name=name, description=req.description.strip(), owner_id=user["user_id"])
    db.add(p)
    db.commit()
    db.refresh(p)
    return ProjectOut.model_validate(p)


@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p or p.owner_id != user["user_id"]:
        raise HTTPException(status_code=404, detail="项目不存在")
    models = db.query(ModelInfo).filter(ModelInfo.project_id == p.id).all()
    d = ProjectOut.model_validate(p).model_dump()
    d["models"] = [{"id": m.id, "name": m.name} for m in models]
    return d


@router.put("/{project_id}")
def update_project(project_id: str, req: UpdateProjectRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p or p.owner_id != user["user_id"]:
        raise HTTPException(status_code=404, detail="项目不存在")
    if req.name is not None:
        name = req.name.strip()
        if len(name) > 200:
            raise HTTPException(status_code=400, detail="项目名称不能超过200个字符")
        p.name = name
    if req.description is not None:
        p.description = req.description.strip()
    db.commit()
    return {"message": "更新成功"}


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    p = db.query(Project).filter(Project.id == project_id).first()
    if not p or p.owner_id != user["user_id"]:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 清理项目下所有模型的上传文件
    models = db.query(ModelInfo).filter(ModelInfo.project_id == project_id).all()
    clear_project([m.id for m in models])

    db.delete(p)
    db.commit()
    return {"message": "删除成功"}
