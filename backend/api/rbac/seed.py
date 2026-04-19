import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Role
from api.rbac.service import create_role, get_role_by_name

DEFAULT_ROLES = {
    "admin": {
        "*": True,
    },
    "designer": {
        "designs.create": True,
        "designs.read": True,
        "designs.update": True,
        "designs.delete": True,
        "materials.create": True,
        "materials.read": True,
        "materials.delete": True,
    },
    "viewer": {
        "designs.read": True,
        "materials.read": True,
    },
}


async def seed_default_roles(session: AsyncSession) -> None:
    logger = logging.getLogger(__name__)
    try:
        logger.info("Starting role seeding...")
        existing_admin = await get_role_by_name(session, "admin")
        if existing_admin:
            logger.info("Roles already seeded, skipping")
            return
        for role_name, permissions in DEFAULT_ROLES.items():
            await create_role(session, role_name, permissions)
            logger.info("Added role: %s", role_name)
        await session.flush()
        result = await session.execute(select(func.count()).select_from(Role))
        count = result.scalar_one()
        logger.info("✅ Roles seeded successfully. Total roles: %s", count)
    except Exception as exc:
        logger.error("❌ Role seeding failed: %s", exc, exc_info=True)
        raise
