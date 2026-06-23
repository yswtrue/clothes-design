"""add ecommerce_posters

Revision ID: d02432dc7ea1
Revises: d4e5f6a7b8c9
Create Date: 2026-06-23 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d02432dc7ea1"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ecommerce_posters",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("product_type", sa.String(length=100), nullable=False),
        sa.Column("style", sa.String(length=100), nullable=False),
        sa.Column("custom_prompt", sa.Text(), nullable=True),
        sa.Column("material_ids", sa.JSON(), nullable=True),
        sa.Column("image_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("width", sa.Integer(), nullable=False, server_default=sa.text("1024")),
        sa.Column("height", sa.Integer(), nullable=False, server_default=sa.text("768")),
        sa.Column("language", sa.String(length=10), nullable=False, server_default=sa.text("'en'")),
        sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'generating'")),
        sa.Column("result_images", sa.JSON(), nullable=True),
        sa.Column("generation_params", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("ecommerce_posters", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_ecommerce_posters_deleted_at"), ["deleted_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ecommerce_posters_user_id"), ["user_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ecommerce_posters_product_type"), ["product_type"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ecommerce_posters_status"), ["status"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ecommerce_posters_language"), ["language"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_ecommerce_posters_created_at"), ["created_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("ecommerce_posters", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_ecommerce_posters_created_at"))
        batch_op.drop_index(batch_op.f("ix_ecommerce_posters_language"))
        batch_op.drop_index(batch_op.f("ix_ecommerce_posters_status"))
        batch_op.drop_index(batch_op.f("ix_ecommerce_posters_product_type"))
        batch_op.drop_index(batch_op.f("ix_ecommerce_posters_user_id"))
        batch_op.drop_index(batch_op.f("ix_ecommerce_posters_deleted_at"))

    op.drop_table("ecommerce_posters")
