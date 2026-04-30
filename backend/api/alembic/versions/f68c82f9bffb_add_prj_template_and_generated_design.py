"""add prj_template and generated_design tables

Revision ID: f68c82f9bffb
Revises: bc70a227d0be
Create Date: 2026-04-29 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f68c82f9bffb'
down_revision: Union[str, None] = 'bc70a227d0be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('prj_templates',
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('prj_path', sa.String(length=500), nullable=False),
        sa.Column('preview_image', sa.String(length=500), nullable=True),
        sa.Column('regions', sa.JSON(), nullable=True),
        sa.Column('is_builtin', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default='now()', nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('prj_templates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_prj_templates_category'), ['category'], unique=False)
        batch_op.create_index(batch_op.f('ix_prj_templates_deleted_at'), ['deleted_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_prj_templates_name'), ['name'], unique=False)

    op.create_table('generated_designs',
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('material_id', sa.Integer(), nullable=False),
        sa.Column('image_path', sa.String(length=500), nullable=False),
        sa.Column('thumbnail_path', sa.String(length=500), nullable=True),
        sa.Column('prompt_used', sa.String(), nullable=True),
        sa.Column('seed', sa.Integer(), nullable=True),
        sa.Column('variant_index', sa.Integer(), nullable=False),
        sa.Column('generation_params', sa.JSON(), nullable=True),
        sa.Column('is_selected', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default='now()', nullable=True),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('generated_designs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_generated_designs_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_generated_designs_deleted_at'), ['deleted_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_generated_designs_is_selected'), ['is_selected'], unique=False)
        batch_op.create_index(batch_op.f('ix_generated_designs_material_id'), ['material_id'], unique=False)

    with op.batch_alter_table('designs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('generated_design_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('prj_template_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('output_tif_path', sa.String(length=500), nullable=True))
        batch_op.create_index(batch_op.f('ix_designs_generated_design_id'), ['generated_design_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_designs_prj_template_id'), ['prj_template_id'], unique=False)
        batch_op.create_foreign_key('fk_designs_generated_design_id', 'generated_designs', ['generated_design_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_designs_prj_template_id', 'prj_templates', ['prj_template_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    with op.batch_alter_table('designs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_designs_prj_template_id', type_='foreignkey')
        batch_op.drop_constraint('fk_designs_generated_design_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_designs_prj_template_id'))
        batch_op.drop_index(batch_op.f('ix_designs_generated_design_id'))
        batch_op.drop_column('output_tif_path')
        batch_op.drop_column('prj_template_id')
        batch_op.drop_column('generated_design_id')

    with op.batch_alter_table('generated_designs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_generated_designs_material_id'))
        batch_op.drop_index(batch_op.f('ix_generated_designs_is_selected'))
        batch_op.drop_index(batch_op.f('ix_generated_designs_deleted_at'))
        batch_op.drop_index(batch_op.f('ix_generated_designs_created_at'))

    op.drop_table('generated_designs')

    with op.batch_alter_table('prj_templates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_prj_templates_name'))
        batch_op.drop_index(batch_op.f('ix_prj_templates_deleted_at'))
        batch_op.drop_index(batch_op.f('ix_prj_templates_category'))

    op.drop_table('prj_templates')
