from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session
from sqlmodel import Field, SQLModel

from config import get_settings

_settings = get_settings()

engine = create_async_engine(
    _settings.database.async_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=_settings.database.pool_size,
    max_overflow=_settings.database.max_overflow,
    pool_recycle=_settings.database.pool_recycle,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    pass


class SoftDeleteMixin(SQLModel):
    """Mixin for soft delete functionality.

    Provides deleted_at timestamp field and is_deleted property.
    """

    deleted_at: Optional[datetime] = Field(default=None, index=True)

    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft-deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark record as soft-deleted."""
        self.deleted_at = datetime.utcnow()

    @classmethod
    def exclude_deleted(cls, stmt):
        """Filter out soft-deleted records from select statement."""
        return stmt.where(cls.deleted_at == None)


@event.listens_for(Session, "do_orm_execute", propagate=True)
def _filter_soft_deleted(orm_execute_state):
    """Automatically filter soft-deleted records for all queries."""
    if not orm_execute_state.is_select:
        return

    if orm_execute_state.execution_options.get("include_deleted", False):
        return

    statement = orm_execute_state.statement

    for entity in statement.column_descriptions:
        entity_class = entity.get("entity")
        if entity_class is None:
            continue

        if hasattr(entity_class, "deleted_at"):
            orm_execute_state.statement = statement.filter(entity_class.deleted_at == None)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
