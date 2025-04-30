"""add_title_to_daily_tasks

Revision ID: 312f338f9f0e
Revises: 4e2d56a04892
Create Date: 2025-04-29 19:40:49.589597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '312f338f9f0e'
down_revision: Union[str, None] = '4e2d56a04892'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('daily_tasks', sa.Column('title', sa.String(255), nullable=False, server_default="Task", index=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('daily_tasks', 'title')
