"""Material management service."""

from typing import Any

from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import Material
from api.materials.schemas import (
    MaterialListResponse,
    MaterialMeta,
    MaterialUpdateRequest,
)
from api.storage.storages import thumbnail_storage


class MaterialService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _add_thumbnail_url(self, material: Material) -> MaterialListResponse:
        response = MaterialListResponse.model_validate(material)
        if material.meta:
            meta = MaterialMeta(**material.meta)
            if meta.thumbnail_path:
                response.thumbnail_url = thumbnail_storage.get_url(meta.thumbnail_path)
        return response

    async def list_materials(
        self,
        uploaded_by: int | None = None,
        mime_type: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Page[MaterialListResponse]:
        query = select(Material)

        if uploaded_by is not None:
            query = query.filter(Material.uploaded_by == uploaded_by)  # type: ignore[arg-type]

        if mime_type:
            query = query.filter(Material.mime_type == mime_type)  # type: ignore[arg-type]

        sort_col: Any
        if sort_by == "file_size":
            sort_col = Material.file_size
        else:
            sort_col = Material.created_at

        if sort_order == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        page = await paginate(self.session, query)

        items_with_thumbnails = []
        for item in page.items:
            item_with_url = self._add_thumbnail_url(item)
            items_with_thumbnails.append(item_with_url)

        return Page(
            items=items_with_thumbnails,  # type: ignore[call-arg]
            total=page.total,
            page=page.page,
            size=page.size,
            pages=page.pages,
        )

    async def get_material_by_id(self, material_id: int) -> Material | None:
        query = select(Material).filter(Material.id == material_id)  # type: ignore[arg-type]
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

        meta = MaterialMeta(**material.meta) if material.meta else MaterialMeta()  # type: ignore[arg-type]

        if update_data.name is not None:
            meta.name = update_data.name

        if update_data.tags is not None:
            meta.tags = update_data.tags

        if update_data.description is not None:
            meta.description = update_data.description

        stmt = (
            update(Material)
            .where(Material.id == material_id)  # type: ignore[arg-type]
            .values(meta=meta.model_dump(exclude_none=True))
            .returning(Material)
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

        material.soft_delete()
        await self.session.commit()

        return material

    async def search_materials(
        self,
        query: str,
    ) -> Page[MaterialListResponse]:
        search_filter = or_(  # type: ignore[arg-type]
            Material.meta["name"].as_string().ilike(f"%{query}%"),  # type: ignore[index]
            Material.meta["tags"].as_string().ilike(f"%{query}%"),  # type: ignore[index]
        )

        stmt = select(Material).filter(search_filter).order_by(Material.created_at.desc())  # type: ignore[attr-defined]

        page = await paginate(self.session, stmt)

        items_with_thumbnails = []
        for item in page.items:
            item_with_url = self._add_thumbnail_url(item)
            items_with_thumbnails.append(item_with_url)

        return Page(
            items=items_with_thumbnails,  # type: ignore[call-arg]
            total=page.total,
            page=page.page,
            size=page.size,
            pages=page.pages,
        )
