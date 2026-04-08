import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.security import get_password_hash
from db.models import Role, User
from rbac.service import assign_role_to_user

_TEST_USERS = [
    ("admin", "admin123", "admin"),
    ("designer", "designer123", "designer"),
    ("viewer", "viewer123", "viewer"),
]


async def seed_test_users(session: AsyncSession) -> None:
    logger = logging.getLogger(__name__)
    for username, password, role_name in _TEST_USERS:
        existing = await session.execute(select(User).where(User.username == username))
        if existing.scalar_one_or_none():
            logger.info("Test user %s already exists, skipping", username)
            continue
        user = User(username=username, password_hash=get_password_hash(password))
        session.add(user)
        await session.flush()
        role_result = await session.execute(select(Role).where(Role.name == role_name))
        role = role_result.scalar_one_or_none()
        if role:
            await assign_role_to_user(session, user_id=int(user.id), role_id=int(role.id))
            logger.info("Assigned role %s to %s", role_name, username)
        else:
            logger.warning("Role %s missing; user %s created without role", role_name, username)
    logger.info("✅ Test users seeding complete")
