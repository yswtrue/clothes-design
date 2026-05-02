from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Optional

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Session
from sqlmodel import Field, SQLModel

from shared.db import get_engine, get_session_factory

engine = get_engine()
AsyncSessionLocal = get_session_factory()


class Base(DeclarativeBase):
    pass


class SoftDeleteMixin(SQLModel):
    deleted_at: Optional[datetime] = Field(default=None, index=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = datetime.utcnow()

    @classmethod
    def exclude_deleted(cls, stmt):
        return stmt.where(cls.deleted_at == None)


@event.listens_for(Session, "do_orm_execute", propagate=True)
def _filter_soft_deleted(orm_execute_state):
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
