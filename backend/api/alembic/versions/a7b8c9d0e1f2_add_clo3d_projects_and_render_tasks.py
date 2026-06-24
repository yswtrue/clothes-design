"""add clo3d_projects and clo3d_render_tasks

Revision ID: a7b8c9d0e1f2
Revises: e5f6a7b8c9d0
Create Date: 2026-06-24 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7b8c9d0e1f2"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clo3d_projects",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("prj_path", sa.String(length=500), nullable=True),
        sa.Column("preview_image", sa.String(length=500), nullable=True),
        sa.Column("pieces", sa.JSON(), nullable=True),
        sa.Column("piece_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="'uploaded'"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("clo3d_projects", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_clo3d_projects_category"), ["category"], unique=False)
        batch_op.create_index(batch_op.f("ix_clo3d_projects_deleted_at"), ["deleted_at"], unique=False)
        batch_op.create_index(batch_op.f("ix_clo3d_projects_name"), ["name"], unique=False)
        batch_op.create_index(batch_op.f("ix_clo3d_projects_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_clo3d_projects_user_id"), ["user_id"], unique=False)

    op.create_table(
        "clo3d_render_tasks",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("material_assignments", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="'pending'"),
        sa.Column("front_image_path", sa.String(length=500), nullable=True),
        sa.Column("back_image_path", sa.String(length=500), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("render_params", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["clo3d_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("clo3d_render_tasks", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_clo3d_render_tasks_created_at"), ["created_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_clo3d_render_tasks_deleted_at"), ["deleted_at"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_clo3d_render_tasks_project_id"), ["project_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_clo3d_render_tasks_status"), ["status"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_clo3d_render_tasks_user_id"), ["user_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("clo3d_render_tasks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_clo3d_render_tasks_user_id"))
        batch_op.drop_index(batch_op.f("ix_clo3d_render_tasks_status"))
        batch_op.drop_index(batch_op.f("ix_clo3d_render_tasks_project_id"))
        batch_op.drop_index(batch_op.f("ix_clo3d_render_tasks_deleted_at"))
        batch_op.drop_index(batch_op.f("ix_clo3d_render_tasks_created_at"))

    op.drop_table("clo3d_render_tasks")

    with op.batch_alter_table("clo3d_projects", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_clo3d_projects_user_id"))
        batch_op.drop_index(batch_op.f("ix_clo3d_projects_status"))
        batch_op.drop_index(batch_op.f("ix_clo3d_projects_name"))
        batch_op.drop_index(batch_op.f("ix_clo3d_projects_deleted_at"))
        batch_op.drop_index(batch_op.f("ix_clo3d_projects_category"))

    op.drop_table("clo3d_projects")
