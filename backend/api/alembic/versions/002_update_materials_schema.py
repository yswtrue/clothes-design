"""Update materials table schema for file upload service

Revision ID: 002_update_materials_schema
Revises: 001_initial_schema
Create Date: 2026-04-05 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002_update_materials_schema"
down_revision: str | None = "001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop old index
    op.drop_index("ix_materials_user_id", table_name="materials")

    # Rename user_id to uploaded_by
    op.alter_column("materials", "user_id", new_column_name="uploaded_by")

    # Rename file_path to storage_path
    op.alter_column("materials", "file_path", new_column_name="storage_path")

    # Drop file_type column (replaced by mime_type)
    op.drop_column("materials", "file_type")

    # Add new columns
    op.add_column("materials", sa.Column("original_filename", sa.String(255), nullable=True))
    op.add_column("materials", sa.Column("stored_filename", sa.String(255), nullable=True))
    op.add_column("materials", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("materials", sa.Column("mime_type", sa.String(100), nullable=True))

    # Recreate index with new column name
    op.create_index("ix_materials_uploaded_by", "materials", ["uploaded_by"])

    # Add unique constraint on stored_filename
    op.create_unique_constraint("uq_materials_stored_filename", "materials", ["stored_filename"])


def downgrade() -> None:
    # Drop unique constraint
    op.drop_constraint("uq_materials_stored_filename", "materials", type_="unique")

    # Drop new index
    op.drop_index("ix_materials_uploaded_by", table_name="materials")

    # Drop new columns
    op.drop_column("materials", "mime_type")
    op.drop_column("materials", "file_size")
    op.drop_column("materials", "stored_filename")
    op.drop_column("materials", "original_filename")

    # Add back file_type column
    op.add_column("materials", sa.Column("file_type", sa.String(50), nullable=True))

    # Rename storage_path back to file_path
    op.alter_column("materials", "storage_path", new_column_name="file_path")

    # Rename uploaded_by back to user_id
    op.alter_column("materials", "uploaded_by", new_column_name="user_id")

    # Recreate old index
    op.create_index("ix_materials_user_id", "materials", ["user_id"])
