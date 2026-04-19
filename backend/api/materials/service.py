"""Material management service."""

import math
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import String, and_, cast as sa_cast, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Material
from api.materials.schemas import (
    MaterialListResponse,
    MaterialUpdateRequest,
    PaginatedMaterialsResponse,
)
from api.storage.factory import get_storage_service


class MaterialService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.storage = get_storage_service()

    async def _add_thumbnail_url(self, material: Material) -> MaterialListResponse:
        response = MaterialListResponse.model_validate(material)
        if material.meta and isinstance(material.meta, dict):
            thumbnail_path = material.meta.get("thumbnail_path")
            if thumbnail_path:
                response.thumbnail_url = await self.storage.get_url(
                    thumbnail_path.replace("thumbnails/", "")
                    if thumbnail_path.startswith("thumbnails/")
                    else thumbnail_path
                )
        return response

    async def list_materials(
        self,
        page: int = 1,
        page_size: int = 20,
        uploaded_by: int | None = None,
        mime_type: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedMaterialsResponse:
        query = select(Material).filter(
            or_(
                sa_cast(Material.meta["is_deleted"], String) != "true",
                Material.meta["is_deleted"].is_(None),
                Material.meta.is_(None),
            )
        )

        if uploaded_by is not None:
            query = query.filter(Material.uploaded_by == uploaded_by)

        if mime_type:
            query = query.filter(Material.mime_type == mime_type)

        sort_col: Any
        if sort_by == "file_size":
            sort_col = Material.file_size
        else:
            sort_col = Material.created_at

        if sort_order == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        count_result = await self.session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.session.execute(query)
        materials = result.scalars().all()

        total_pages = math.ceil(total / page_size) if page_size > 0 else 0

        items = []
        for m in materials:
            items.append(await self._add_thumbnail_url(m))

        return PaginatedMaterialsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_material_by_id(self, material_id: int) -> Material | None:
        query = select(Material).filter(
            and_(
                Material.id == material_id,
                or_(
                    sa_cast(Material.meta["is_deleted"], String) != "true",
                    Material.meta["is_deleted"].is_(None),
                    Material.meta.is_(None),
                ),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_material(
        self,
        material_id: int,
        user_id: int,
        update_data: MaterialUpdateRequest,
    ) -> Material | None:
        material = await self.get_material_by_id(material_id)

        if material is None:
            return None

        if material.uploaded_by != user_id:
            raise PermissionError("User does not own this material")

        meta: dict = cast(dict, material.meta) or {}

        if update_data.name is not None:
            meta["name"] = update_data.name

        if update_data.tags is not None:
            meta["tags"] = update_data.tags

        if update_data.description is not None:
            meta["description"] = update_data.description

        stmt = (
            update(Material).where(Material.id == material_id).values(meta=meta).returning(Material)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.scalar_one()

    async def delete_material(self, material_id: int, user_id: int) -> Material | None:
        material = await self.get_material_by_id(material_id)

        if material is None:
            return None

        if material.uploaded_by != user_id:
            raise PermissionError("User does not own this material")

        meta: dict = cast(dict, material.meta) or {}
        meta["is_deleted"] = True
        meta["deleted_at"] = datetime.now(UTC).isoformat()

        stmt = (
            update(Material).where(Material.id == material_id).values(meta=meta).returning(Material)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()

        return result.scalar_one()

    async def search_materials(
        self,
        query: str,
        page: int = 1,
        page_size: int = 20,
    ) -> PaginatedMaterialsResponse:
        search_filter = or_(
            Material.meta["name"].as_string().ilike(f"%{query}%"),
            Material.meta["tags"].as_string().ilike(f"%{query}%"),
        )

        stmt = select(Material).filter(
            and_(
                or_(
                    sa_cast(Material.meta["is_deleted"], String) != "true",
                    Material.meta["is_deleted"].is_(None),
                    Material.meta.is_(None),
                ),
                search_filter,
            )
        )

        count_result = await self.session.execute(select(func.count()).select_from(stmt.subquery()))
        total = count_result.scalar_one()

        offset = (page - 1) * page_size
        stmt = stmt.order_by(Material.created_at.desc()).offset(offset).limit(page_size)

        result = await self.session.execute(stmt)
        materials = result.scalars().all()

        total_pages = math.ceil(total / page_size) if page_size > 0 else 0

        items = []
        for m in materials:
            items.append(await self._add_thumbnail_url(m))

        return PaginatedMaterialsResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
