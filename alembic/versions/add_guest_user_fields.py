"""Add guest user fields

Revision ID: 53f7cb651d97
Revises: f51d88681e18
Create Date: 2023-05-12 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import text


# revision identifiers, used by Alembic.
revision = '53f7cb651d97'
down_revision = 'f51d88681e18'  # Update this to your actual latest migration
branch_labels = None
depends_on = None


def upgrade():
    # Add guest user fields to the users table
    op.add_column('users', sa.Column('is_guest', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('merged_into_user_id', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('last_active_at', sa.DateTime(), server_default=text('CURRENT_TIMESTAMP'), nullable=True))
    
    # Create an index on is_guest for better query performance
    op.create_index(op.f('ix_users_is_guest'), 'users', ['is_guest'], unique=False)
    
    # Create an index on last_active_at to support cleaning up inactive guest users
    op.create_index(op.f('ix_users_last_active_at'), 'users', ['last_active_at'], unique=False)
    
    # Create foreign key constraint for merged_into_user_id
    op.create_foreign_key(
        'fk_users_merged_into_user_id',
        'users', 'users',
        ['merged_into_user_id'], ['id'],
        ondelete='SET NULL'
    )


def downgrade():
    # Drop foreign key constraint first
    op.drop_constraint('fk_users_merged_into_user_id', 'users', type_='foreignkey')
    
    # Drop indexes
    op.drop_index(op.f('ix_users_last_active_at'), table_name='users')
    op.drop_index(op.f('ix_users_is_guest'), table_name='users')
    
    # Drop the columns
    op.drop_column('users', 'last_active_at')
    op.drop_column('users', 'merged_into_user_id')
    op.drop_column('users', 'is_guest') 