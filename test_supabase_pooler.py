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

# Pooler connection information - Note the updated format with project ID
DB_USER = "postgres.ecwdxlkvqiqyjffcovby"  # Format: postgres.<project_id>
DB_PASSWORD = "usvWwFHsvcAEymNQ"  # Your Supabase password
DB_HOST = "aws-0-ap-southeast-1.pooler.supabase.com"
DB_PORT = 6543
DB_NAME = "postgres"

# Create connection string
CONNECTION_STRING = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Test with psycopg2
def test_psycopg2_connection():
    logger.info("Testing direct psycopg2 connection to Supabase Transaction Pooler...")
    try:
        # Connect using connection string
        conn = psycopg2.connect(CONNECTION_STRING)
        
        # Test the connection with a simple query
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        logger.info(f"psycopg2 connection successful: {result}")
        return True
    except Exception as e:
        logger.error(f"psycopg2 connection failed: {e}")
        logger.error(f"If you see 'could not translate host name', this might be a DNS issue")
        logger.error(f"If you see 'Tenant or user not found', check your username format: postgres.<project_id>")
        return False

# Test with SQLAlchemy
def test_sqlalchemy_connection():
    logger.info("Testing SQLAlchemy connection to Supabase Transaction Pooler...")
    try:
        # Connect using SQLAlchemy
        engine = create_engine(CONNECTION_STRING)
        
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            logger.info(f"SQLAlchemy connection successful: {result}")
        
        return True
    except Exception as e:
        logger.error(f"SQLAlchemy connection failed: {e}")
        return False

if __name__ == "__main__":
    print("=================================================")
    print("TESTING SUPABASE TRANSACTION POOLER CONNECTION")
    print("=================================================")
    print(f"Connection String: postgresql://{DB_USER}:****@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print("=================================================")
    
    # Test with psycopg2
    psycopg2_result = test_psycopg2_connection()
    
    # Test with SQLAlchemy
    sqlalchemy_result = test_sqlalchemy_connection()
    
    if psycopg2_result or sqlalchemy_result:
        print("\n✅ SUCCESS: Connection to Supabase Transaction Pooler worked!")
        print("\nNext steps:")
        print("1. Your connection works! Keep your .env and alembic.ini as they are now")
        print("2. Run the database initialization:")
        print("   python init_supabase_db.py")
    else:
        print("\n❌ FAILED: Could not connect to Supabase Transaction Pooler.")
        print("\nTroubleshooting steps:")
        print("1. Verify you've added your IP to Supabase Network Restrictions:")
        print("   https://supabase.com/dashboard/project/ecwdxlkvqiqyjffcovby/settings/database")
        print(f"2. Your IPv4 address is: {os.popen('curl -s https://api.ipify.org').read()}")
        print("3. Check if your network/firewall allows outbound connections to port 6543")
        print("4. Make sure your username is in the correct format: postgres.<project_id>") 