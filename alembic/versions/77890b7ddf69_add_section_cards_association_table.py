"""Add section_cards association table

Revision ID: 77890b7ddf69
Revises: 4efe243b309e
Create Date: 2025-04-19 18:29:26.720976

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '77890b7ddf69'
down_revision: Union[str, None] = '4efe243b309e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Add 'question' column ---
    op.add_column('cards', sa.Column('question', sa.Text(), nullable=True))

    # --- Populate existing rows ---
    # Set default empty string for 'question' for existing rows
    op.execute("UPDATE cards SET question = '' WHERE question IS NULL")

    # --- Modify 'question' to be NOT NULL ---
    op.alter_column('cards', 'question',
               existing_type=sa.Text(),
               nullable=False)

    # --- Keep any other operations originally in this migration ---
    # Example: If this migration also added the section_cards table
    # op.create_table('section_cards',
    #     sa.Column('section_id', sa.Integer(), nullable=False),
    #     sa.Column('card_id', sa.Integer(), nullable=False),
    #     sa.Column('order_index', sa.Integer(), nullable=True),
    #     sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ),
    #     sa.ForeignKeyConstraint(['section_id'], ['course_sections.id'], ),
    #     sa.PrimaryKeyConstraint('section_id', 'card_id')
    # )
    # ### end Alembic commands ###


def downgrade() -> None:
    # --- Revert 'question' column changes ---
    # Revert nullability first
    op.alter_column('cards', 'question',
               existing_type=sa.Text(),
               nullable=True)
    # Drop the column
    op.drop_column('cards', 'question')

    # --- Keep any other downgrade operations originally here ---
    # Example: Drop section_cards table
    # op.drop_table('section_cards')
    # ### end Alembic commands ###