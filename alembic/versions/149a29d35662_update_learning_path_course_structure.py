"""update_learning_path_course_structure

Revision ID: 149a29d35662
Revises: 12eb81c8bf58
Create Date: 2025-04-15 15:20:53.732622

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship

# revision identifiers, used by Alembic.
revision: str = '149a29d35662'
down_revision: Union[str, None] = '12eb81c8bf58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name):
    """Check if a table exists in the database"""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # Disable foreign key checks for MySQL
    op.execute("SET FOREIGN_KEY_CHECKS=0")
    
    # Save user data if users table exists
    if table_exists('users'):
        op.execute("CREATE TEMPORARY TABLE temp_users AS SELECT * FROM users")
    
    # Drop existing tables if they exist
    tables_to_drop = [
        'user_achievements', 'user_cards', 'user_learning_paths', 
        'user_courses', 'daily_logs', 'course_sections', 'cards', 
        'achievements', 'learning_path_courses', 'course_section_association',
        'learning_paths', 'courses'
    ]
    
    for table in tables_to_drop:
        if table_exists(table):
            op.drop_table(table)
    
    # Drop users table last (after we've saved the data)
    if table_exists('users'):
        op.drop_table('users')
    
    # Create new tables
    
    # Users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('username', sa.String(length=50), nullable=True),
        sa.Column('hashed_password', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('oauth_provider', sa.String(length=50), nullable=True),
        sa.Column('oauth_id', sa.String(length=255), nullable=True),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('profile_picture', sa.String(length=255), nullable=True),
        sa.Column('interests', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    
    # Restore user data if we saved it
    if table_exists('temp_users'):
        op.execute("INSERT INTO users SELECT * FROM temp_users")
        op.execute("DROP TABLE temp_users")
    
    # Learning paths table
    op.create_table('learning_paths',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('difficulty_level', sa.String(length=50), nullable=True),
        sa.Column('estimated_days', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_template', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_learning_paths_category'), 'learning_paths', ['category'], unique=False)
    op.create_index(op.f('ix_learning_paths_id'), 'learning_paths', ['id'], unique=False)
    op.create_index(op.f('ix_learning_paths_title'), 'learning_paths', ['title'], unique=False)
    
    # Courses table
    op.create_table('courses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('estimated_days', sa.Integer(), nullable=True),
        sa.Column('is_template', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_courses_id'), 'courses', ['id'], unique=False)
    op.create_index(op.f('ix_courses_title'), 'courses', ['title'], unique=False)
    
    # Course sections table
    op.create_table('course_sections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('learning_path_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=True),
        sa.Column('estimated_days', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_template', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['learning_path_id'], ['learning_paths.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_course_sections_id'), 'course_sections', ['id'], unique=False)
    
    # Cards table
    op.create_table('cards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('keyword', sa.String(length=255), nullable=True),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('resources', sa.JSON(), nullable=True),
        sa.Column('level', sa.String(length=20), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cards_id'), 'cards', ['id'], unique=False)
    op.create_index(op.f('ix_cards_keyword'), 'cards', ['keyword'], unique=False)
    
    # Section-Card association table
    op.create_table('section_cards',
        sa.Column('section_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ),
        sa.ForeignKeyConstraint(['section_id'], ['course_sections.id'], ),
        sa.PrimaryKeyConstraint('section_id', 'card_id')
    )
    
    # Achievements table
    op.create_table('achievements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('badge_image', sa.String(length=255), nullable=True),
        sa.Column('achievement_type', sa.String(length=50), nullable=True),
        sa.Column('criteria', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_achievements_id'), 'achievements', ['id'], unique=False)
    
    # Daily logs table
    op.create_table('daily_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('log_date', sa.DateTime(), nullable=True),
        sa.Column('completed_sections', sa.JSON(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('study_time_minutes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_daily_logs_id'), 'daily_logs', ['id'], unique=False)
    
    # Association tables
    op.create_table('course_section_association',
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('section_id', sa.Integer(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
        sa.ForeignKeyConstraint(['section_id'], ['course_sections.id'], ),
        sa.PrimaryKeyConstraint('course_id', 'section_id')
    )
    
    op.create_table('learning_path_courses',
        sa.Column('learning_path_id', sa.Integer(), nullable=False),
        sa.Column('course_id', sa.Integer(), nullable=False),
        sa.Column('order_index', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
        sa.ForeignKeyConstraint(['learning_path_id'], ['learning_paths.id'], ),
        sa.PrimaryKeyConstraint('learning_path_id', 'course_id')
    )
    
    op.create_table('user_achievements',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('achievement_id', sa.Integer(), nullable=False),
        sa.Column('achieved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['achievement_id'], ['achievements.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'achievement_id')
    )
    
    op.create_table('user_cards',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('is_completed', sa.Boolean(), nullable=True),
        sa.Column('expanded_example', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('saved_at', sa.DateTime(), nullable=True),
        sa.Column('difficulty_rating', sa.Integer(), nullable=True),
        sa.Column('depth_preference', sa.String(length=20), nullable=True),
        sa.Column('recommended_by', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('user_id', 'card_id')
    )
    
    op.create_table('user_courses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('course_id', sa.Integer(), nullable=True),
        sa.Column('progress', sa.Float(), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_courses_id'), 'user_courses', ['id'], unique=False)
    
    op.create_table('user_learning_paths',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('learning_path_id', sa.Integer(), nullable=True),
        sa.Column('progress', sa.Float(), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['learning_path_id'], ['learning_paths.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_learning_paths_id'), 'user_learning_paths', ['id'], unique=False)
    
    # Re-enable foreign key checks
    op.execute("SET FOREIGN_KEY_CHECKS=1")


def downgrade() -> None:
    # This is a major restructuring, so the downgrade path is complex
    # For simplicity, we'll just drop all tables
    op.execute("SET FOREIGN_KEY_CHECKS=0")
    
    tables_to_drop = [
        'user_learning_paths', 'user_courses', 'user_cards', 'user_achievements',
        'learning_path_courses', 'course_section_association', 'section_cards', 'daily_logs',
        'cards', 'course_sections', 'achievements', 'courses', 'learning_paths',
        'users'
    ]
    
    for table in tables_to_drop:
        if table_exists(table):
            op.drop_table(table)
    
    op.execute("SET FOREIGN_KEY_CHECKS=1")
