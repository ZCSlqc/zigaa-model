import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, ForeignKey, Integer, JSON, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from core.database import Base


def gen_id():
    return str(uuid.uuid4())


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_id)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")
    created_at = Column(String(32), default=now_iso)
    uploaded_at = Column(String(32), default=now_iso)

    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=gen_id)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(String(32), default=now_iso)
    uploaded_at = Column(String(32), default=now_iso)

    __table_args__ = (
        Index("idx_projects_owner_id", "owner_id"),
    )

    owner = relationship("User", back_populates="projects")
    models = relationship("ModelInfo", back_populates="project", cascade="all, delete-orphan")


class ModelInfo(Base):
    __tablename__ = "model_info"

    id = Column(String(36), primary_key=True, default=gen_id)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status = Column(JSON, nullable=True)
    upload_path = Column(String(500), nullable=True)
    created_at = Column(String(32), default=now_iso)
    uploaded_at = Column(String(32), default=now_iso)

    __table_args__ = (
        Index("idx_model_info_project_id", "project_id"),
    )

    project = relationship("Project", back_populates="models")
    data_packages = relationship("DataPackage", back_populates="model", cascade="all, delete-orphan")


class DataPackage(Base):
    __tablename__ = "data_packages"

    id = Column(String(36), primary_key=True, default=gen_id)
    model_id = Column(String(36), ForeignKey("model_info.id", ondelete="CASCADE"), nullable=False)
    resource_type = Column(String(20), nullable=False)
    file_path = Column(String(500), nullable=False)
    passed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    errors = Column(JSON, default=list)
    created_at = Column(String(32), default=now_iso)
    uploaded_at = Column(String(32), default=now_iso)

    __table_args__ = (
        UniqueConstraint("model_id", "resource_type", name="uq_model_resource"),
    )

    model = relationship("ModelInfo", back_populates="data_packages")


