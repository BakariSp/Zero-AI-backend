"""Add progress column to user_sections table

Revision ID: add_progress_to_user_sections
Revises: f51d88681e18
Create Date: 2023-07-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_progress_to_user_sections'
down_revision = 'f51d88681e18'  # This should be the current head from alembic current
branch_labels = None
depends_on = None


def upgrade():
    # Add progress column to user_sections table
    op.add_column('user_sections', sa.Column('progress', sa.Float(), nullable=False, server_default='0.0'))


def downgrade():
    # Remove progress column from user_sections table
    op.drop_column('user_sections', 'progress') 