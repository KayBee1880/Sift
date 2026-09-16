"""add chunks.overlapping_sections for fixed-size chunking provenance

Revision ID: 70c685ee0db9
Revises: 76892ade6e06
Create Date: 2026-09-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '70c685ee0db9'
down_revision: Union[str, Sequence[str], None] = '76892ade6e06'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'chunks',
        sa.Column(
            'overlapping_sections',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chunks', 'overlapping_sections')
