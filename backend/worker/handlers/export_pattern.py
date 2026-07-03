import io
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col
from starlette.datastructures import UploadFile

from api.storage.converter import ColorSpace, png_to_tif
from api.storage.storages import (
    generated_image_storage,
    output_tif_storage,
    upscaled_storage,
    vector_storage,
)
from config import get_settings
from shared.ai.base import AIProvider
from shared.ai.exceptions import AIProviderError
from shared.ai.factory import Capability, get_provider_by_capability
from shared.task_queue import release_export_slot

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)

ExportFormat = Literal["svg", "tif"]


@dataclass(frozen=True)
class ExportContext:
    image_filename: str
    existing_vector_path: str | None
    existing_tif_path: str | None
    existing_upscaled_path: str | None


@dataclass(frozen=True)
class UpscaledImage:
    data: bytes
    filename: str
    original_size: int


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
                select(GeneratedDesign).where(col(GeneratedDesign.id) == generated_design_id)
            )
            record = result.scalar_one_or_none()
            if record:
                record.status = status
                await session.commit()
                self.logger.info(
                    f"Updated GeneratedDesign {generated_design_id} status to '{status}'"
                )

    async def _save_upscaled_path(self, generated_design_id: int, upscaled_filename: str) -> None:
        from sqlalchemy import text

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            await session.execute(
                text("UPDATE generated_designs SET upscaled_path = :path WHERE id = :id"),
                {"path": upscaled_filename, "id": generated_design_id},
            )
            await session.commit()

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        if "generated_design_id" not in task_data:
            raise WorkerError("Missing required field: generated_design_id")

        target_resolution = task_data.get("target_resolution", 12000)
        if not isinstance(target_resolution, int) or not 1024 <= target_resolution <= 16384:
            raise WorkerError(f"Invalid target_resolution: {target_resolution}")

        color_space = task_data.get("color_space", "CMYK")
        if color_space not in ("CMYK", "RGB"):
            raise WorkerError(f"Invalid color_space: {color_space}")

        export_format = task_data.get("format", "svg")
        if export_format not in ("svg", "tif"):
            raise WorkerError(f"Invalid format: {export_format}")

    async def _load_export_context(self, generated_design_id: int) -> ExportContext:
        from api.db.models import GeneratedDesign

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(GeneratedDesign).where(col(GeneratedDesign.id) == generated_design_id)
            )
            record = result.scalar_one_or_none()
            if not record:
                raise WorkerError(f"GeneratedDesign {generated_design_id} not found")
            if not record.image:
                raise WorkerError(f"GeneratedDesign {generated_design_id} has no image")

            image_filename = _get_file_path(record.image)
            if not image_filename:
                raise WorkerError(f"GeneratedDesign {generated_design_id} has no image path")

            return ExportContext(
                image_filename=image_filename,
                existing_vector_path=_get_file_path(record.vector_svg),
                existing_tif_path=_get_file_path(record.export_tif),
                existing_upscaled_path=_get_file_path(record.upscaled_image),
            )

    def _existing_export_response(
        self,
        generated_design_id: int,
        target_resolution: int,
        export_format: ExportFormat,
        context: ExportContext,
    ) -> dict[str, Any] | None:
        if export_format == "svg" and context.existing_vector_path and context.existing_upscaled_path:
            self.logger.info(f"Reusing existing SVG export: {context.existing_vector_path}")
            return {
                "download_url": vector_storage.get_url(context.existing_vector_path),
                "generated_design_id": generated_design_id,
                "resolution": target_resolution,
                "format": "svg",
                "upscaled_url": upscaled_storage.get_url(context.existing_upscaled_path),
                "reused": True,
            }

        if export_format == "tif" and context.existing_tif_path and context.existing_upscaled_path:
            self.logger.info(f"Reusing existing TIF export: {context.existing_tif_path}")
            return {
                "download_url": output_tif_storage.get_url(context.existing_tif_path),
                "generated_design_id": generated_design_id,
                "resolution": target_resolution,
                "format": "tif",
                "upscaled_url": upscaled_storage.get_url(context.existing_upscaled_path),
                "reused": True,
            }

        return None

    async def _prepare_upscaled_image(
        self,
        generated_design_id: int,
        target_resolution: int,
        context: ExportContext,
        content_type: str = "pattern",
        sharpen: bool = False,
    ) -> UpscaledImage:
        pattern_bytes = await generated_image_storage.download(context.image_filename)
        original_size = Image.open(io.BytesIO(pattern_bytes)).size[0]

        if context.existing_upscaled_path:
            self.logger.info(f"Reusing existing upscaled image: {context.existing_upscaled_path}")
            upscaled_bytes = await upscaled_storage.download(context.existing_upscaled_path)
            return UpscaledImage(
                data=upscaled_bytes,
                filename=context.existing_upscaled_path,
                original_size=original_size,
            )

        self.logger.info(f"Downloading pattern: {context.image_filename}")
        upscaler = await self._get_upscaler()
        self.logger.info(f"Upscaling pattern to {target_resolution}px")

        # Pre-resize if image exceeds GPU memory limits
        GPU_SAFE_PIXELS = 2_000_000  # Replicate ESRGAN GPU limit ≈ 2,096,704
        img = Image.open(io.BytesIO(pattern_bytes))
        w, h = img.size
        if w * h > GPU_SAFE_PIXELS:
            ratio = (GPU_SAFE_PIXELS / (w * h)) ** 0.5
            new_w = int(w * ratio)
            new_h = int(h * ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            pattern_bytes = buf.getvalue()
            original_size = max(new_w, new_h)
            self.logger.info(
                f"Pre-resized for GPU: {w}×{h} → {new_w}×{new_h} "
                f"({w * h:,} → {new_w * new_h:,} pixels)"
            )

        try:
            upscaled_bytes = await upscaler.upscale_image(pattern_bytes, target_resolution, content_type=content_type, sharpen=sharpen)
        except AIProviderError as e:
            self.logger.error(
                f"Upscale failed, reverting status to completed: {e}", exc_info=True
            )
            await self._update_status(generated_design_id, "completed")
            raise WorkerError(f"Upscale failed: {e}") from e

        self.logger.info(f"Upscaled: {len(pattern_bytes)} → {len(upscaled_bytes)} bytes")
        upscaled_filename = f"gen_{generated_design_id}_{uuid.uuid4().hex[:8]}_upscaled.png"
        await upscaled_storage.upload(upscaled_bytes, upscaled_filename)
        self.logger.info(f"Saved upscaled image: {upscaled_filename}")
        await self._save_upscaled_path(generated_design_id, upscaled_filename)
        return UpscaledImage(
            data=upscaled_bytes,
            filename=upscaled_filename,
            original_size=original_size,
        )

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        generated_design_id = task_data["generated_design_id"]
        target_resolution = task_data.get("target_resolution", 12000)
        color_space: ColorSpace = task_data.get("color_space", "CMYK")
        export_format: ExportFormat = task_data.get("format", "svg")
        content_type = task_data.get("content_type", "pattern")
        sharpen = task_data.get("sharpen", False)

        try:
            context = await self._load_export_context(generated_design_id)
            existing_export = self._existing_export_response(
                generated_design_id,
                target_resolution,
                export_format,
                context,
            )
            if existing_export:
                return existing_export

            await self._update_status(generated_design_id, "exporting")
            upscaled = await self._prepare_upscaled_image(
                generated_design_id,
                target_resolution,
                context,
                content_type=content_type,
                sharpen=sharpen,
            )

            upscaled_size = Image.open(io.BytesIO(upscaled.data)).size[0]
            export_dpi = 300
            self.logger.info(
                f"Export: {upscaled.original_size}px -> {upscaled_size}px, DPI={export_dpi}"
            )

            if export_format == "svg":
                return await self._export_svg(
                    generated_design_id,
                    upscaled.data,
                    upscaled.filename,
                    target_resolution,
                    color_space,
                )

            return await self._export_tif(
                generated_design_id,
                upscaled.data,
                upscaled.filename,
                target_resolution,
                color_space,
                export_dpi,
            )

        except WorkerError:
            raise
        except Exception as e:
            self.logger.error(f"Export failed: {e}", exc_info=True)
            await self._update_status(generated_design_id, "completed")
            raise WorkerError(f"Export processing failed: {e}") from e
        finally:
            await release_export_slot()

    async def _export_svg(
        self,
        generated_design_id: int,
        upscaled_bytes: bytes,
        upscaled_filename: str,
        target_resolution: int,
        color_space: str,
    ) -> dict[str, Any]:
        from api.db.models import GeneratedDesign

        self.logger.info("Vectorizing to SVG")
        vectorizer = await self._get_vectorizer()
        svg_bytes = await vectorizer.vectorize(upscaled_bytes, color_space)
        self.logger.info(f"Vectorized: {len(svg_bytes)} bytes")

        unique_id = uuid.uuid4().hex[:8]
        svg_filename = f"gen_{generated_design_id}_{unique_id}.svg"

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(GeneratedDesign).where(col(GeneratedDesign.id) == generated_design_id)
            )
            record = result.scalar_one_or_none()
            if record:
                record.status = "exported"
                record.vector_svg = make_upload_file(svg_bytes, svg_filename)
                record.exported_at = datetime.utcnow()
                await session.commit()

        upscaled_url = upscaled_storage.get_url(upscaled_filename)
        svg_url = vector_storage.get_url(svg_filename)

        self.logger.info(f"SVG export complete: {svg_url}")

        return {
            "download_url": svg_url,
            "generated_design_id": generated_design_id,
            "resolution": target_resolution,
            "format": "svg",
            "file_size": len(svg_bytes),
            "upscaled_url": upscaled_url,
        }

    async def _export_tif(
        self,
        generated_design_id: int,
        upscaled_bytes: bytes,
        upscaled_filename: str,
        target_resolution: int,
        color_space: ColorSpace,
        dpi: int = 300,
    ) -> dict[str, Any]:
        from api.db.models import GeneratedDesign

        self.logger.info(f"Converting to TIF ({color_space}, {dpi} DPI)")
        tif_bytes = png_to_tif(upscaled_bytes, color_space=color_space, dpi=dpi)
        self.logger.info(f"Converted to TIF: {len(tif_bytes)} bytes")

        unique_id = uuid.uuid4().hex[:8]
        tif_filename = f"gen_{generated_design_id}_{unique_id}_{color_space}.tif"

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(GeneratedDesign).where(col(GeneratedDesign.id) == generated_design_id)
            )
            record = result.scalar_one_or_none()
            if record:
                record.status = "exported"
                record.export_tif = make_upload_file(tif_bytes, tif_filename)
                record.exported_at = datetime.utcnow()
                await session.commit()

        upscaled_url = upscaled_storage.get_url(upscaled_filename)
        tif_url = output_tif_storage.get_url(tif_filename)

        self.logger.info(f"TIF export complete: {tif_url}")

        return {
            "download_url": tif_url,
            "generated_design_id": generated_design_id,
            "resolution": target_resolution,
            "format": "tif",
            "file_size": len(tif_bytes),
            "upscaled_url": upscaled_url,
        }


__all__ = ["ExportPatternHandler"]
