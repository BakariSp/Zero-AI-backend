"""add answer, difficulty to cards and modify keyword nullability

Revision ID: 67dbb635f1d2
Revises: 77890b7ddf69
Create Date: 2025-04-19 23:44:21.309288

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '67dbb635f1d2'
down_revision: Union[str, None] = '77890b7ddf69'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- Columns 'answer' and 'difficulty' already exist, so DO NOT add them ---
    # op.add_column('cards', sa.Column('answer', sa.Text(), nullable=True))
    # op.add_column('cards', sa.Column('difficulty', sa.String(length=50), nullable=True))

    # --- Populate existing rows before making columns NOT NULL ---
    # You MUST populate existing NULL values before changing nullable=False.
    # Example: Set default empty string for 'answer' for existing rows
    # Ensure this runs only if 'answer' might have NULLs you want to change
    op.execute("UPDATE cards SET answer = '' WHERE answer IS NULL")
    # Example: Set default 'intermediate' for 'difficulty' for existing rows
    # op.execute("UPDATE cards SET difficulty = 'intermediate' WHERE difficulty IS NULL") # Keep difficulty nullable


    # --- Modify columns to match the model (if necessary) ---
    # Modify 'answer' nullability (if it's currently nullable=True in DB)
    op.alter_column('cards', 'answer',
               existing_type=sa.Text(),
               nullable=False) # Model requires False
    # Modify 'keyword' nullability (if it's currently nullable=True in DB)
    op.alter_column('cards', 'keyword',
               existing_type=sa.String(length=255),
               nullable=False) # Model requires False
    # Note: 'difficulty' remains nullable=True as per the model, so no alter needed unless type is wrong


def downgrade() -> None:
    """Downgrade schema."""
    # Revert 'keyword' nullability
    op.alter_column('cards', 'keyword',
               existing_type=sa.String(length=255),
               nullable=True) # Revert to previous state (likely nullable=True based on DESCRIBE)
    # Revert 'answer' nullability
    op.alter_column('cards', 'answer',
               existing_type=sa.Text(),
               nullable=True) # Revert to previous state (likely nullable=True based on DESCRIBE)

    # --- DO NOT drop columns 'answer' and 'difficulty' as this migration didn't add them ---
    # op.drop_column('cards', 'difficulty')
    # op.drop_column('cards', 'answer')
    # The 'question' column should be dropped in the downgrade of its own migration file
