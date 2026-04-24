from datetime import datetime
from typing import Optional

from api.db.base import SoftDeleteMixin
from sqlalchemy import JSON, Column, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declared_attr
from sqlmodel import Field, Relationship


class User(SoftDeleteMixin, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(max_length=50, unique=True, index=True)
    email: Optional[str] = Field(default=None, max_length=255)
    password_hash: str = Field(max_length=255)
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": "now()"}
    )
    updated_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": "now()", "onupdate": "now()"}
    )

    designs: list["Design"] = Relationship(back_populates="user", cascade_delete=True)
    user_roles: list["UserRole"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    materials: list["Material"] = Relationship(
        back_populates="user", cascade_delete=True
    )

    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "users"


class Role(SoftDeleteMixin, table=True):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "roles"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=50, unique=True, index=True)
    permissions: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": "now()"}
    )

    user_roles: list["UserRole"] = Relationship(
        back_populates="role", cascade_delete=True
    )


class UserRole(SoftDeleteMixin, table=True):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "user_roles"

    @declared_attr.directive
    def __table_args__(cls):
        return (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(
            ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    role_id: int = Field(
        sa_column=Column(
            ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": "now()"}
    )

    user: Optional[User] = Relationship(back_populates="user_roles")
    role: Optional[Role] = Relationship(back_populates="user_roles")


class Design(SoftDeleteMixin, table=True):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "designs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: Optional[int] = Field(
        default=None,
        sa_column=Column(ForeignKey("users.id", ondelete="SET NULL"), index=True),
    )
    name: str = Field(max_length=255)
    status: str = Field(default="draft", max_length=50, index=True)
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": "now()"}, index=True
    )
    updated_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": "now()", "onupdate": "now()"}
    )

    user: Optional[User] = Relationship(back_populates="designs")
    versions: list["DesignVersion"] = Relationship(
        back_populates="design", cascade_delete=True
    )


class DesignVersion(SoftDeleteMixin, table=True):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "design_versions"

    @declared_attr.directive
    def __table_args__(cls):
        return (UniqueConstraint("design_id", "version", name="uq_design_version"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    design_id: int = Field(
        sa_column=Column(
            ForeignKey("designs.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    version: int
    data: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": "now()"}
    )

    design: Optional[Design] = Relationship(back_populates="versions")


class Material(SoftDeleteMixin, table=True):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "materials"

    id: Optional[int] = Field(default=None, primary_key=True)
    uploaded_by: Optional[int] = Field(
        default=None,
        sa_column=Column(ForeignKey("users.id", ondelete="SET NULL"), index=True),
    )
    original_filename: Optional[str] = Field(default=None, max_length=255)
    stored_filename: Optional[str] = Field(default=None, max_length=255, unique=True)
    file_size: Optional[int] = Field(default=None)
    mime_type: Optional[str] = Field(default=None, max_length=100)
    storage_path: str = Field(max_length=500)
    meta: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": "now()"}, index=True
    )

    user: Optional[User] = Relationship(back_populates="materials")


class Template(SoftDeleteMixin, table=True):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "templates"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    category: str = Field(max_length=50)
    image_path: str = Field(max_length=500)
    is_builtin: int = Field(default=0)
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": "now()"}
    )
