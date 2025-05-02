"""add_user_terms_acceptance_table

Revision ID: ee045e8ca546
Revises: 31660d552ec3
Create Date: 2025-05-01 12:13:52.909793

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = 'ee045e8ca546'
down_revision: Union[str, None] = '31660d552ec3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create user_terms_acceptance table."""
    op.create_table(
        'user_terms_acceptance',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('terms_version', sa.String(10), nullable=False),
        sa.Column('signed_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.Index('ix_user_terms_acceptance_id', 'id')
    )


def downgrade() -> None:
    """Drop user_terms_acceptance table."""
    op.drop_table('user_terms_acceptance')
