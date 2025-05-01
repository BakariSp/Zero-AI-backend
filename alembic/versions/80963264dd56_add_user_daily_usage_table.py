"""add_user_daily_usage_table

Revision ID: 80963264dd56
Revises: 4e2d56a04892
Create Date: 2025-04-30 19:29:07.557583

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func


# revision identifiers, used by Alembic.
revision: str = '80963264dd56'
down_revision: Union[str, None] = '4e2d56a04892'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create user_daily_usage table to track daily generation of paths and cards
    op.create_table('user_daily_usage',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('usage_date', sa.Date(), nullable=False, server_default=sa.text('(CURRENT_DATE)')),
        sa.Column('paths_generated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cards_generated', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('paths_daily_limit', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('cards_daily_limit', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'usage_date', name='uix_user_daily_usage')
    )
    
    # Add indexes for performance
    op.create_index(op.f('ix_user_daily_usage_id'), 'user_daily_usage', ['id'], unique=False)
    op.create_index(op.f('ix_user_daily_usage_user_id'), 'user_daily_usage', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_daily_usage_usage_date'), 'user_daily_usage', ['usage_date'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes first
    op.drop_index(op.f('ix_user_daily_usage_usage_date'), table_name='user_daily_usage')
    op.drop_index(op.f('ix_user_daily_usage_user_id'), table_name='user_daily_usage')
    op.drop_index(op.f('ix_user_daily_usage_id'), table_name='user_daily_usage')
    
    # Drop the table
    op.drop_table('user_daily_usage')
