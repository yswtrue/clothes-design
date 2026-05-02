import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import PromptTemplate

DEFAULT_TEMPLATES = [
    {
        "name": "默认文生图模板",
        "task_type": "text2img",
        "provider_type": None,
        "template": "{style_description}. {pattern_type} pattern design. Color palette: {color_palette}. High quality, detailed, professional textile design for fabric printing.",
        "description": "通用文生图模板，适用于所有 Provider",
        "is_default": 1,
        "is_active": 1,
    },
    {
        "name": "默认图生图模板",
        "task_type": "img2img",
        "provider_type": None,
        "template": "Based on this fabric photo, enhance and refine the design. Make the image clearer with smoother, more fluid lines. Preserve the original style and color palette ({color_palette}). Create a clean, production-ready {pattern_type} textile pattern. {style_description}.",
        "description": "通用图生图模板，强调清晰化和线条流畅",
        "is_default": 1,
        "is_active": 1,
    },
    {
        "name": "GPTProto 图生图模板",
        "task_type": "img2img",
        "provider_type": "openai_image_edit",
        "template": "Enhance this fabric design image. Clean up and refine all lines to be smoother and more precise. Improve clarity and sharpness while maintaining the original {pattern_type} pattern style. Keep the color palette: {color_palette}. Output a production-ready textile design. {style_description}.",
        "description": "针对图片编辑模型优化的图生图模板",
        "is_default": 1,
        "is_active": 1,
    },
    {
        "name": "布料图案还原模板",
        "task_type": "img2img",
        "provider_type": None,
        "template": """Reconstruct the original flat pattern design from this fabric photo.

Requirements:
1. Remove all fabric textures (weave, knit, material grain)
2. Ignore surface occlusions (wrinkles, shadows, overlays, dust, loose threads)
3. Complete missing or obscured pattern areas, maintaining style consistency
4. Output a clean, flat vector-style pattern with crisp edges and solid colors

Style: {style_description}
Colors: {color_palette}
Output: {width}x{height} pixels, {pattern_type} pattern""",
        "description": "从布料照片还原原始平面图案，去除布纹和遮挡物，补全缺失部分",
        "is_default": 0,
        "is_active": 1,
    },
    {
        "name": "默认图像分析模板",
        "task_type": "analyze",
        "provider_type": None,
        "template": """Analyze this clothing design image and provide a detailed style analysis in JSON format.

Return ONLY valid JSON with these exact fields:
{
  "style_description": "A concise natural language description of the design style",
  "color_palette": ["#HEX1", "#HEX2", "#HEX3"],
  "pattern_type": "seamless|standalone|full",
  "suggested_params": {
    "tiling": "tile|clamp|reflect|wrap",
    "scale": 0.5-2.0
  }
}

Pattern types:
- seamless: Repeating pattern with no visible seams (suitable for tiling)
- standalone: Single design element on a background
- full: Full-coverage design that fills the entire area

Extract 3-5 dominant colors as hex codes. Suggest optimal tiling mode and scale.""",
        "description": "图像风格分析模板，用于 GPT-4V 分析服装图案",
        "is_default": 1,
        "is_active": 1,
    },
]


async def seed_prompt_templates(session: AsyncSession) -> None:
    logger = logging.getLogger(__name__)
    try:
        logger.info("Starting prompt template seeding...")
        
        added_count = 0
        for template_data in DEFAULT_TEMPLATES:
            result = await session.execute(
                select(PromptTemplate).where(PromptTemplate.name == template_data["name"])
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                logger.debug("Template '%s' already exists, skipping", template_data["name"])
                continue
            
            template = PromptTemplate(**template_data)
            session.add(template)
            logger.info("Added prompt template: %s", template_data["name"])
            added_count += 1
        
        if added_count > 0:
            await session.flush()
        
        result = await session.execute(select(PromptTemplate))
        count = len(result.scalars().all())
        logger.info("✅ Prompt templates seeded. Added: %s, Total: %s", added_count, count)
        
    except Exception as exc:
        logger.error("❌ Prompt template seeding failed: %s", exc, exc_info=True)
        raise
