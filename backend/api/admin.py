from enum import Enum
from typing import Any, ClassVar, Optional

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

from api.auth.security import verify_password
from api.db.base import AsyncSessionLocal, engine
from api.db.models import (
    AIProviderConfig,
    Clo3dProject,
    Clo3dRenderTask,
    EcommercePoster,
    Material,
    PrjTemplate,
    PromptFeature,
    PromptTemplate,
    Role,
    User,
    UserRole,
)


class ProviderType(str, Enum):
    OPENAI = "openai"
    OPENAI_IMAGE_EDIT = "openai_image_edit"
    GPTPROTO = "gptproto"
    REPLICATE = "replicate"
    TOPAZ = "topaz"
    VECTORIZER_AI = "vectorizer_ai"


class TaskType(str, Enum):
    TEXT2IMG = "text2img"
    IMG2IMG = "img2img"
    ANALYZE = "analyze"


DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "openai_image_edit": "https://api.openai.com/v1",
    "gptproto": "https://gptproto.com/api/v3",
    "replicate": "https://api.replicate.com/v1",
    "topaz": "https://api.topazlabs.com/image/v1",
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


class MaterialView(ModelView):
    name = "Material"
    label = "Materials"

    fields = [
        IntegerField("id", exclude_from_create=True, exclude_from_edit=True),
        IntegerField("uploaded_by", exclude_from_create=True, exclude_from_edit=True),
        StringField("original_filename", label="原始文件名"),
        StringField(
            "stored_filename", label="存储文件名", exclude_from_create=True, exclude_from_edit=True
        ),
        IntegerField(
            "file_size", label="文件大小", exclude_from_create=True, exclude_from_edit=True
        ),
        StringField(
            "mime_type", label="MIME 类型", exclude_from_create=True, exclude_from_edit=True
        ),
        FileField("file", label="文件", exclude_from_list=True),
        JSONField("meta", label="元数据", exclude_from_list=True),
        StringField("created_at", exclude_from_create=True, exclude_from_edit=True),
    ]

    exclude_fields_from_list = ["meta", "created_at", "deleted_at", "stored_filename"]
    searchable_fields = ["original_filename", "mime_type"]
    sortable_fields = ["id", "original_filename", "file_size", "created_at"]


class PrjTemplateView(ModelView):
    name = "DXF Template"
    label = "DXF Templates"

    fields = [
        IntegerField("id", exclude_from_create=True, exclude_from_edit=True),
        StringField("name", required=True, help_text="模板名称"),
        StringField("category", required=True, help_text="分类: T恤, 卫衣, 裤子 等"),
        FileField(
            "prj_file",
            label="DXF 文件",
            accept=".dxf,application/dxf,application/x-dxf,application/octet-stream,text/plain",
            help_text="请选择 .dxf 模板文件",
            exclude_from_list=True,
        ),
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


class PromptFeatureView(ModelView):
    name = "Prompt Feature"
    label = "Prompt Features"

    fields: ClassVar[list[Any]] = [
        IntegerField("id", exclude_from_create=True, exclude_from_edit=True),
        StringField("key", required=True, help_text="唯一标识, 例如 preserve_style"),
        StringField("label", required=True, help_text="前端展示名称"),
        StringField("description", help_text="前端展示说明"),
        StringField(
            "prompt",
            required=True,
            maxlength=5000,
            help_text="勾选该功能后追加到最终生成提示词的内容",
        ),
        IntegerField("sort_order", help_text="排序值, 越小越靠前"),
        BooleanField("is_default", help_text="前端默认勾选"),
        BooleanField("is_active", help_text="启用/禁用"),
        StringField("created_at", exclude_from_create=True, exclude_from_edit=True),
        StringField("updated_at", exclude_from_create=True, exclude_from_edit=True),
    ]

    exclude_fields_from_list: ClassVar[list[str]] = [
        "prompt",
        "created_at",
        "updated_at",
        "deleted_at",
    ]
    searchable_fields: ClassVar[list[str]] = ["key", "label", "description"]
    sortable_fields: ClassVar[list[str]] = [
        "id",
        "key",
        "label",
        "sort_order",
        "is_default",
        "is_active",
    ]

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        if "sort_order" not in data or data["sort_order"] is None:
            data["sort_order"] = 0
            obj.sort_order = 0

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


class EcommercePosterView(ModelView):
    name = "E-commerce Poster"
    label = "E-commerce Posters"

    fields = [
        IntegerField("id", exclude_from_create=True, exclude_from_edit=True),
        IntegerField("user_id", label="用户 ID", exclude_from_create=True, exclude_from_edit=True),
        StringField("name", label="名称", required=False),
        StringField("product_type", label="产品类型", required=True),
        StringField("style", label="风格", required=True),
        StringField("custom_prompt", label="自定义提示词", exclude_from_list=True),
        JSONField("material_ids", label="素材 ID 列表", exclude_from_list=True),
        IntegerField("image_count", label="图片数量"),
        IntegerField("width", label="宽度"),
        IntegerField("height", label="高度"),
        StringField("status", label="状态"),
        JSONField("result_images", label="结果图片 URL", exclude_from_list=True),
        JSONField("generation_params", label="生成参数", exclude_from_list=True),
        StringField("created_at", exclude_from_create=True, exclude_from_edit=True),
    ]

    exclude_fields_from_list = [
        "custom_prompt", "material_ids", "result_images", "generation_params",
        "created_at", "deleted_at",
    ]
    searchable_fields = ["name", "product_type", "style", "status"]
    sortable_fields = ["id", "product_type", "style", "status", "image_count", "created_at"]


class Clo3dProjectView(ModelView):
    name = "CLO3D Project"
    label = "CLO3D Projects"

    fields = [
        IntegerField("id", exclude_from_create=True, exclude_from_edit=True),
        IntegerField("user_id", label="用户 ID", exclude_from_create=True, exclude_from_edit=True),
        StringField("name", required=True, help_text="项目名称"),
        StringField("category", required=True, help_text="分类"),
        FileField("prj_file", label="ZPRJ 文件", accept=".zprj", exclude_from_list=True),
        ImageField("preview_image", label="预览图", exclude_from_list=True),
        JSONField("pieces", label="版片数据", exclude_from_list=True),
        IntegerField("piece_count", label="版片数量", exclude_from_create=True, exclude_from_edit=True),
        StringField("status", label="状态"),
        StringField("created_at", exclude_from_create=True, exclude_from_edit=True),
    ]

    exclude_fields_from_list = ["pieces", "created_at", "deleted_at", "prj_file"]
    searchable_fields = ["name", "category", "status"]
    sortable_fields = ["id", "name", "category", "status", "piece_count", "created_at"]


class Clo3dRenderTaskView(ModelView):
    name = "CLO3D Render Task"
    label = "CLO3D Render Tasks"

    fields = [
        IntegerField("id", exclude_from_create=True, exclude_from_edit=True),
        IntegerField("project_id", label="项目 ID"),
        IntegerField("user_id", label="用户 ID", exclude_from_create=True, exclude_from_edit=True),
        JSONField("material_assignments", label="面料分配", exclude_from_list=True),
        StringField("status", label="状态"),
        ImageField("front_image", label="正面渲染图", exclude_from_list=True),
        ImageField("back_image", label="背面渲染图", exclude_from_list=True),
        StringField("error_message", label="错误信息", exclude_from_list=True),
        StringField("created_at", exclude_from_create=True, exclude_from_edit=True),
        StringField("completed_at", exclude_from_create=True, exclude_from_edit=True),
    ]

    exclude_fields_from_list = [
        "material_assignments", "error_message", "created_at", "completed_at", "deleted_at",
    ]
    searchable_fields = ["status"]
    sortable_fields = ["id", "project_id", "status", "created_at"]


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
    admin.add_view(MaterialView(Material, icon="fa fa-image"))
    admin.add_view(PrjTemplateView(PrjTemplate, icon="fa fa-file-code"))
    admin.add_view(PromptTemplateView(PromptTemplate, icon="fa fa-comment-alt"))
    admin.add_view(PromptFeatureView(PromptFeature, icon="fa fa-list-check"))
    admin.add_view(AIProviderConfigView(AIProviderConfig, icon="fa fa-key"))
    admin.add_view(EcommercePosterView(EcommercePoster, icon="fa fa-shopping-cart"))
    admin.add_view(Clo3dProjectView(Clo3dProject, icon="fa fa-tshirt"))
    admin.add_view(Clo3dRenderTaskView(Clo3dRenderTask, icon="fa fa-image"))

    return admin
