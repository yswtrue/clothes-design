"""add_export_fields_to_generated_designs

Revision ID: b9dac66412b7
Revises: 5861bbc7c78c
Create Date: 2026-05-03 00:16:27.445446

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b9dac66412b7'
down_revision: Union[str, None] = '5861bbc7c78c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('generated_designs', sa.Column('status', sa.String(50), nullable=False, server_default='completed'))
    op.add_column('generated_designs', sa.Column('upscaled_image', sa.String(500), nullable=True))
    op.add_column('generated_designs', sa.Column('vector_svg', sa.String(500), nullable=True))
    op.add_column('generated_designs', sa.Column('export_tif', sa.String(500), nullable=True))
    op.add_column('generated_designs', sa.Column('exported_at', sa.DateTime(), nullable=True))
    op.create_index('ix_generated_designs_status', 'generated_designs', ['status'])


def downgrade() -> None:
    op.drop_index('ix_generated_designs_status', 'generated_designs')
    op.drop_column('generated_designs', 'exported_at')
    op.drop_column('generated_designs', 'export_tif')
    op.drop_column('generated_designs', 'vector_svg')
    op.drop_column('generated_designs', 'upscaled_image')
    op.drop_column('generated_designs', 'status')
