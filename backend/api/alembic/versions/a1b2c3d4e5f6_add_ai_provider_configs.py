"""add ai_provider_configs table

Revision ID: a1b2c3d4e5f6
Revises: f68c82f9bffb
Create Date: 2026-04-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f68c82f9bffb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('ai_provider_configs',
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_type', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('base_url', sa.String(length=500), nullable=False),
        sa.Column('api_key', sa.String(length=500), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rate_limit', sa.Integer(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('ai_provider_configs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ai_provider_configs_deleted_at'), ['deleted_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_provider_configs_provider_type'), ['provider_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_provider_configs_is_active'), ['is_active'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_provider_configs_priority'), ['priority'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('ai_provider_configs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ai_provider_configs_priority'))
        batch_op.drop_index(batch_op.f('ix_ai_provider_configs_is_active'))
        batch_op.drop_index(batch_op.f('ix_ai_provider_configs_provider_type'))
        batch_op.drop_index(batch_op.f('ix_ai_provider_configs_deleted_at'))

    op.drop_table('ai_provider_configs')
