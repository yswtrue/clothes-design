from typing import Optional

from api.auth.security import verify_password
from api.db.base import AsyncSessionLocal, engine
from api.db.models import Design, Material, Role, Template, User, UserRole
from sqlalchemy import select
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin import I18nConfig
from starlette_admin.auth import AdminConfig, AdminUser, AuthProvider
from starlette_admin.contrib.sqlmodel import Admin, ModelView
from starlette_admin.exceptions import FormValidationError, LoginFailed


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
            result = await session.execute(select(User).where(User.username == username))
            user = result.scalar_one_or_none()

            if not user or not verify_password(password, user.password_hash):
                raise LoginFailed("Invalid username or password")

            roles_result = await session.execute(
                select(Role)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(UserRole.user_id == user.id)
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
            result = await session.execute(select(User).where(User.id == user_id))
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
    admin.add_view(ModelView(Template, icon="fa fa-shapes"))

    return admin
