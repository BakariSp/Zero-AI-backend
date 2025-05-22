import os
import sys
from dotenv import load_dotenv
import logging
import urllib.parse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables - make sure to override any system variables
print("Loading environment variables from .env file...")
load_dotenv(override=True)

# Check if DB_PASSWORD is set
if not os.getenv("DB_PASSWORD"):
    logger.error("DB_PASSWORD environment variable is not set! Please update your .env file.")
    logger.info("You can run 'python test_supabase_pooler.py' to test your connection first.")
    sys.exit(1)

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Get database connection parameters
DB_USER = os.getenv("DB_USER", "postgres.ecwdxlkvqiqyjffcovby")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "aws-0-ap-southeast-1.pooler.supabase.com")
DB_PORT = os.getenv("DB_PORT", "6543")
DB_NAME = os.getenv("DB_NAME", "postgres")

# Log connection attempt without exposing password
logger.info(f"Attempting to connect to PostgreSQL database at {DB_HOST}:{DB_PORT}/{DB_NAME}")

# Import your database configuration and models
try:
    from app.db import Base, engine, test_connection
    import app.models
    import app.user_tasks.models
    import app.backend_tasks.models
except Exception as e:
    logger.error(f"Error importing database modules: {e}")
    sys.exit(1)

def init_database():
    """Initialize the Supabase database by creating all tables defined in models."""
    logger.info("Starting Supabase database initialization...")
    
    try:
        # Test the connection first
        logger.info("Testing database connection...")
        if not test_connection():
            logger.error("Connection test failed. Check your Supabase credentials.")
            return False
        
        # Create all tables defined in models
        logger.info("Connection successful! Creating tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("All tables created successfully!")
        
        return True
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

if __name__ == "__main__":
    logger.info("Initializing Supabase PostgreSQL database...")
    
    # Initialize the database
    if init_database():
        logger.info("Database initialization completed successfully!")
    else:
        logger.error("Database initialization failed!")
        sys.exit(1)
    
    logger.info("Done!") 