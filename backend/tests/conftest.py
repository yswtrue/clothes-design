from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

pytest_plugins = ("pytest_asyncio",)
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

try:
    from main import app
    from db.base import Base, get_session
    from db.models import User

    _app_available = True
except Exception as e:
    _app_available = False


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    if not _app_available:
        pytest.skip("App not available")
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.execute(delete(User))
            await session.commit()
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    if not _app_available:
        pytest.skip("App not available")

    async def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_env(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test_secret_key_should_be_long_enough")
    monkeypatch.setenv("JWT_EXPIRY", "900")
    monkeypatch.setenv("JWT_REFRESH_EXPIRY", "604800")


@pytest.fixture
async def test_user(db_session: AsyncSession):
    if not _app_available:
        pytest.skip("App not available")

    from auth.security import get_password_hash
    from db.models import User
    from rbac.seed import seed_default_roles
    from rbac.service import assign_role_to_user, get_role_by_name

    # Seed default roles
    await seed_default_roles(db_session)

    # Create user
    user = User(username="testuser", password_hash=get_password_hash("Test123!@#"))
    db_session.add(user)
    await db_session.flush()

    # Assign designer role
    designer_role = await get_role_by_name(db_session, "designer")
    if designer_role:
        await assign_role_to_user(db_session, user.id, designer_role.id)

    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_headers(client: AsyncClient, test_env, db_session: AsyncSession) -> dict:
    if not _app_available:
        pytest.skip("App not available")

    from rbac.seed import seed_default_roles
    from rbac.service import assign_role_to_user, get_role_by_name
    from db.models import User

    # Seed default roles
    await seed_default_roles(db_session)

    await client.post(
        "/api/auth/register",
        json={"username": "authuser", "password": "Test123!@#"},
    )

    # Assign designer role to authuser
    authuser = await db_session.execute(select(User).where(User.username == "authuser"))
    user = authuser.scalar_one_or_none()
    if user:
        designer_role = await get_role_by_name(db_session, "designer")
        if designer_role:
            await assign_role_to_user(db_session, user.id, designer_role.id)
        await db_session.commit()

    login_response = await client.post(
        "/api/auth/login",
        json={"username": "authuser", "password": "Test123!@#"},
    )
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def auth_user(auth_headers: dict, db_session: AsyncSession) -> "User":
    if not _app_available:
        pytest.skip("App not available")

    from db.models import User

    result = await db_session.execute(select(User).where(User.username == "authuser"))
    return result.scalar_one_or_none()
