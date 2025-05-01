"""add_subscription_dates_to_users

Revision ID: 9582a472e65f
Revises: 80963264dd56
Create Date: 2023-08-30 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9582a472e65f'
down_revision = '80963264dd56'  # Update this to the most recent revision ID
branch_labels = None
depends_on = None


def upgrade():
    # Add subscription_start_date and subscription_expiry_date columns to users table
    op.add_column('users', sa.Column('subscription_start_date', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('subscription_expiry_date', sa.DateTime(), nullable=True))


def downgrade():
    # Remove subscription_start_date and subscription_expiry_date columns from users table
    op.drop_column('users', 'subscription_expiry_date')
    op.drop_column('users', 'subscription_start_date') 