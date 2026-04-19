"""Seed built-in garment templates."""

import asyncio
import os

from sqlalchemy import select

from api.db.base import AsyncSessionLocal
from api.db.models import Template

BUILT_IN_TEMPLATES = [
    {"name": "Classic T-Shirt", "category": "t-shirt", "image": "tshirt_classic.png"},
    {"name": "V-Neck T-Shirt", "category": "t-shirt", "image": "tshirt_vneck.png"},
    {"name": "Hoodie", "category": "hoodie", "image": "hoodie_classic.png"},
    {"name": "Zip Hoodie", "category": "hoodie", "image": "hoodie_zip.png"},
    {"name": "Tank Top", "category": "tank", "image": "tank_classic.png"},
    {"name": "Muscle Tee", "category": "tank", "image": "tank_muscle.png"},
    {"name": "Long Sleeve T-Shirt", "category": "long-sleeve", "image": "longsleeve_classic.png"},
    {"name": "Polo Shirt", "category": "polo", "image": "polo_classic.png"},
]


async def seed_templates():
    """Seed built-in templates if table is empty."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Template))
        existing = result.scalars().all()

        if len(existing) > 0:
            print(f"Templates already seeded ({len(existing)} templates exist)")
            return

        print("Seeding built-in templates...")
        templates_dir = os.path.join(os.path.dirname(__file__), "..", "static", "templates")
        os.makedirs(templates_dir, exist_ok=True)

        for t in BUILT_IN_TEMPLATES:
            template = Template(
                name=t["name"],
                image_path=f"/static/templates/{t['image']}",
                category=t["category"],
                is_builtin=1,
            )
            session.add(template)

        await session.commit()
        print(f"Seeded {len(BUILT_IN_TEMPLATES)} templates")


if __name__ == "__main__":
    asyncio.run(seed_templates())
