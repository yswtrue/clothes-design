from typing import Any, Optional
import uuid

from api.auth.security import verify_password
from api.db.base import AsyncSessionLocal, engine
from api.db.models import Design, Material, Role, Template, User, UserRole
from api.storage.factory import get_storage_service
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin import I18nConfig
from starlette_admin.auth import AdminConfig, AdminUser, AuthProvider
from starlette_admin.contrib.sqlmodel import Admin, ModelView
from starlette_admin.exceptions import FormValidationError, LoginFailed
from starlette_admin.fields import FileField, StringField


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


class TemplateView(ModelView):
    fields = [
        StringField("id", exclude_from_create=True, exclude_from_edit=True),
        StringField("name", required=True),
        StringField("category", required=True),
        FileField("image_file", label="Template Image", exclude_from_list=True),
        StringField("image_path", exclude_from_create=True, exclude_from_edit=True),
        StringField("created_at", exclude_from_create=True, exclude_from_edit=True),
    ]

    async def before_create(self, request: Request, data: dict[str, Any], obj: Any) -> None:
        image_file = data.get("image_file")

        if image_file and hasattr(image_file, "read"):
            content = await image_file.read()
            filename = getattr(image_file, "filename", "template.png")

            file_id = str(uuid.uuid4())
            storage_key = f"templates/{file_id}_{filename}"

            storage = get_storage_service()
            image_path = await storage.upload(content, storage_key)

            data["image_path"] = image_path
            obj.image_path = image_path

        if "image_file" in data:
            del data["image_file"]

        data["is_builtin"] = 1
        obj.is_builtin = 1


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
    admin.add_view(ModelView(Design, icon="fa fa-palette"))
    admin.add_view(ModelView(Material, icon="fa fa-image"))
    admin.add_view(TemplateView(Template, icon="fa fa-shapes"))

    return admin
