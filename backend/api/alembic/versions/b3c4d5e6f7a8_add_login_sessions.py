"""add login_sessions table

Revision ID: b3c4d5e6f7a8
Revises: f272c0c5c32c
Create Date: 2026-05-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'f272c0c5c32c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('login_sessions',
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('login_token', sa.String(length=36), nullable=False),
        sa.Column('token_type', sa.String(length=20), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('login_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_login_sessions_deleted_at'), ['deleted_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_login_sessions_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_login_sessions_login_token'), ['login_token'], unique=True)
        batch_op.create_index(batch_op.f('ix_login_sessions_token_type'), ['token_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_login_sessions_expires_at'), ['expires_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('login_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_login_sessions_expires_at'))
        batch_op.drop_index(batch_op.f('ix_login_sessions_token_type'))
        batch_op.drop_index(batch_op.f('ix_login_sessions_login_token'))
        batch_op.drop_index(batch_op.f('ix_login_sessions_user_id'))
        batch_op.drop_index(batch_op.f('ix_login_sessions_deleted_at'))

    op.drop_table('login_sessions')
