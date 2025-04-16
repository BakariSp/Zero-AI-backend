"""refactor_cards_table

Revision ID: 12eb81c8bf58
Revises: 389b22e2c163
Create Date: 2025-04-15 15:03:05.178337

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '12eb81c8bf58'
down_revision: Union[str, None] = '389b22e2c163'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop existing tables if they exist
    op.execute("DROP TABLE IF EXISTS user_cards")
    op.execute("DROP TABLE IF EXISTS cards")
    
    # Create cards table with new schema
    op.create_table(
        'cards',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('keyword', sa.String(255), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('resources', sa.JSON(), nullable=True),
        sa.Column('level', sa.String(20), nullable=True, server_default='basic'),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), 
                  onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cards_keyword', 'cards', ['keyword'])
    
    # Create user_cards table with new schema
    op.create_table(
        'user_cards',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('is_completed', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('expanded_example', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('saved_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('difficulty_rating', sa.Integer(), nullable=True),
        sa.Column('depth_preference', sa.String(20), nullable=True),
        sa.Column('recommended_by', sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'card_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables
    op.drop_table('user_cards')
    op.drop_table('cards')
    
    # Recreate original cards table
    op.create_table(
        'cards',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('section_id', sa.Integer(), nullable=True),
        sa.Column('keyword', sa.String(255), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('example', sa.Text(), nullable=True),
        sa.Column('resources', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), 
                  onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cards_keyword', 'cards', ['keyword'])
    
    # Recreate original user_cards table
    op.create_table(
        'user_cards',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('is_completed', sa.Boolean(), nullable=True, server_default='0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('saved_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'card_id')
    )
