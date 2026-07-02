import io
import logging
import uuid
from datetime import datetime
from typing import Any

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import col

from api.storage.converter import ColorSpace, png_to_tif
from api.storage.storages import (
    material_storage,
    output_tif_storage,
    upscaled_storage,
)
from config import get_settings
from shared.ai.base import AIProvider
from shared.ai.exceptions import AIProviderError
from shared.ai.factory import Capability, get_provider_by_capability
from starlette.datastructures import UploadFile

from .base import TaskHandler, WorkerError
from .tile_upscale import tile_upscale

logger = logging.getLogger(__name__)


def _make_upload_file(data: bytes, filename: str) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename=filename)


class ExportMaterialHandler(TaskHandler):
    handler_name = "export_material"

    def __init__(self) -> None:
        super().__init__()
        self.upscaler: AIProvider | None = None
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

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        if "material_id" not in task_data:
            raise WorkerError("Missing required field: material_id")

        if "stored_filename" not in task_data:
            raise WorkerError("Missing required field: stored_filename")

        target_resolution = task_data.get("target_resolution", 12000)
        if not isinstance(target_resolution, int) or not 1024 <= target_resolution <= 16384:
            raise WorkerError(f"Invalid target_resolution: {target_resolution}")

        color_space = task_data.get("color_space", "CMYK")
        if color_space not in ("CMYK", "RGB"):
            raise WorkerError(f"Invalid color_space: {color_space}")

    async def _save_material_export(
        self,
        material_id: int,
        upscaled_filename: str,
        tif_filename: str,
    ) -> None:
        from api.db.models import Material

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(Material).where(col(Material.id) == material_id)
            )
            record = result.scalar_one_or_none()
            if record:
                record.upscaled_image = _make_upload_file(
                    await upscaled_storage.download(upscaled_filename),
                    upscaled_filename,
                )
                record.export_tif = _make_upload_file(
                    await output_tif_storage.download(tif_filename),
                    tif_filename,
                )
                record.exported_at = datetime.utcnow()
                await session.commit()
                self.logger.info(
                    f"Persisted export_tif and upscaled_image to Material {material_id}"
                )

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        material_id: int = task_data["material_id"]
        stored_filename: str = task_data["stored_filename"]
        target_resolution: int = task_data.get("target_resolution", 12000)
        color_space: ColorSpace = task_data.get("color_space", "CMYK")
        dpi: int = task_data.get("dpi", 300)

        try:
            self.logger.info(
                f"Exporting material {material_id}: {stored_filename} "
                f"(target: {target_resolution}px, {color_space}, {dpi} DPI)"
            )

            # Allow large images (Topaz output can exceed PIL default limit)
            Image.MAX_IMAGE_PIXELS = None

            # Step 1: Download original material image
            self.logger.info(f"Downloading material image: {stored_filename}")
            original_bytes = await material_storage.download(stored_filename)
            original_size = Image.open(io.BytesIO(original_bytes)).size[0]
            self.logger.info(f"Original image size: {original_size}px, {len(original_bytes)} bytes")

            # Step 2: AI upscale — tile for GPU-limited models, direct for Topaz
            upscaler = await self._get_upscaler()

            GPU_SAFE_PIXELS = 2_000_000  # All Replicate models: 2,096,704 pixel limit
            img = Image.open(io.BytesIO(original_bytes))
            w, h = img.size
            needs_tiling = (
                w * h > GPU_SAFE_PIXELS
                and "topaz" not in upscaler.__class__.__name__.lower()
            )

            if needs_tiling:
                self.logger.info(
                    f"Image too large for GPU ({w}×{h} = {w * h:,} px), "
                    f"using tiled upscaling (1024px tiles)"
                )
                upscaled_bytes = await tile_upscale(
                    original_bytes,
                    target_resolution,
                    lambda tile_bytes, tile_target: upscaler.upscale_image(tile_bytes, tile_target),
                )
            else:
                self.logger.info(f"Upscaling to {target_resolution}px via {upscaler.__class__.__name__}")
                try:
                    upscaled_bytes = await upscaler.upscale_image(original_bytes, target_resolution)
                except AIProviderError as e:
                    self.logger.error(f"Upscale failed: {e}", exc_info=True)
                    raise WorkerError(f"Upscale failed: {e}") from e

            upscaled_size = Image.open(io.BytesIO(upscaled_bytes)).size[0]
            self.logger.info(
                f"Upscaled: {original_size}px → {upscaled_size}px, "
                f"{len(original_bytes)} → {len(upscaled_bytes)} bytes"
            )

            # Save upscaled intermediate
            upscaled_filename = f"mat_{material_id}_{uuid.uuid4().hex[:8]}_upscaled.png"
            await upscaled_storage.upload(upscaled_bytes, upscaled_filename)
            self.logger.info(f"Saved upscaled image: {upscaled_filename}")

            # Step 3: Convert to TIF
            self.logger.info(f"Converting to TIF ({color_space}, {dpi} DPI)")
            tif_bytes = png_to_tif(upscaled_bytes, color_space=color_space, dpi=dpi)
            self.logger.info(f"Converted to TIF: {len(tif_bytes)} bytes")

            # Step 4: Save TIF
            unique_id = uuid.uuid4().hex[:8]
            tif_filename = f"mat_{material_id}_{unique_id}_{color_space}.tif"
            await output_tif_storage.upload(tif_bytes, tif_filename)

            # Step 5: Persist to Material record
            await self._save_material_export(material_id, upscaled_filename, tif_filename)

            tif_url = output_tif_storage.get_url(tif_filename)
            upscaled_url = upscaled_storage.get_url(upscaled_filename)

            self.logger.info(f"Material TIF export complete: {tif_url}")

            return {
                "download_url": tif_url,
                "material_id": material_id,
                "resolution": target_resolution,
                "format": "tif",
                "file_size": len(tif_bytes),
                "upscaled_url": upscaled_url,
                "original_size": original_size,
                "upscaled_size": upscaled_size,
            }

        except WorkerError:
            raise
        except Exception as e:
            self.logger.error(f"Material export failed: {e}", exc_info=True)
            raise WorkerError(f"Material export processing failed: {e}") from e


__all__ = ["ExportMaterialHandler"]

