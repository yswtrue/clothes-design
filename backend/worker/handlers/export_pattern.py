import io
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.datastructures import UploadFile

from config import get_settings
from shared.ai.base import AIProvider
from shared.ai.factory import Capability, get_provider_by_capability
from shared.task_queue import release_export_slot
from api.storage.storages import generated_image_storage, upscaled_storage, vector_storage

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)


def make_upload_file(data: bytes, filename: str) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=filename)


def _get_file_path(file_obj) -> str | None:
    if file_obj is None:
        return None
    if hasattr(file_obj, "path"):
        return file_obj.path
    if isinstance(file_obj, str):
        return file_obj
    return str(file_obj) if file_obj else None


class ExportPatternHandler(TaskHandler):
    handler_name = "export_pattern"

    def __init__(self) -> None:
        super().__init__()
        self.upscaler: AIProvider | None = None
        self.vectorizer: AIProvider | None = None
        self._session_factory: async_sessionmaker | None = None

    async def _get_session_factory(self) -> async_sessionmaker:
        if self._session_factory is None:
            settings = get_settings()
            engine = create_async_engine(settings.database.async_url, echo=False)
            self._session_factory = async_sessionmaker(engine, expire_on_commit=False)
        return self._session_factory

    async def _get_upscaler(self) -> AIProvider:
        if self.upscaler is None:
            result = await get_provider_by_capability(Capability.UPSCALE)
            if result is None:
                raise WorkerError("No active upscale provider configured")
            self.upscaler, _ = result
        return self.upscaler

    async def _get_vectorizer(self) -> AIProvider:
        if self.vectorizer is None:
            result = await get_provider_by_capability(Capability.VECTORIZE)
            if result is None:
                raise WorkerError("No active vectorizer provider configured")
            self.vectorizer, _ = result
        return self.vectorizer

    async def _update_status(self, generated_design_id: int, status: str) -> None:
        from api.db.models import GeneratedDesign

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(GeneratedDesign).where(GeneratedDesign.id == generated_design_id)
            )
            record = result.scalar_one_or_none()
            if record:
                record.status = status
                await session.commit()
                self.logger.info(f"Updated GeneratedDesign {generated_design_id} status to '{status}'")

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        if "generated_design_id" not in task_data:
            raise WorkerError("Missing required field: generated_design_id")

        target_resolution = task_data.get("target_resolution", 12000)
        if not isinstance(target_resolution, int) or not 1024 <= target_resolution <= 16384:
            raise WorkerError(f"Invalid target_resolution: {target_resolution}")

        color_space = task_data.get("color_space", "CMYK")
        if color_space not in ("CMYK", "RGB"):
            raise WorkerError(f"Invalid color_space: {color_space}")

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        generated_design_id = task_data["generated_design_id"]
        target_resolution = task_data.get("target_resolution", 12000)
        color_space = task_data.get("color_space", "CMYK")

        from api.db.models import GeneratedDesign

        try:
            session_factory = await self._get_session_factory()
            async with session_factory() as session:
                result = await session.execute(
                    select(GeneratedDesign).where(GeneratedDesign.id == generated_design_id)
                )
                record = result.scalar_one_or_none()
                if not record:
                    raise WorkerError(f"GeneratedDesign {generated_design_id} not found")
                if not record.image:
                    raise WorkerError(f"GeneratedDesign {generated_design_id} has no image")

                existing_vector_path = _get_file_path(record.vector_svg)
                existing_upscaled_path = _get_file_path(record.upscaled_image)
                image_filename = _get_file_path(record.image)

            if existing_vector_path and existing_upscaled_path:
                self.logger.info(f"Reusing existing export: {existing_vector_path}")
                return {
                    "download_url": vector_storage.get_url(existing_vector_path),
                    "generated_design_id": generated_design_id,
                    "resolution": target_resolution,
                    "format": "svg",
                    "upscaled_url": upscaled_storage.get_url(existing_upscaled_path),
                    "reused": True,
                }

            await self._update_status(generated_design_id, "exporting")

            if existing_upscaled_path:
                self.logger.info(f"Reusing existing upscaled image: {existing_upscaled_path}")
                upscaled_bytes = await upscaled_storage.download(existing_upscaled_path)
                upscaled_filename = existing_upscaled_path
            else:
                self.logger.info(f"Downloading pattern: {image_filename}")
                pattern_bytes = await generated_image_storage.download(image_filename)

                upscaler = await self._get_upscaler()
                self.logger.info(f"Upscaling pattern to {target_resolution}px")
                upscaled_bytes = await upscaler.upscale_image(pattern_bytes, target_resolution)
                self.logger.info(f"Upscaled: {len(pattern_bytes)} → {len(upscaled_bytes)} bytes")

                unique_id = uuid.uuid4().hex[:8]
                upscaled_filename = f"gen_{generated_design_id}_{unique_id}_upscaled.png"

            self.logger.info("Vectorizing to SVG")
            vectorizer = await self._get_vectorizer()
            svg_bytes = await vectorizer.vectorize(upscaled_bytes, color_space)
            self.logger.info(f"Vectorized: {len(svg_bytes)} bytes")

            unique_id = uuid.uuid4().hex[:8]
            svg_filename = f"gen_{generated_design_id}_{unique_id}.svg"

            session_factory = await self._get_session_factory()
            async with session_factory() as session:
                result = await session.execute(
                    select(GeneratedDesign).where(GeneratedDesign.id == generated_design_id)
                )
                record = result.scalar_one_or_none()
                if record:
                    record.status = "exported"
                    if not existing_upscaled_path:
                        record.upscaled_image = make_upload_file(upscaled_bytes, upscaled_filename)
                    record.vector_svg = make_upload_file(svg_bytes, svg_filename)
                    record.exported_at = datetime.utcnow()
                    await session.commit()

            upscaled_url = upscaled_storage.get_url(upscaled_filename)
            svg_url = vector_storage.get_url(svg_filename)

            self.logger.info(f"Export complete: {svg_url}")

            return {
                "download_url": svg_url,
                "generated_design_id": generated_design_id,
                "resolution": target_resolution,
                "format": "svg",
                "file_size": len(svg_bytes),
                "upscaled_url": upscaled_url,
            }

        except WorkerError:
            raise
        except Exception as e:
            self.logger.error(f"Export failed: {e}", exc_info=True)
            await self._update_status(generated_design_id, "completed")
            raise WorkerError(f"Export processing failed: {e}") from e
        finally:
            await release_export_slot()


__all__ = ["ExportPatternHandler"]
