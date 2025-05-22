import os
import psycopg2
import logging
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get the actual Supabase password from the user
password = input("Enter your Supabase password: ")

# Direct connection string format
CONNECTION_STRING = f"postgresql://postgres:{password}@db.ecwdxlkvqiqyjffcovby.supabase.co:5432/postgres"

# Test direct psycopg2 connection
def test_psycopg2_connection():
    logger.info("Testing direct psycopg2 connection to Supabase...")
    try:
        conn = psycopg2.connect(CONNECTION_STRING)
        
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        logger.info(f"psycopg2 connection successful: {result}")
        return True
    except Exception as e:
        logger.error(f"psycopg2 connection failed: {e}")
        return False

# Test SQLAlchemy connection
def test_sqlalchemy_connection():
    logger.info("Testing SQLAlchemy connection to Supabase...")
    try:
        # Hide the password in logs
        masked_connection = CONNECTION_STRING.replace(password, "********")
        logger.info(f"Connection string (masked): {masked_connection}")
        
        engine = create_engine(CONNECTION_STRING)
        
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            logger.info(f"SQLAlchemy connection successful: {result}")
        
        return True
    except Exception as e:
        logger.error(f"SQLAlchemy connection failed: {e}")
        return False

if __name__ == "__main__":
    print("=== TESTING DIRECT CONNECTION TO SUPABASE ===")
    
    # Test with psycopg2
    psycopg2_result = test_psycopg2_connection()
    
    # Test with SQLAlchemy
    sqlalchemy_result = test_sqlalchemy_connection()
    
    if psycopg2_result or sqlalchemy_result:
        print("\n✅ SUCCESS: Connection to Supabase PostgreSQL worked!")
        print("\nNext steps:")
        print("1. Add your password to .env file:")
        print("   DB_PASSWORD=your_actual_password")
        print("\n2. Update alembic.ini:")
        print("   sqlalchemy.url = postgresql://postgres:your_actual_password@db.ecwdxlkvqiqyjffcovby.supabase.co:5432/postgres")
        print("\n3. Run the database initialization:")
        print("   python init_supabase_db.py")
    else:
        print("\n❌ FAILED: Could not connect to Supabase with any method.")
        print("Make sure your password is correct and that your IP address is allowed to connect.") 