import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool
from sqlmodel import SQLModel
from sqlmodel.sql.sqltypes import AutoString

from alembic import context
from api.db.models import Design, DesignVersion, Material, Role, Template, User, UserRole

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def render_item(type_, obj, autogen_context):
    """Render SQLModel types as standard SQLAlchemy types."""
    if isinstance(obj, AutoString):
        # Render AutoString as sa.String with length
        if obj.length:
            return f"sa.String(length={obj.length})"
        return "sa.String()"
    return False


def get_sqlalchemy_url() -> str:
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/clothes_design_dev"
    )
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


def run_migrations_offline() -> None:
    url = get_sqlalchemy_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = get_sqlalchemy_url()

    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
            render_item=render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
