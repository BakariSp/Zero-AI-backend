"""add_subscription_type_to_users

Revision ID: df6971787818
Revises: 312f338f9f0e
Create Date: 2025-04-30 18:54:13.807083

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'df6971787818'
down_revision: Union[str, None] = '312f338f9f0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add subscription_type column to users table
    op.add_column('users', sa.Column('subscription_type', sa.String(20), nullable=True, server_default='free'))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove subscription_type column from users table
    op.drop_column('users', 'subscription_type')
