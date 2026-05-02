"""make image_path nullable in generated_designs

Revision ID: c1d2e3f4g5h6
Revises: 045e54e0e5b2
Create Date: 2026-05-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1d2e3f4g5h6'
down_revision: Union[str, None] = '045e54e0e5b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('generated_designs', 'image_path',
                    existing_type=sa.VARCHAR(length=500),
                    nullable=True)


def downgrade() -> None:
    op.alter_column('generated_designs', 'image_path',
                    existing_type=sa.VARCHAR(length=500),
                    nullable=False)
