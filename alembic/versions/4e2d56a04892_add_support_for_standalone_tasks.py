"""Add support for standalone tasks

Revision ID: 4e2d56a04892
Revises: a384beeb732d
Create Date: 2025-04-29 19:22:40.084781

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '4e2d56a04892'
down_revision: Union[str, None] = 'a384beeb732d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make foreign key fields nullable to support standalone tasks."""
    # Instead of dropping tables, we'll just modify the columns to be nullable
    with op.batch_alter_table('daily_tasks', schema=None) as batch_op:
        # Make card_id nullable
        batch_op.alter_column('card_id',
               existing_type=mysql.INTEGER(),
               nullable=True)
        
        # Make section_id nullable
        batch_op.alter_column('section_id',
               existing_type=mysql.INTEGER(),
               nullable=True)
        
        # Make course_id nullable
        batch_op.alter_column('course_id',
               existing_type=mysql.INTEGER(),
               nullable=True)
        
        # Make learning_path_id nullable
        batch_op.alter_column('learning_path_id',
               existing_type=mysql.INTEGER(),
               nullable=True)


def downgrade() -> None:
    """Revert foreign key fields back to non-nullable.
    
    Warning: This will fail if there are any standalone tasks in the database.
    Make sure to update or delete all standalone tasks before downgrading.
    """
    # First, confirm there are no NULL values in these fields
    # This section would need manual intervention before downgrading
    
    with op.batch_alter_table('daily_tasks', schema=None) as batch_op:
        # Make card_id non-nullable again
        batch_op.alter_column('card_id',
               existing_type=mysql.INTEGER(),
               nullable=False)
        
        # Make section_id non-nullable again
        batch_op.alter_column('section_id',
               existing_type=mysql.INTEGER(),
               nullable=False)
        
        # Make course_id non-nullable again
        batch_op.alter_column('course_id',
               existing_type=mysql.INTEGER(),
               nullable=False)
        
        # Make learning_path_id non-nullable again
        batch_op.alter_column('learning_path_id',
               existing_type=mysql.INTEGER(),
               nullable=False)
