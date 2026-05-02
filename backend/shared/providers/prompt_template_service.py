import logging
from dataclasses import dataclass

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from shared.ai.schemas import StyleAnalysis, GenerationParams
from shared.db import get_session_context

logger = logging.getLogger(__name__)


@dataclass
class RenderedPrompt:
    prompt: str
    template_id: int | None = None
    template_name: str | None = None


async def get_prompt_template(
    task_type: str,
    provider_type: str | None = None,
    session: AsyncSession | None = None,
) -> tuple[str | None, int | None, str | None]:
    from api.db.models import PromptTemplate

    async def _query(sess: AsyncSession) -> tuple[str | None, int | None, str | None]:
        conditions = [
            PromptTemplate.task_type == task_type,
            PromptTemplate.is_default == 1,
            PromptTemplate.is_active == 1,
        ]

        if provider_type:
            result = await sess.execute(
                select(PromptTemplate)
                .where(and_(*conditions, PromptTemplate.provider_type == provider_type))
                .limit(1)
            )
            template = result.scalar_one_or_none()

            if not template:
                result = await sess.execute(
                    select(PromptTemplate)
                    .where(and_(*conditions, PromptTemplate.provider_type == None))
                    .limit(1)
                )
                template = result.scalar_one_or_none()
        else:
            result = await sess.execute(
                select(PromptTemplate)
                .where(and_(*conditions))
                .order_by(PromptTemplate.provider_type.desc())
                .limit(1)
            )
            template = result.scalar_one_or_none()

        if template:
            return template.template, template.id, template.name
        return None, None, None

    if session is not None:
        return await _query(session)

    async with get_session_context() as sess:
        return await _query(sess)


def render_prompt(
    template: str,
    style: StyleAnalysis,
    params: GenerationParams,
) -> str:
    color_palette_str = ", ".join(style.color_palette[:5]) if style.color_palette else ""

    variables = {
        "style_description": style.style_description,
        "color_palette": color_palette_str,
        "pattern_type": style.pattern_type,
        "width": params.width,
        "height": params.height,
        "seed": params.seed,
        "tiling": params.tiling,
    }

    try:
        return template.format(**variables)
    except KeyError as e:
        logger.warning(f"Template variable not found: {e}, using partial render")
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result


async def get_rendered_prompt(
    task_type: str,
    style: StyleAnalysis,
    params: GenerationParams,
    provider_type: str | None = None,
    session: AsyncSession | None = None,
) -> RenderedPrompt | None:
    template, template_id, template_name = await get_prompt_template(
        task_type=task_type,
        provider_type=provider_type,
        session=session,
    )

    if not template:
        return None

    rendered = render_prompt(template, style, params)
    return RenderedPrompt(
        prompt=rendered,
        template_id=template_id,
        template_name=template_name,
    )


DEFAULT_TEXT2IMG_TEMPLATE = """{style_description}. {pattern_type} pattern design. Color palette: {color_palette}. High quality, detailed, professional textile design for fabric printing."""

DEFAULT_IMG2IMG_TEMPLATE = """Based on this fabric photo, enhance and refine the design. Make the image clearer with smoother, more fluid lines. Preserve the original style and color palette ({color_palette}). Create a clean, production-ready {pattern_type} textile pattern. {style_description}."""


async def get_or_default_prompt(
    task_type: str,
    style: StyleAnalysis,
    params: GenerationParams,
    provider_type: str | None = None,
) -> str:
    result = await get_rendered_prompt(
        task_type=task_type,
        style=style,
        params=params,
        provider_type=provider_type,
    )

    if result:
        logger.info(f"Using prompt template: {result.template_name} (id={result.template_id})")
        return result.prompt

    logger.info(f"No template found for {task_type}/{provider_type}, using default")
    default_template = DEFAULT_IMG2IMG_TEMPLATE if task_type == "img2img" else DEFAULT_TEXT2IMG_TEMPLATE
    return render_prompt(default_template, style, params)


async def get_analyze_prompt(provider_type: str | None = None) -> str | None:
    template, template_id, template_name = await get_prompt_template(
        task_type="analyze",
        provider_type=provider_type,
    )
    
    if template:
        logger.info(f"Using analyze template: {template_name} (id={template_id})")
        return template
    
    return None
