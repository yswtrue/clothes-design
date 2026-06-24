"""CLO3D render task handler — communicates with CLO3D HTTP API server.

Sends JSON requests to the CLO3D plugin's HTTP server (running inside CLO3D),
receives results synchronously (blocking until render completes).

Architecture:
    Worker Handler ──HTTP POST──▶ CLO3D API Server (inside CLO3D, port 9898)
         │                              │
         │◀───── JSON Response ─────────┘
         ▼
    Save rendered images to DB storage
"""

import asyncio
import base64
import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import get_settings

from .base import TaskHandler, WorkerError


class Clo3dRenderHandler(TaskHandler):
    """Handler for CLO3D render tasks via HTTP API."""

    handler_name = "clo3d_render"

    def __init__(self) -> None:
        super().__init__()
        self._session_factory: async_sessionmaker | None = None
        self._http: httpx.AsyncClient | None = None

    async def _get_session_factory(self) -> async_sessionmaker:
        if self._session_factory is None:
            settings = get_settings()
            engine = create_async_engine(settings.database.async_url, echo=False)
            self._session_factory = async_sessionmaker(engine, expire_on_commit=False)
        return self._session_factory

    @property
    def _api_url(self) -> str:
        return get_settings().clo3d.api_base_url.rstrip("/")

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self._api_url,
                timeout=httpx.Timeout(get_settings().clo3d.render_timeout_sec),
            )
        return self._http

    # ── Validation ─────────────────────────────────────────────────────────

    async def validate_input(self, task_data: dict[str, Any]) -> None:
        required = ["render_task_id", "project_id", "material_assignments"]
        for field in required:
            if field not in task_data:
                raise WorkerError(f"Missing required field: {field}")

        if not isinstance(task_data["material_assignments"], dict):
            raise WorkerError("material_assignments must be a dict")

    # ── Main Handler ───────────────────────────────────────────────────────

    async def handle(self, task_data: dict[str, Any]) -> dict[str, Any]:
        await self.validate_input(task_data)

        render_task_id = task_data["render_task_id"]
        project_id = task_data["project_id"]
        material_assignments: dict[str, int] = task_data["material_assignments"]

        # 1. Load project
        project = await self._load_project(project_id)
        if not project:
            raise WorkerError(f"Project {project_id} not found")

        prj_path = await self._resolve_prj_path(project)
        if not prj_path or not Path(prj_path).exists():
            raise WorkerError(f"PRJ file not accessible: {prj_path}")

        # 2. Output dir for render results (shared with CLO3D)
        output_dir = (
            Path(get_settings().storage.local_storage_path)
            / "clo3d_output"
            / str(render_task_id)
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        # 3. Stage material images to shared dir
        material_paths = await self._stage_materials(material_assignments, output_dir)

        # 4. Mark processing
        await self._update_render_task(render_task_id, status="processing")

        # 5. Call CLO3D HTTP API (blocking — waits for render to finish)
        try:
            result = await self._call_clo3d_render(
                prj_path=str(prj_path),
                material_assignments=material_paths,
                output_dir=str(output_dir),
            )
        except httpx.ConnectError:
            await self._update_render_task(
                render_task_id, status="failed",
                error=f"无法连接 CLO3D ({self._api_url})，请确保 CLO3D 已启动且插件正在运行"
            )
            raise WorkerError(f"CLO3D API unreachable at {self._api_url}")
        except httpx.TimeoutException:
            await self._update_render_task(
                render_task_id, status="failed", error="CLO3D 渲染超时"
            )
            raise WorkerError("CLO3D render timed out")

        if result.get("status") != "success":
            error = result.get("error", "Unknown CLO3D error")
            await self._update_render_task(render_task_id, status="failed", error=error)
            raise WorkerError(error)

        # 6. Save rendered images to DB
        images = result.get("images", {})
        front_url, back_url = await self._save_render_images(
            render_task_id, images.get("front", ""), images.get("back", "")
        )

        return {
            "status": "success",
            "render_task_id": render_task_id,
            "front_url": front_url,
            "back_url": back_url,
        }

    # ── CLO3D HTTP Call ────────────────────────────────────────────────────

    async def _call_clo3d_render(
        self,
        prj_path: str,
        material_assignments: dict[str, str],
        output_dir: str,
    ) -> dict[str, Any]:
        """POST /render to CLO3D API server."""
        http = await self._get_http()

        payload = {
            "prj_path": prj_path,
            "material_assignments": material_assignments,
            "views": ["front", "back"],
            "output_dir": output_dir,
        }

        self.logger.info(f"POST /render → {self._api_url}")
        response = await http.post("/render", json=payload)

        if response.status_code != 200:
            raise WorkerError(
                f"CLO3D API returned {response.status_code}: {response.text[:500]}"
            )

        return response.json()

    # ── DB Helpers ──────────────────────────────────────────────────────────

    async def _load_project(self, project_id: int) -> dict[str, Any] | None:
        from api.db.models import Clo3dProject

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(Clo3dProject).where(Clo3dProject.id == project_id)
            )
            record = result.scalar_one_or_none()
            if not record:
                return None
            return {
                "id": record.id,
                "prj_file": str(record.prj_file) if record.prj_file else None,
                "pieces": record.pieces,
            }

    async def _resolve_prj_path(self, project: dict[str, Any]) -> str | None:
        from api.storage.storages import clo3d_project_storage

        prj_file = project.get("prj_file")
        if not prj_file:
            return None

        filename = Path(prj_file).name
        try:
            storage_path = clo3d_project_storage.get_name(filename)
            full_path = Path(clo3d_project_storage.path) / storage_path
            if full_path.exists():
                return str(full_path)
        except Exception:
            pass
        return prj_file

    async def _stage_materials(
        self, assignments: dict[str, int], output_dir: Path
    ) -> dict[str, str]:
        """Copy materials to output dir, return piece_name → local_path map."""
        from api.db.models import Material
        from api.storage.storages import material_storage

        result: dict[str, str] = {}
        unique_ids = set(assignments.values())
        mats_dir = output_dir / "materials"
        mats_dir.mkdir(exist_ok=True)

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            for mid in unique_ids:
                db_result = await session.execute(
                    select(Material).where(Material.id == mid)
                )
                material = db_result.scalar_one_or_none()
                if not material or not material.file:
                    continue

                try:
                    img_bytes = await material_storage.download(str(material.file))
                except Exception as exc:
                    self.logger.warning(f"Material {mid} download failed: {exc}")
                    continue

                ext = (
                    Path(str(material.original_filename or "material.png")).suffix
                    or ".png"
                )
                dest = mats_dir / f"material_{mid}{ext}"
                dest.write_bytes(img_bytes)
                result[str(mid)] = str(dest)

        return {
            name: result.get(str(mid), "")
            for name, mid in assignments.items()
        }

    async def _save_render_images(
        self, render_task_id: int, front_path: str, back_path: str
    ) -> tuple[str | None, str | None]:
        from api.db.models import Clo3dRenderTask
        from api.storage.storages import clo3d_render_storage

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            stmt = select(Clo3dRenderTask).where(Clo3dRenderTask.id == render_task_id)
            db_result = await session.execute(stmt)
            record = db_result.scalar_one_or_none()

            front_url = None
            back_url = None

            if record:
                if front_path and Path(front_path).exists():
                    record.front_image = io.BytesIO(Path(front_path).read_bytes())
                if back_path and Path(back_path).exists():
                    record.back_image = io.BytesIO(Path(back_path).read_bytes())

                record.status = "completed"
                record.completed_at = datetime.now(UTC)
                await session.commit()

                if record.front_image:
                    front_url = clo3d_render_storage.get_url(str(record.front_image))
                if record.back_image:
                    back_url = clo3d_render_storage.get_url(str(record.back_image))

            return front_url, back_url

    async def _update_render_task(
        self, render_task_id: int, status: str, error: str | None = None
    ) -> None:
        from api.db.models import Clo3dRenderTask

        session_factory = await self._get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(Clo3dRenderTask).where(Clo3dRenderTask.id == render_task_id)
            )
            record = result.scalar_one_or_none()
            if record:
                record.status = status
                if error:
                    record.error_message = error
                if status == "completed":
                    record.completed_at = datetime.now(UTC)
                await session.commit()


__all__ = ["Clo3dRenderHandler"]
