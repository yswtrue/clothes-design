"""add_prompt_features_table

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4g5h6
Create Date: 2026-06-13 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c1d2e3f4g5h6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prompt_features",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("prompt_features", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_prompt_features_deleted_at"), ["deleted_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_prompt_features_is_active"), ["is_active"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_prompt_features_is_default"), ["is_default"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_prompt_features_key"), ["key"], unique=True)
        batch_op.create_index(
            batch_op.f("ix_prompt_features_sort_order"), ["sort_order"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("prompt_features", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_prompt_features_sort_order"))
        batch_op.drop_index(batch_op.f("ix_prompt_features_key"))
        batch_op.drop_index(batch_op.f("ix_prompt_features_is_default"))
        batch_op.drop_index(batch_op.f("ix_prompt_features_is_active"))
        batch_op.drop_index(batch_op.f("ix_prompt_features_deleted_at"))

    op.drop_table("prompt_features")
