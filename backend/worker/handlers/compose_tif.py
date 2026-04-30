import io
import logging
import struct
from typing import Any

from PIL import Image

from api.storage.storages import generated_image_storage, output_tif_storage, prj_storage

from .base import TaskHandler, WorkerError

logger = logging.getLogger(__name__)


class PrjParser:
    HEADER_MAGIC = b'\x51\x7f\x01\x01'

    def __init__(self, prj_data: bytes):
        self.data = prj_data
        self.pieces: list[dict] = []

    def parse(self) -> dict:
        if not self.data.startswith(self.HEADER_MAGIC):
            raise WorkerError("Invalid PRJ file format")

        design_id = self._extract_design_id()
        self._extract_pattern_pieces()

        return {
            "design_id": design_id,
            "pieces": self.pieces,
            "total_pieces": len(self.pieces),
        }

    def _extract_design_id(self) -> str:
        start = self.data.find(b'D')
        if start == -1:
            return "unknown"

        end = self.data.find(b'\x00', start)
        if end == -1 or end - start > 50:
            end = start + 20

        try:
            return self.data[start:end].decode('ascii').rstrip('\x00')
        except Exception:
            return "unknown"

    def _extract_pattern_pieces(self) -> None:
        design_id_bytes = self._extract_design_id().encode('ascii')

        pos = 0
        piece_count = 0
        while True:
            pos = self.data.find(design_id_bytes, pos)
            if pos == -1:
                break

            piece_data = self.data[pos:pos+200]
            piece_name = self._extract_piece_name(piece_data, len(design_id_bytes))

            if piece_name and piece_name not in [p.get("name") for p in self.pieces]:
                has_fabric = b'\xc3\xe6\xc1\xcf' in piece_data
                self.pieces.append({
                    "id": piece_count,
                    "name": piece_name,
                    "has_fabric": has_fabric,
                    "offset": pos,
                })
                piece_count += 1

            pos += len(design_id_bytes)

    def _extract_piece_name(self, data: bytes, skip: int) -> str | None:
        i = skip
        while i < len(data) - 1:
            if 0xA1 <= data[i] <= 0xF7 and 0xA1 <= data[i+1] <= 0xFE:
                break
            i += 1

        if i >= len(data) - 1:
            return None

        name_start = i
        name_end = i
        while name_end < len(data) - 1:
            if 0xA1 <= data[name_end] <= 0xF7 and 0xA1 <= data[name_end+1] <= 0xFE:
                name_end += 2
            else:
                break

        try:
            return data[name_start:name_end].decode('gb2312')
        except Exception:
            return None


class ComposeTifHandler(TaskHandler):
    handler_name = "compose_tif"

    def __init__(self) -> None:
        super().__init__()

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        required_fields = ["design_id", "fabric_image_path", "prj_path"]
        for field in required_fields:
            if field not in task_data:
                raise WorkerError(f"Missing required field: {field}")

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        design_id = task_data["design_id"]
        fabric_image_path = task_data["fabric_image_path"]
        prj_path = task_data["prj_path"]
        regions = task_data.get("regions")

        self.logger.info(f"Loading fabric image from {fabric_image_path}")
        fabric_bytes = await generated_image_storage.download(fabric_image_path)
        fabric_image = Image.open(io.BytesIO(fabric_bytes))

        if fabric_image.mode != 'RGB':
            fabric_image = fabric_image.convert('RGB')

        self.logger.info(f"Loading PRJ template from {prj_path}")
        try:
            prj_bytes = await prj_storage.download(prj_path)
        except Exception as e:
            self.logger.warning(f"Could not load PRJ from storage: {e}")
            try:
                with open(prj_path, 'rb') as f:
                    prj_bytes = f.read()
            except Exception as e2:
                raise WorkerError(f"Failed to load PRJ file: {e2}")

        parser = PrjParser(prj_bytes)
        prj_info = parser.parse()

        self.logger.info(
            f"PRJ parsed: {prj_info['total_pieces']} pieces found"
        )

        output_width = 4096
        output_height = 4096
        output_image = Image.new('CMYK', (output_width, output_height), (0, 0, 0, 0))

        fabric_resized = fabric_image.resize((output_width, output_height), Image.LANCZOS)

        if fabric_resized.mode == 'RGB':
            r, g, b = fabric_resized.split()
            c = Image.eval(r, lambda x: 255 - x)
            m = Image.eval(g, lambda x: 255 - x)
            y = Image.eval(b, lambda x: 255 - x)
            k = Image.new('L', fabric_resized.size, 0)
            fabric_cmyk = Image.merge('CMYK', (c, m, y, k))
        else:
            fabric_cmyk = fabric_resized.convert('CMYK')

        output_image.paste(fabric_cmyk, (0, 0))

        output_buffer = io.BytesIO()
        output_image.save(
            output_buffer,
            format='TIFF',
            compression='lzw',
            resolution=300,
            resolution_unit=2,
        )
        output_buffer.seek(0)

        output_filename = f"design-{design_id}-composed.tif"
        download_url = await output_tif_storage.upload(output_buffer.getvalue(), output_filename)

        self.logger.info(f"TIF export complete: {download_url}")

        return {
            "status": "success",
            "design_id": design_id,
            "download_url": download_url,
            "prj_info": {
                "design_id": prj_info["design_id"],
                "total_pieces": prj_info["total_pieces"],
                "piece_names": [p["name"] for p in prj_info["pieces"]],
            },
            "output": {
                "format": "tif",
                "color_space": "CMYK",
                "width": output_width,
                "height": output_height,
                "resolution_dpi": 300,
            },
        }


__all__ = ["ComposeTifHandler"]
