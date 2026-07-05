"""drop_vector_path_from_generated_designs

Revision ID: f7a8b9c0d1e2
Revises: 6a1b2c3d4e5f
Create Date: 2026-07-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = '6a1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('generated_designs', 'vector_path')


def downgrade() -> None:
    op.add_column('generated_designs', sa.Column('vector_path', sa.String(length=500), nullable=True))
