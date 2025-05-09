"""Use native enum for DailyTask status

Revision ID: 9328d07365ce
Revises: 84892dac8fbc
Create Date: 2025-04-29 15:27:11.840706

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '9328d07365ce'
down_revision: Union[str, None] = '84892dac8fbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the Enum type name and values for consistency
status_enum_name = 'dailytaskstatusenum'
status_enum_values = ('TODO', 'DONE', 'SKIPPED') # Use UPPERCASE values matching Python Enum

def upgrade() -> None:
    """Upgrade schema: Change status column to native ENUM."""
    # Create the ENUM type explicitly for MySQL
    # Note: PostgreSQL handles this automatically with native_enum=True in the model usually,
    # but explicit creation is safer across backends or if type doesn't exist.
    # For MySQL, altering the column directly defines the ENUM.

    # Alter the column type to the native ENUM
    # Using modify_type which should handle MySQL's ENUM syntax
    op.alter_column('daily_tasks', 'status',
               existing_type=sa.VARCHAR(length=50), # Assuming it was VARCHAR before
               type_=mysql.ENUM(*status_enum_values, name=status_enum_name),
               existing_nullable=False,
               # Add default if needed, ensure it matches the new type
               # existing_server_default=sa.text("'todo'"), # Old default if any
               server_default='TODO' # New default using uppercase
               )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema: Change status column back to VARCHAR."""
    # ### commands auto generated by Alembic - please adjust! ###
    # Alter the column back to VARCHAR (or whatever it was originally)
    op.alter_column('daily_tasks', 'status',
               existing_type=mysql.ENUM(*status_enum_values, name=status_enum_name),
               type_=sa.VARCHAR(length=50), # Revert to VARCHAR or original type
               existing_nullable=False,
               # Revert server default if needed
               # existing_server_default='TODO',
               server_default=sa.text("'todo'") # Revert to old default if any
               )

    # Drop the ENUM type if necessary (depends on DB backend, MySQL usually doesn't need explicit drop)
    # op.execute(f"DROP TYPE {status_enum_name}") # Example for PostgreSQL
    # ### end Alembic commands ###
