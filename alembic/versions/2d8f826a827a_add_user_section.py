"""add_user_section

Revision ID: 2d8f826a827a
Revises: 149a29d35662
Create Date: 2025-04-15 15:42:19.134631

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d8f826a827a'
down_revision: Union[str, None] = '149a29d35662'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name):
    """Check if a table exists in the database"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    """Upgrade schema."""
    # Disable foreign key checks for MySQL
    op.execute("SET FOREIGN_KEY_CHECKS=0")
    
    # Create user_sections table
    op.create_table('user_sections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('section_template_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['section_template_id'], ['course_sections.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_sections_id'), 'user_sections', ['id'], unique=False)
    
    # Create user_section_cards table
    op.create_table('user_section_cards',
        sa.Column('user_section_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.Column('is_custom', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ),
        sa.ForeignKeyConstraint(['user_section_id'], ['user_sections.id'], ),
        sa.PrimaryKeyConstraint('user_section_id', 'card_id')
    )
    
    # Re-enable foreign key checks
    op.execute("SET FOREIGN_KEY_CHECKS=1")


def downgrade() -> None:
    """Downgrade schema."""
    # Disable foreign key checks for MySQL
    op.execute("SET FOREIGN_KEY_CHECKS=0")
    
    # Drop tables if they exist
    if table_exists('user_section_cards'):
        op.drop_table('user_section_cards')
    if table_exists('user_sections'):
        op.drop_table('user_sections')
    
    # Re-enable foreign key checks
    op.execute("SET FOREIGN_KEY_CHECKS=1")
