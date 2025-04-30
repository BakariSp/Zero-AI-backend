"""rename_user_tasks_table_to_backend_tasks

Revision ID: a384beeb732d
Revises: 9328d07365ce
Create Date: 2025-04-29 18:34:26.430562

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a384beeb732d'
down_revision: Union[str, None] = '9328d07365ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename the user_tasks table to backend_tasks."""
    # For MySQL, we need to use a simpler approach - just rename the table
    # The indexes will be renamed automatically with the table
    op.rename_table('user_tasks', 'backend_tasks')
    
    # Note: MySQL doesn't support direct renaming of indexes or constraints
    # The indexes are renamed automatically when the table is renamed
    # For foreign key constraints, they would need to be dropped and recreated
    # if we need to rename them specifically, but that's not necessary here


def downgrade() -> None:
    """Rename the backend_tasks table back to user_tasks."""
    # Simply rename the table back
    op.rename_table('backend_tasks', 'user_tasks')
    
    # No need to manually rename indexes or constraints in MySQL
