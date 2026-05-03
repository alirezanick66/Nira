"""merge_migration_heads

Revision ID: fd9deb62477c
Revises: 001_query_logs, 7e357f5fe430
Create Date: 2026-05-03 14:55:56.821788

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd9deb62477c'
down_revision: Union[str, Sequence[str], None] = ('001_query_logs', '7e357f5fe430')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
