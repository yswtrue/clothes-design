import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import get_settings
from shared.ai.base import AIProvider
from shared.ai.exceptions import (
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from shared.ai.schemas import GenerationParams, StyleAnalysis
from shared.providers.config_loader import get_provider_config
from shared.providers.gptproto import GPTProtoProvider
from shared.providers.openai_image import OpenAIImageProvider
from shared.providers.prompt_template_service import get_or_default_prompt
from shared.providers.replicate import ReplicateProvider
from shared.providers.vectorizer import VectorizerProvider

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)


class GenerateHandler(TaskHandler):
    handler_name = "generate"

    def __init__(self) -> None:
        super().__init__()
        self.provider: AIProvider | None = None
        self.img2img_provider: AIProvider | None = None
        self._session_factory: async_sessionmaker | None = None

    async def _get_session_factory(self) -> async_sessionmaker:
        if self._session_factory is None:
            settings = get_settings()
            engine = create_async_engine(settings.database.async_url, echo=False)
            self._session_factory = async_sessionmaker(engine, expire_on_commit=False)
        return self._session_factory

    async def _get_provider(self, for_img2img: bool = False) -> AIProvider:
        if for_img2img and self.img2img_provider is not None:
            return self.img2img_provider
        if not for_img2img and self.provider is not None:
            return self.provider

        if for_img2img:
            gptproto_config = await get_provider_config("gptproto")
            if gptproto_config:
                provider = GPTProtoProvider.from_config(gptproto_config)
                self.img2img_provider = provider
                self.logger.info(f"Using GPTProto provider for img2img: {gptproto_config.model_name}")
                return provider

        openai_config = await get_provider_config("openai_image")
        if openai_config:
            provider = OpenAIImageProvider.from_config(openai_config)
            self.logger.info(f"Using OpenAI image provider: {openai_config.model_name}")
        else:
            replicate_config = await get_provider_config("replicate")
            if replicate_config:
                provider = ReplicateProvider.from_config(replicate_config)
                self.logger.info("Using Replicate provider from config")
            else:
                provider = ReplicateProvider()
                self.logger.info("Using default Replicate provider")

        if for_img2img:
            self.img2img_provider = provider
        else:
            self.provider = provider

        return provider

    def _get_provider_type(self, provider: AIProvider) -> str | None:
        if isinstance(provider, GPTProtoProvider):
            return "gptproto"
        elif isinstance(provider, OpenAIImageProvider):
            return "openai_image"
        elif isinstance(provider, ReplicateProvider):
            return "replicate"
        return None

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        required_fields = ["style", "params"]
        for field in required_fields:
            if field not in task_data:
                raise WorkerError(f"Missing required field: {field}")

        try:
            StyleAnalysis(**task_data["style"])
        except Exception as e:
            raise WorkerError(f"Invalid style data: {e}")

        try:
            GenerationParams(**task_data["params"])
        except Exception as e:
            raise WorkerError(f"Invalid generation params: {e}")

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        style = StyleAnalysis(**task_data["style"])
        params = GenerationParams(**task_data["params"])
        design_id = task_data.get("design_id")
        generate_vector = task_data.get("generate_vector", False)

        try:
            is_img2img = bool(params.init_image_b64)
            task_type = "img2img" if is_img2img else "text2img"
            provider = await self._get_provider(for_img2img=is_img2img)

            provider_type = self._get_provider_type(provider)
            
            if params.prompt_override:
                prompt = params.prompt_override
                self.logger.info(f"Using custom prompt ({task_type}/{provider_type}): {prompt[:100]}...")
            else:
                prompt = await get_or_default_prompt(
                    task_type=task_type,
                    style=style,
                    params=params,
                    provider_type=provider_type,
                )
                params = params.model_copy(update={"prompt_override": prompt})
                self.logger.info(f"Using default prompt ({task_type}/{provider_type}): {prompt[:100]}...")

            image_bytes = await provider.generate_pattern(style, params)

            import base64

            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            self.logger.info(
                f"Pattern generated successfully: {params.width}x{params.height}, "
                f"tiling={params.tiling}, seed={params.seed}"
            )

            pattern_url = None
            vector_url = None
            if design_id:
                pattern_url = await self._save_and_update_design(design_id, image_bytes, params)

                if generate_vector:
                    vector_url = await self._vectorize_and_save(design_id, image_bytes)

            return {
                "status": "success",
                "image_data": image_b64,
                "pattern_url": pattern_url,
                "vector_url": vector_url,
                "width": params.width,
                "height": params.height,
                "tiling": params.tiling,
                "seed": params.seed,
            }

        except ProviderTimeoutError as e:
            self.logger.error(f"Generation timeout: {e}")
            return {"status": "error", "error": "Request timed out. Please retry."}

        except ProviderRateLimitError as e:
            self.logger.error(f"Rate limit exceeded: {e}")
            return {
                "status": "error",
                "error": "Rate limit exceeded. Please retry later.",
            }

        except ProviderError as e:
            self.logger.error(f"Provider error: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

        except Exception as e:
            self.logger.exception(f"Unexpected error during generation: {e}")
            raise WorkerError(f"Pattern generation failed: {e}")

    async def _save_and_update_design(
        self, design_id: int, image_bytes: bytes, params: GenerationParams
    ) -> str:
        from api.db.models import Design, DesignVersion
        from api.storage.storages import generated_image_storage

        unique_id = uuid.uuid4().hex[:8]
        filename = f"design_{design_id}_{unique_id}.png"
        pattern_url = await generated_image_storage.upload(image_bytes, filename)
        self.logger.info(f"Saved pattern image: {filename} -> {pattern_url}")

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            result = await session.execute(select(Design).where(Design.id == design_id))
            design = result.scalar_one_or_none()

            if design:
                design.status = "draft"

                version_result = await session.execute(
                    select(DesignVersion)
                    .where(DesignVersion.design_id == design_id)
                    .order_by(DesignVersion.version.desc())
                    .limit(1)
                )
                version = version_result.scalar_one_or_none()

                if version:
                    version_data = dict(version.data) if version.data else {}
                    version_data["pattern_url"] = pattern_url
                    version.data = version_data

                await session.commit()
                self.logger.info(f"Updated design {design_id} status to 'draft'")

        return pattern_url

    async def _vectorize_and_save(self, design_id: int, image_bytes: bytes) -> str | None:
        from api.storage.storages import output_tif_storage

        try:
            vectorizer = VectorizerProvider()
            svg_bytes = await vectorizer.vectorize(image_bytes)

            unique_id = uuid.uuid4().hex[:8]
            filename = f"design_{design_id}_{unique_id}.svg"
            vector_url = await output_tif_storage.upload(svg_bytes, filename)
            self.logger.info(f"Saved vector image: {filename} -> {vector_url}")
            return vector_url

        except Exception as e:
            self.logger.error(f"Vectorization failed: {e}")
            return None


__all__ = ["GenerateHandler"]
