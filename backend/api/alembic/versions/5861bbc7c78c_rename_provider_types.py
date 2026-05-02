"""rename_provider_types

Revision ID: 5861bbc7c78c
Revises: f272c0c5c32c
Create Date: 2026-05-02 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '5861bbc7c78c'
down_revision: Union[str, None] = '84276b1cc399'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PROVIDER_TYPE_RENAMES = {
    'openai_image': 'openai_image_edit',
    'vectorizer': 'vectorizer_ai',
    'esrgan': 'replicate',
    'gptproto': 'openai_image_edit',
}


def upgrade() -> None:
    for old_type, new_type in PROVIDER_TYPE_RENAMES.items():
        op.execute(
            f"UPDATE ai_provider_configs SET provider_type = '{new_type}' "
            f"WHERE provider_type = '{old_type}'"
        )
        op.execute(
            f"UPDATE prompt_templates SET provider_type = '{new_type}' "
            f"WHERE provider_type = '{old_type}'"
        )


def downgrade() -> None:
    reverse_renames = {
        'openai_image_edit': 'openai_image',
        'vectorizer_ai': 'vectorizer',
    }
    for new_type, old_type in reverse_renames.items():
        op.execute(
            f"UPDATE ai_provider_configs SET provider_type = '{old_type}' "
            f"WHERE provider_type = '{new_type}'"
        )
        op.execute(
            f"UPDATE prompt_templates SET provider_type = '{old_type}' "
            f"WHERE provider_type = '{new_type}'"
        )
