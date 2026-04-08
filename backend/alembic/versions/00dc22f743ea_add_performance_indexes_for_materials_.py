"""add performance indexes for materials and designs

Revision ID: 00dc22f743ea
Revises: 002_update_materials_schema
Create Date: 2026-04-06 01:46:57.521085

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "00dc22f743ea"
down_revision: Union[str, None] = "002_update_materials_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f("ix_designs_created_at"), "designs", ["created_at"], unique=False)
    op.create_index(op.f("ix_designs_status"), "designs", ["status"], unique=False)
    op.create_index(op.f("ix_materials_created_at"), "materials", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_materials_created_at"), table_name="materials")
    op.drop_index(op.f("ix_designs_status"), table_name="designs")
    op.drop_index(op.f("ix_designs_created_at"), table_name="designs")
