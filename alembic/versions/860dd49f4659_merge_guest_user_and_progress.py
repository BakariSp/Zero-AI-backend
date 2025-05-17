"""merge_guest_user_and_progress

Revision ID: 860dd49f4659
Revises: 53f7cb651d97, add_progress_to_user_sections
Create Date: 2025-05-14 18:42:40.476846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '860dd49f4659'
down_revision: Union[str, None] = ('53f7cb651d97', 'add_progress_to_user_sections')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
