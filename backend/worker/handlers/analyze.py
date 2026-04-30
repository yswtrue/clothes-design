import base64
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import get_settings
from shared.ai.exceptions import (
    ProviderConfigurationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from shared.providers.config_loader import get_provider_config
from shared.providers.gpt4v import GPT4VProvider, GPT4VProviderError

from .base import TaskHandler, WorkerError


class AnalyzeHandler(TaskHandler):
    handler_name = "analyze"

    def __init__(self) -> None:
        super().__init__()
        self.provider: GPT4VProvider | None = None
        self.db_session: AsyncSession | None = None

    async def _get_db_session(self) -> AsyncSession:
        if self.db_session is None:
            settings = get_settings()
            engine = create_async_engine(settings.database.async_url, echo=False)
            async_session_factory = async_sessionmaker(engine, expire_on_commit=False)
            self.db_session = async_session_factory()
        return self.db_session

    async def _get_provider(self) -> GPT4VProvider:
        if self.provider is not None:
            return self.provider

        config = await get_provider_config("openai")
        if config:
            self.provider = GPT4VProvider.from_config(config)
            self.logger.info(f"Using DB config: {config.base_url}, model={config.model_name}")
        else:
            self.provider = GPT4VProvider()
            self.logger.info("Using env config for OpenAI")

        return self.provider

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        if "image_data" not in task_data:
            raise WorkerError("Missing required field: image_data")

        if "material_id" not in task_data:
            raise WorkerError("Missing required field: material_id")

        if not isinstance(task_data["image_data"], (bytes, str)):
            raise WorkerError("image_data must be bytes or base64 string")

        if isinstance(task_data["image_data"], str) and not task_data["image_data"]:
            raise WorkerError("image_data cannot be empty string")

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        material_id = task_data["material_id"]
        image_data = task_data["image_data"]

        if isinstance(image_data, str):
            try:
                image_data = base64.b64decode(image_data)
            except Exception as e:
                raise WorkerError(f"Invalid base64 image_data: {e}") from e

        try:
            provider = await self._get_provider()

            analysis = await provider.analyze_style(image_data)

            result = {
                "status": "success",
                "style_description": analysis.style_description,
                "color_palette": analysis.color_palette,
                "pattern_type": analysis.pattern_type,
                "suggested_params": analysis.suggested_params,
            }

            session = await self._get_db_session()

            from api.db.models import Material

            stmt = (
                update(Material)
                .where(Material.id == material_id)
                .values(
                    meta={
                        "style_analysis": {
                            "style_description": analysis.style_description,
                            "color_palette": analysis.color_palette,
                            "pattern_type": analysis.pattern_type,
                            "suggested_params": analysis.suggested_params,
                        }
                    }
                )
            )
            await session.execute(stmt)
            await session.commit()

            return result

        except ProviderConfigurationError as e:
            self.logger.error(f"Provider configuration error: {e}")
            raise WorkerError(f"AI provider not configured: {e}") from e

        except ProviderTimeoutError as e:
            self.logger.warning(f"Provider timeout: {e}")
            raise WorkerError(f"Analysis timed out: {e}") from e

        except ProviderRateLimitError as e:
            self.logger.warning(f"Rate limit hit: {e}")
            raise WorkerError(f"Rate limited: {e}") from e

        except GPT4VProviderError as e:
            self.logger.error(f"GPT-4V error: {e}")
            raise WorkerError(f"Analysis failed: {e}") from e

        except Exception as e:
            self.logger.exception("Unexpected error during analysis")
            raise WorkerError(f"Unexpected error: {e}") from e

        finally:
            if self.db_session:
                await self.db_session.close()
