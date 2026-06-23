"""add language to ecommerce_posters

Revision ID: e5f6a7b8c9d0
Revises: d02432dc7ea1
Create Date: 2026-06-23 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d02432dc7ea1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("ecommerce_posters", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "language",
                sa.String(length=10),
                nullable=False,
                server_default=sa.text("'en'"),
            )
        )
        batch_op.create_index(
            batch_op.f("ix_ecommerce_posters_language"), ["language"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("ecommerce_posters", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ecommerce_posters_language"))
        batch_op.drop_column("language")
