"""add_promotion_code_usage_table

Revision ID: ac87a5d3e92f
Revises: 9582a472e65f
Create Date: 2023-09-01 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision = 'ac87a5d3e92f'
down_revision = '9582a472e65f'  # Update this to the most recent revision ID
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()
    
    # Only create the table if it doesn't exist
    if 'promotion_code_usage' not in tables:
        # Create promotion_code_usage table
        op.create_table(
            'promotion_code_usage',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('code', sa.String(50), nullable=False, index=True),
            sa.Column('tier', sa.String(20), nullable=False),
            sa.Column('total_limit', sa.Integer(), nullable=False),
            sa.Column('times_used', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('code')
        )
    
    # Check if we need to initialize the promotion codes
    has_data = conn.execute("SELECT COUNT(*) FROM promotion_code_usage").scalar() > 0
    
    # Initialize with existing promotion codes if table is empty
    if not has_data:
        op.execute(
            """
            INSERT INTO promotion_code_usage (code, tier, total_limit, times_used)
            VALUES 
            ('zeroai#0430', 'standard', 200, 0),
            ('zeroultra#2025', 'premium', 100, 0)
            """
        )


def downgrade():
    # We won't drop the table if we're now making creation conditional
    # Just a safety measure to avoid accidental data loss
    pass 