from enum import Enum
from typing import Any, Optional

from api.auth.security import verify_password
from api.db.base import AsyncSessionLocal, engine
from api.db.models import AIProviderConfig, Material, PrjTemplate, PromptTemplate, Role, User, UserRole
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin import I18nConfig
from starlette_admin.auth import AdminConfig, AdminUser, AuthProvider
from starlette_admin.contrib.sqlmodel import Admin, ModelView
from starlette_admin.exceptions import FormValidationError, LoginFailed
from starlette_admin.fields import (
    BooleanField,
    EnumField,
    FileField,
    ImageField,
    IntegerField,
    JSONField,
    PasswordField,
    StringField,
)


class ProviderType(str, Enum):
    OPENAI = "openai"
    OPENAI_IMAGE_EDIT = "openai_image_edit"
    REPLICATE = "replicate"
    VECTORIZER_AI = "vectorizer_ai"


class TaskType(str, Enum):
    TEXT2IMG = "text2img"
    IMG2IMG = "img2img"
    ANALYZE = "analyze"


DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "openai_image_edit": "https://api.openai.com/v1",
    "replicate": "https://api.replicate.com/v1",
    "vectorizer_ai": "https://api.vectorizer.ai/api/v1",
}


class JWTAuthProvider(AuthProvider):
    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        if len(username) < 3:
            raise FormValidationError({"username": "Username must be at least 3 characters"})

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.username == username)  # type: ignore[arg-type]
            )
            user = result.scalar_one_or_none()

            if not user or not verify_password(password, user.password_hash):
                raise LoginFailed("Invalid username or password")

            roles_result = await session.execute(
                select(Role)
                .join(UserRole, UserRole.role_id == Role.id)  # type: ignore[arg-type]
                .where(UserRole.user_id == user.id)  # type: ignore[arg-type]
            )
            roles = list(roles_result.scalars().all())

            has_admin = any(
                role.permissions and (role.permissions.get("*") or role.permissions.get("admin"))
                for role in roles
            )

            if not has_admin:
                raise LoginFailed("Access denied: admin permission required")

            request.session.update({"user_id": user.id, "username": user.username})
            return response

    async def is_authenticated(self, request: Request) -> bool:
        user_id = request.session.get("user_id")
        if not user_id:
            return False

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.id == user_id)  # type: ignore[arg-type]
            )
            user = result.scalar_one_or_none()

            if user:
                request.state.user = user
                return True

        return False

    def get_admin_config(self, request: Request) -> AdminConfig:
        return AdminConfig(app_title="Clothes Design Admin")

    def get_admin_user(self, request: Request) -> Optional[AdminUser]:
        user = getattr(request.state, "user", None)
        if user is None:
            return None
        return AdminUser(username=user.username)

    async def logout(self, request: Request, response: Response) -> Response:
        request.session.clear()
        return response


class AIProviderConfigView(ModelView):
    name = "AI Provider"
    label = "AI Providers"

    fields = [
        IntegerField("id", exclude_from_create=True, exclude_from_edit=True),
        EnumField("provider_type", enum=ProviderType, required=True),
        StringField("name", required=True, help_text="Display name"),
        StringField(
            "base_url",
            required=False,
            help_text="留空使用默认 URL",
        ),
        PasswordField("api_key", required=True, help_text="API key"),
        StringField("model_name", required=True, help_text="Model identifier"),
        BooleanField("is_active", help_text="Enable/disable this provider"),
        IntegerField("priority", help_text="Lower number = higher priority"),
        IntegerField("rate_limit", help_text="Requests per minute (optional)"),
        JSONField("config", help_text="Extra configuration (JSON)"),
        StringField("created_at", exclude_from_create=True, exclude_from_edit=True),
        StringField("updated_at", exclude_from_create=True, exclude_from_edit=True),
    ]

    exclude_fields_from_list = ["api_key", "config", "created_at", "updated_at", "deleted_at"]
    searchable_fields = ["name", "provider_type", "model_name"]
    sortable_fields = ["id", "provider_type", "name", "priority", "is_active"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        if "is_active" not in data or data["is_active"] is None:
            data["is_active"] = 1
            obj.is_active = 1
        else:
            data["is_active"] = 1 if data["is_active"] else 0
            obj.is_active = data["is_active"]

        if "priority" not in data or data["priority"] is None:
            data["priority"] = 0
            obj.priority = 0

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        if "is_active" in data:
            data["is_active"] = 1 if data["is_active"] else 0
            obj.is_active = data["is_active"]


class PrjTemplateView(ModelView):
    name = "PRJ Template"
    label = "PRJ Templates"

    fields = [
        IntegerField("id", exclude_from_create=True, exclude_from_edit=True),
        StringField("name", required=True, help_text="模板名称"),
        StringField("category", required=True, help_text="分类: T恤, 卫衣, 裤子 等"),
        FileField("prj_file", label="PRJ 文件", exclude_from_list=True),
        ImageField("preview_image", label="预览图", exclude_from_list=True),
        BooleanField("is_builtin", help_text="内置模板"),
        StringField("created_at", exclude_from_create=True, exclude_from_edit=True),
    ]

    exclude_fields_from_list = ["created_at", "deleted_at", "regions"]
    searchable_fields = ["name", "category"]
    sortable_fields = ["id", "name", "category", "is_builtin"]

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        if "is_builtin" not in data or data["is_builtin"] is None:
            data["is_builtin"] = 1
            obj.is_builtin = 1
        else:
            data["is_builtin"] = 1 if data["is_builtin"] else 0
            obj.is_builtin = data["is_builtin"]

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        if "is_builtin" in data:
            data["is_builtin"] = 1 if data["is_builtin"] else 0
            obj.is_builtin = data["is_builtin"]


class PromptTemplateView(ModelView):
    name = "Prompt Template"
    label = "Prompt Templates"

    fields = [
        IntegerField("id", exclude_from_create=True, exclude_from_edit=True),
        StringField("name", required=True, help_text="模板名称（唯一）"),
        EnumField("task_type", enum=TaskType, required=True, help_text="任务类型"),
        EnumField(
            "provider_type",
            enum=ProviderType,
            required=False,
            help_text="指定 Provider（留空=通用）",
        ),
        StringField(
            "template",
            required=True,
            maxlength=5000,
            help_text="模板内容，支持变量: {style_description}, {color_palette}, {pattern_type}, {width}, {height}",
        ),
        StringField("description", help_text="模板描述"),
        BooleanField("is_default", help_text="设为该任务类型的默认模板"),
        BooleanField("is_active", help_text="启用/禁用"),
        StringField("created_at", exclude_from_create=True, exclude_from_edit=True),
        StringField("updated_at", exclude_from_create=True, exclude_from_edit=True),
    ]

    exclude_fields_from_list = ["template", "created_at", "updated_at", "deleted_at"]
    searchable_fields = ["name", "task_type", "provider_type"]
    sortable_fields = ["id", "name", "task_type", "provider_type", "is_default", "is_active"]

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        if "is_active" not in data or data["is_active"] is None:
            data["is_active"] = 1
            obj.is_active = 1
        else:
            data["is_active"] = 1 if data["is_active"] else 0
            obj.is_active = data["is_active"]

        if "is_default" not in data or data["is_default"] is None:
            data["is_default"] = 0
            obj.is_default = 0
        else:
            data["is_default"] = 1 if data["is_default"] else 0
            obj.is_default = data["is_default"]

    async def before_edit(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        if "is_active" in data:
            data["is_active"] = 1 if data["is_active"] else 0
            obj.is_active = data["is_active"]

        if "is_default" in data:
            data["is_default"] = 1 if data["is_default"] else 0
            obj.is_default = data["is_default"]


def create_admin() -> Admin:
    admin = Admin(
        engine,
        title="Clothes Design Admin",
        base_url="/admin",
        auth_provider=JWTAuthProvider(),
        i18n_config=I18nConfig(default_locale="zh_Hant", language_switcher=["zh_Hant", "en"]),
    )

    admin.add_view(ModelView(User, icon="fa fa-users"))
    admin.add_view(ModelView(Role, icon="fa fa-shield"))
    admin.add_view(ModelView(UserRole, icon="fa fa-user-tag"))
    admin.add_view(ModelView(Material, icon="fa fa-image"))
    admin.add_view(PrjTemplateView(PrjTemplate, icon="fa fa-file-code"))
    admin.add_view(PromptTemplateView(PromptTemplate, icon="fa fa-comment-alt"))
    admin.add_view(AIProviderConfigView(AIProviderConfig, icon="fa fa-key"))

    return admin
