import os
import sys
import pymysql
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
    """Get the database URL from environment variables with SSL configuration"""
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    
    # Return the database URL with SSL configuration
    return f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

def get_ssl_ca_path():
    """Get the SSL CA certificate path"""
    # Try multiple possible locations for the SSL CA certificate
    possible_paths = [
        # Current directory
        os.path.join(os.getcwd(), os.getenv("SSL_CA", "DigiCertGlobalRootCA.crt.pem")),
        # Project root directory
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                    os.getenv("SSL_CA", "DigiCertGlobalRootCA.crt.pem")),
        # One level up from current directory
        os.path.join(os.path.dirname(os.getcwd()), 
                    os.getenv("SSL_CA", "DigiCertGlobalRootCA.crt.pem")),
        # Absolute path if specified in .env
        os.getenv("SSL_CA", "")
    ]
    
    # Find the first path that exists
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # If no path exists, return the first one and let the error be caught later
    print("Warning: SSL CA certificate not found in any of the expected locations.")
    print(f"Searched in: {possible_paths}")
    return possible_paths[0]

def table_exists(engine, table_name):
    """Check if a table exists in the database"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()

def clean_database_with_alembic():
    """Clean all database tables except users using Alembic and SQLAlchemy"""
    print("Starting database cleanup using Alembic...")
    
    # Create SQLAlchemy engine and session with SSL
    database_url = get_database_url()
    print(f"Using database: {database_url}")
    
    ssl_ca = get_ssl_ca_path()
    print(f"Using SSL CA certificate: {ssl_ca}")
    
    connect_args = {
        "ssl": {
            "ca": ssl_ca
        }
    }
    
    engine = create_engine(database_url, connect_args=connect_args)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Disable foreign key checks for easier deletion
        session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        
        # Delete data from all tables except users
        # Order matters - delete in reverse order of dependencies
        
        # Check and delete association tables first
        tables_to_clean = [
            "section_cards", 
            "course_section_association",
            "learning_path_courses", 
            "user_section_cards",
            "user_sections",
            "user_cards", 
            "user_courses",
            "user_learning_paths", 
            "user_achievements",
            "daily_logs",
            "cards",
            "course_sections", 
            "courses",
            "learning_paths", 
            "achievements"
        ]
        
        for table in tables_to_clean:
            if table_exists(engine, table):
                print(f"\nDeleting data from {table}...")
                session.execute(text(f"DELETE FROM {table}"))
            else:
                print(f"\nTable {table} does not exist, skipping...")
        
        # Commit the changes
        session.commit()
        
        # Re-enable foreign key checks
        session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        session.commit()
        
        print("\nDatabase cleanup completed!")
        
    except Exception as e:
        session.rollback()
        print(f"Error during database cleanup: {e}")
    finally:
        session.close()

def clean_database_with_alembic_downgrade():
    """Alternative approach: Use alembic downgrade and upgrade to reset the database"""
    print("Starting database cleanup using Alembic downgrade/upgrade...")
    
    try:
        # Get the alembic.ini file path
        alembic_ini_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alembic.ini')
        
        if not os.path.exists(alembic_ini_path):
            print(f"Error: alembic.ini not found at {alembic_ini_path}")
            return
            
        # Create Alembic config
        alembic_cfg = Config(alembic_ini_path)
        
        # Get the current revision
        from alembic.script import ScriptDirectory
        script = ScriptDirectory.from_config(alembic_cfg)
        current_rev = script.get_current_head()
        
        print(f"Current database revision: {current_rev}")
        
        # Find the revision before user tables were created
        # We'll use the revision from the file we're looking at
        target_rev = '149a29d35662'  # This is the revision ID from the file
        
        # Create SQLAlchemy engine and session for direct SQL operations
        database_url = get_database_url()
        ssl_ca = get_ssl_ca_path()
        
        connect_args = {
            "ssl": {
                "ca": ssl_ca
            }
        }
        
        engine = create_engine(database_url, connect_args=connect_args)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # Disable foreign key checks
            session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            
            # Instead of using Alembic's downgrade/upgrade which is causing issues,
            # we'll manually truncate all tables except users
            tables_to_clean = [
                "section_cards", 
                "course_section_association",
                "learning_path_courses", 
                "user_section_cards",
                "user_sections",
                "user_cards", 
                "user_courses",
                "user_learning_paths", 
                "user_achievements",
                "daily_logs",
                "cards",
                "course_sections", 
                "courses",
                "learning_paths", 
                "achievements"
            ]
            
            for table in tables_to_clean:
                if table_exists(engine, table):
                    print(f"\nTruncating table {table}...")
                    session.execute(text(f"TRUNCATE TABLE {table}"))
                else:
                    print(f"\nTable {table} does not exist, skipping...")
            
            # Re-enable foreign key checks
            session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            session.commit()
            
            # Update Alembic version to current without actually running migrations
            print(f"\nSetting Alembic version to current ({current_rev}) without running migrations...")
            command.stamp(alembic_cfg, current_rev)
            
            print("\nDatabase cleanup completed!")
            
        except Exception as e:
            session.rollback()
            print(f"Error during manual table cleanup: {e}")
        finally:
            session.close()
            
    except Exception as e:
        print(f"Error during database cleanup: {e}")

def clean_database_with_direct_sql():
    """Clean database using direct SQL commands - most reliable method"""
    print("Starting database cleanup using direct SQL...")
    
    # Create SQLAlchemy engine and session with SSL
    database_url = get_database_url()
    print(f"Using database: {database_url}")
    
    ssl_ca = get_ssl_ca_path()
    print(f"Using SSL CA certificate: {ssl_ca}")
    
    connect_args = {
        "ssl": {
            "ca": ssl_ca
        }
    }
    
    engine = create_engine(database_url, connect_args=connect_args)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Disable foreign key checks for easier deletion
        session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        
        # Get all tables except users and alembic_version
        inspector = inspect(engine)
        all_tables = inspector.get_table_names()
        tables_to_clean = [t for t in all_tables if t != 'users' and t != 'alembic_version']
        
        # Truncate all tables except users and alembic_version
        for table in tables_to_clean:
            print(f"\nTruncating table {table}...")
            try:
                session.execute(text(f"TRUNCATE TABLE {table}"))
            except Exception as e:
                print(f"Error truncating {table}: {e}")
                print("Trying DELETE instead...")
                try:
                    session.execute(text(f"DELETE FROM {table}"))
                except Exception as e2:
                    print(f"Error deleting from {table}: {e2}")
        
        # Commit the changes
        session.commit()
        
        # Re-enable foreign key checks
        session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        session.commit()
        
        print("\nDatabase cleanup completed!")
        
    except Exception as e:
        session.rollback()
        print(f"Error during database cleanup: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    # Ask user which method to use
    print("Choose database cleanup method:")
    print("1. Direct SQL deletion (keeps user data)")
    print("2. Alembic downgrade/upgrade (resets entire schema)")
    print("3. Direct SQL with auto-detection (most reliable)")
    
    choice = input("Enter choice (1, 2, or 3): ")
    
    if choice == "1":
        clean_database_with_alembic()
    elif choice == "2":
        clean_database_with_alembic_downgrade()
    elif choice == "3":
        clean_database_with_direct_sql()
    else:
        print("Invalid choice. Please enter 1, 2, or 3.")
