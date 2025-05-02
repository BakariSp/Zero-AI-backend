"""Add interest_learning_path_recommendation table

Revision ID: f51d88681e18
Revises: ee045e8ca546
Create Date: 2025-05-01 13:12:02.259015

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'f51d88681e18'
down_revision: Union[str, None] = 'ee045e8ca546'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the interest_learning_path_recommendation table
    op.create_table(
        'interest_learning_path_recommendation',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('interest_id', sa.String(50), nullable=False, index=True),
        sa.Column('learning_path_id', sa.Integer(), nullable=False, index=True),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['learning_path_id'], ['learning_paths.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_interest_learning_path_recommendation_id', 'interest_learning_path_recommendation', ['id'], unique=False)
    op.create_index('ix_interest_learning_path_recommendation_interest_id', 'interest_learning_path_recommendation', ['interest_id'], unique=False)
    op.create_index('ix_interest_learning_path_recommendation_learning_path_id', 'interest_learning_path_recommendation', ['learning_path_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop the interest_learning_path_recommendation table
    op.drop_table('interest_learning_path_recommendation')
