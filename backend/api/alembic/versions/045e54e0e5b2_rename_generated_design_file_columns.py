"""rename_generated_design_file_columns

Revision ID: 045e54e0e5b2
Revises: b9dac66412b7
Create Date: 2026-05-03 00:23:12.655100

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '045e54e0e5b2'
down_revision: Union[str, None] = 'b9dac66412b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('generated_designs', 'upscaled_image', new_column_name='upscaled_path')
    op.alter_column('generated_designs', 'vector_svg', new_column_name='vector_path')
    op.alter_column('generated_designs', 'export_tif', new_column_name='export_tif_path')


def downgrade() -> None:
    op.alter_column('generated_designs', 'upscaled_path', new_column_name='upscaled_image')
    op.alter_column('generated_designs', 'vector_path', new_column_name='vector_svg')
    op.alter_column('generated_designs', 'export_tif_path', new_column_name='export_tif')
