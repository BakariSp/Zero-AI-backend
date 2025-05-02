"""merge heads

Revision ID: 31660d552ec3
Revises: ac87a5d3e92f, df6971787818
Create Date: 2025-05-01 12:10:21.760270

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31660d552ec3'
down_revision: Union[str, None] = ('ac87a5d3e92f', 'df6971787818')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
