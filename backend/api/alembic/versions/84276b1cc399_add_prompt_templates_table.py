"""add_prompt_templates_table

Revision ID: 84276b1cc399
Revises: b3c4d5e6f7a8
Create Date: 2026-05-02 20:18:15.819252

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '84276b1cc399'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('prompt_templates',
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('task_type', sa.String(length=50), nullable=False),
    sa.Column('provider_type', sa.String(length=50), nullable=True),
    sa.Column('template', sa.Text(), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('is_default', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('prompt_templates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_prompt_templates_deleted_at'), ['deleted_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_prompt_templates_is_active'), ['is_active'], unique=False)
        batch_op.create_index(batch_op.f('ix_prompt_templates_is_default'), ['is_default'], unique=False)
        batch_op.create_index(batch_op.f('ix_prompt_templates_name'), ['name'], unique=True)
        batch_op.create_index(batch_op.f('ix_prompt_templates_provider_type'), ['provider_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_prompt_templates_task_type'), ['task_type'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('prompt_templates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_prompt_templates_task_type'))
        batch_op.drop_index(batch_op.f('ix_prompt_templates_provider_type'))
        batch_op.drop_index(batch_op.f('ix_prompt_templates_name'))
        batch_op.drop_index(batch_op.f('ix_prompt_templates_is_default'))
        batch_op.drop_index(batch_op.f('ix_prompt_templates_is_active'))
        batch_op.drop_index(batch_op.f('ix_prompt_templates_deleted_at'))

    op.drop_table('prompt_templates')
