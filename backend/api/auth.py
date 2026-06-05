from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import User, Project
from core.auth import hash_password, verify_password, create_token, get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class TokenResponse(BaseModel):
    token: str
    username: str
    role: str


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = create_token(user.username, user.role, user.id)
    return TokenResponse(token=token, username=user.username, role=user.role)


@router.post("/logout")
def logout(user: dict = Depends(get_current_user)):
    return {"message": "登出成功"}


@router.get("/me")
def me(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user["user_id"]).first()
    project_count = db.query(func.count(Project.id)).filter(Project.owner_id == user["user_id"]).scalar()
    return {
        "username": user["username"],
        "role": user["role"],
        "user_id": user["user_id"],
        "created_at": db_user.created_at if db_user else "",
        "project_count": project_count,
    }


@router.post("/change-password")
def change_password(req: ChangePasswordRequest, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_user = db.query(User).filter(User.id == user["user_id"]).first()
    if not db_user or not verify_password(req.old_password, db_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    if len(req.new_password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="新密码至少6位")
    db_user.password_hash = hash_password(req.new_password)
    db.commit()
    return {"message": "密码修改成功"}
