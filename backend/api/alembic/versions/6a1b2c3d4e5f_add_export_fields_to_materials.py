"""add export fields to materials

Revision ID: 6a1b2c3d4e5f
Revises: f68c82f9bffb
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6a1b2c3d4e5f'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('materials', sa.Column('upscaled_path', sa.String(length=500), nullable=True))
    op.add_column('materials', sa.Column('export_tif_path', sa.String(length=500), nullable=True))
    op.add_column('materials', sa.Column('exported_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('materials', 'exported_at')
    op.drop_column('materials', 'export_tif_path')
    op.drop_column('materials', 'upscaled_path')
