import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import PromptFeature

DEFAULT_PROMPT_FEATURES = [
    {
        "key": "preserve_style",
        "label": "保留素材风格",
        "description": "延续上传素材的核心视觉语言和图案气质",
        "prompt": "Preserve the original material style, visual language, motif structure, and overall design mood.",
        "sort_order": 10,
        "is_default": 1,
        "is_active": 1,
    },
    {
        "key": "seamless_repeat",
        "label": "无缝平铺",
        "description": "优化为可重复拼接的服装印花图案",
        "prompt": "Create a seamless repeat pattern suitable for textile printing, with clean tileable edges and balanced repetition.",
        "sort_order": 20,
        "is_default": 0,
        "is_active": 1,
    },
    {
        "key": "color_harmony",
        "label": "强化配色",
        "description": "根据素材色板提升颜色协调度和层次",
        "prompt": "Enhance color harmony using the material color palette, keeping the palette cohesive and production-friendly.",
        "sort_order": 30,
        "is_default": 0,
        "is_active": 1,
    },
    {
        "key": "print_ready",
        "label": "适合印刷",
        "description": "提升清晰度、边缘质量和商业落地效果",
        "prompt": "Make the artwork print-ready for apparel production, with crisp edges, clear shapes, and high-quality details.",
        "sort_order": 40,
        "is_default": 1,
        "is_active": 1,
    },
    {
        "key": "rich_details",
        "label": "增加细节",
        "description": "添加更丰富的纹理、装饰元素和视觉层次",
        "prompt": "Add refined decorative details, texture depth, and layered visual interest without making the design cluttered.",
        "sort_order": 50,
        "is_default": 0,
        "is_active": 1,
    },
    {
        "key": "clean_background",
        "label": "背景干净",
        "description": "减少杂乱背景, 让主体图案更突出",
        "prompt": "Keep the background clean and controlled so the main pattern elements remain clear and prominent.",
        "sort_order": 60,
        "is_default": 0,
        "is_active": 1,
    },
]


async def seed_prompt_features(session: AsyncSession) -> None:
    logger = logging.getLogger(__name__)
    try:
        logger.info("Starting prompt feature seeding...")

        added_count = 0
        for feature_data in DEFAULT_PROMPT_FEATURES:
            result = await session.execute(
                select(PromptFeature).where(PromptFeature.key == feature_data["key"])
            )
            existing = result.scalar_one_or_none()

            if existing:
                logger.debug("Prompt feature '%s' already exists, skipping", feature_data["key"])
                continue

            feature = PromptFeature(**feature_data)
            session.add(feature)
            logger.info("Added prompt feature: %s", feature_data["key"])
            added_count += 1

        if added_count > 0:
            await session.flush()

        result = await session.execute(select(PromptFeature))
        count = len(result.scalars().all())
        logger.info("✅ Prompt features seeded. Added: %s, Total: %s", added_count, count)

    except Exception as exc:
        logger.error("❌ Prompt feature seeding failed: %s", exc, exc_info=True)
        raise
