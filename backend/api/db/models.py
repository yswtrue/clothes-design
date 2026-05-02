from datetime import datetime
from typing import Any, Optional

from api.db.base import SoftDeleteMixin
from api.storage.storages import (
    generated_image_storage,
    material_storage,
    output_tif_storage,
    preview_storage,
    prj_storage,
    thumbnail_storage,
)
from fastapi_storages.integrations.sqlalchemy import FileType
from sqlalchemy import JSON, Column, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.orm import declared_attr
from sqlmodel import Field, Relationship


class User(SoftDeleteMixin, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(max_length=50, unique=True, index=True)
    email: Optional[str] = Field(default=None, max_length=255)
    password_hash: str = Field(max_length=255)
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now()}
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"server_default": func.now(), "onupdate": datetime.utcnow}
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
        default=None, sa_column_kwargs={"server_default": func.now()}
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
        default=None, sa_column_kwargs={"server_default": func.now()}
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
    generated_design_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            ForeignKey("generated_designs.id", ondelete="SET NULL"), index=True
        ),
    )
    prj_template_id: Optional[int] = Field(
        default=None,
        sa_column=Column(
            ForeignKey("prj_templates.id", ondelete="SET NULL"), index=True
        ),
    )
    name: str = Field(max_length=255)
    status: str = Field(default="draft", max_length=50, index=True)
    output_tif: Any = Field(default=None, sa_column=Column("output_tif_path", FileType(storage=output_tif_storage), nullable=True))
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now()}, index=True
    )
    updated_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now(), "onupdate": datetime.utcnow}
    )

    user: Optional[User] = Relationship(back_populates="designs")
    generated_design: Optional["GeneratedDesign"] = Relationship(
        back_populates="designs"
    )
    prj_template: Optional["PrjTemplate"] = Relationship(back_populates="designs")
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
        default=None, sa_column_kwargs={"server_default": func.now()}
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
    file: Any = Field(default=None, sa_column=Column("storage_path", FileType(storage=material_storage), nullable=False))
    meta: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now()}, index=True
    )

    user: Optional[User] = Relationship(back_populates="materials")
    generated_designs: list["GeneratedDesign"] = Relationship(
        back_populates="material", cascade_delete=True
    )


class PrjTemplate(SoftDeleteMixin, table=True):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "prj_templates"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, index=True)
    category: str = Field(max_length=50, index=True)
    prj_file: Any = Field(default=None, sa_column=Column("prj_path", FileType(storage=prj_storage), nullable=True))
    preview_image: Any = Field(default=None, sa_column=Column(FileType(storage=preview_storage), nullable=True))
    regions: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    is_builtin: int = Field(default=1)
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now()}
    )

    designs: list["Design"] = Relationship(back_populates="prj_template")


class GeneratedDesign(SoftDeleteMixin, table=True):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "generated_designs"

    id: Optional[int] = Field(default=None, primary_key=True)
    material_id: int = Field(
        sa_column=Column(
            ForeignKey("materials.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    image: Any = Field(default=None, sa_column=Column("image_path", FileType(storage=generated_image_storage), nullable=False))
    thumbnail: Any = Field(default=None, sa_column=Column("thumbnail_path", FileType(storage=thumbnail_storage), nullable=True))
    prompt_used: Optional[str] = Field(default=None)
    seed: Optional[int] = Field(default=None)
    variant_index: int = Field(default=0)
    generation_params: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    is_selected: int = Field(default=0, index=True)
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now()}, index=True
    )

    material: Optional["Material"] = Relationship(back_populates="generated_designs")
    designs: list["Design"] = Relationship(back_populates="generated_design")


class LoginSession(SoftDeleteMixin, table=True):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "login_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(
        sa_column=Column(
            ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
        )
    )
    login_token: str = Field(max_length=36, unique=True, index=True)
    token_type: str = Field(max_length=20, index=True)
    expires_at: datetime = Field(index=True)
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now()}
    )

    user: Optional[User] = Relationship()


class AIProviderConfig(SoftDeleteMixin, table=True):
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "ai_provider_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    provider_type: str = Field(max_length=50, index=True)
    name: str = Field(max_length=100)
    base_url: Optional[str] = Field(default=None, max_length=500)
    api_key: str = Field(max_length=500)
    model_name: str = Field(max_length=100)
    is_active: int = Field(default=1, index=True)
    priority: int = Field(default=0, index=True)
    rate_limit: Optional[int] = Field(default=None)
    config: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now()}
    )
    updated_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now(), "onupdate": datetime.utcnow}
    )


class PromptTemplate(SoftDeleteMixin, table=True):
    """Prompt templates for AI generation tasks.
    
    Supports variable placeholders:
    - {style_description}: Style analysis description
    - {color_palette}: Comma-separated color list
    - {pattern_type}: 'seamless' or 'standalone'
    - {width}, {height}: Image dimensions
    """
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return "prompt_templates"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=100, unique=True, index=True)
    task_type: str = Field(max_length=50, index=True)  # text2img, img2img, analyze
    provider_type: Optional[str] = Field(default=None, max_length=50, index=True)  # null = all providers
    template: str = Field(sa_column=Column("template", Text, nullable=False))
    description: Optional[str] = Field(default=None, max_length=500)
    is_default: int = Field(default=0, index=True)
    is_active: int = Field(default=1, index=True)
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now()}
    )
    updated_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now(), "onupdate": datetime.utcnow}
    )
