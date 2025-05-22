import os
import sys
import psycopg2
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
import time
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
load_dotenv()

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import your database configuration
from app.db import SessionLocal

def get_database_url():
    """Get the database URL from environment variables"""
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    
    # Return the database URL for PostgreSQL
    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

def clean_database_with_direct_sql():
    """Clean database using direct SQL commands - most reliable method"""
    print("Starting database cleanup using direct SQL...")
    
    # Create SQLAlchemy engine and session
    database_url = get_database_url()
    print(f"Using database: {database_url}")
    
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Disable foreign key checks for PostgreSQL
        session.execute(text("SET session_replication_role = 'replica';"))
        
        # Get all tables except users and alembic_version
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        tables_to_clean = [t for t in all_tables if t != 'users' and t != 'alembic_version']
        
        # Truncate all tables except users and alembic_version
        for table in tables_to_clean:
            print(f"\nTruncating table {table}...")
            try:
                # PostgreSQL syntax for truncate
                session.execute(text(f'TRUNCATE TABLE "{table}" CASCADE;'))
            except Exception as e:
                print(f"Error truncating {table}: {e}")
                print("Trying DELETE instead...")
                try:
                    session.execute(text(f'DELETE FROM "{table}";'))
                except Exception as e2:
                    print(f"Error deleting from {table}: {e2}")
        
        # Commit the changes
        session.commit()
        
        # Re-enable foreign key checks
        session.execute(text("SET session_replication_role = 'origin';"))
        session.commit()
        
        print("\nDatabase cleanup completed!")
        
    except Exception as e:
        session.rollback()
        print(f"Error during database cleanup: {e}")
    finally:
        session.close() 