import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
import urllib.parse
from dotenv import load_dotenv

# Load environment variables from .env file with override
load_dotenv(override=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get database connection parameters from environment variables
DB_USER = os.getenv("DB_USER", "postgres.ecwdxlkvqiqyjffcovby")
DB_PASSWORD = os.getenv("DB_PASSWORD", "usvWwFHsvcAEymNQ")
DB_HOST = os.getenv("DB_HOST", "aws-0-ap-southeast-1.pooler.supabase.com")
DB_PORT = int(os.getenv("DB_PORT", "6543"))
DB_NAME = os.getenv("DB_NAME", "postgres")

# URL encode the password to handle special characters
ENCODED_PASSWORD = urllib.parse.quote_plus(DB_PASSWORD) if DB_PASSWORD else ""

# IMPORTANT: Force PostgreSQL connection - ignore any DATABASE_URL from env vars
# that might be pointing to MySQL
DATABASE_URL = f"postgresql://{DB_USER}:{ENCODED_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Log connection info (without password)
masked_url = DATABASE_URL.replace(DB_PASSWORD, "*****") if DB_PASSWORD else DATABASE_URL
logger.info(f"Connecting to PostgreSQL database using URL: {masked_url}")

# Extra check to ensure we're using PostgreSQL dialect
if "postgresql://" not in DATABASE_URL:
    logger.error(f"ERROR: Database URL does not use PostgreSQL dialect: {DATABASE_URL.split('://')[0]}")
    logger.error("Forcing PostgreSQL dialect to ensure proper connection")
    # Extract components and rebuild with postgresql:// prefix
    if "://" in DATABASE_URL:
        _, connection_details = DATABASE_URL.split("://", 1)
        DATABASE_URL = f"postgresql://{connection_details}"
        logger.info(f"Updated DATABASE_URL to: {DATABASE_URL.replace(DB_PASSWORD, '*****') if DB_PASSWORD else DATABASE_URL}")

# Create SQLAlchemy engine for PostgreSQL
engine = create_engine(
    DATABASE_URL,
    # Add connection pooling settings appropriate for a connection pooler
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True
)

# Log the actual driver being used
logger.info(f"SQLAlchemy engine dialect: {engine.dialect.name}")
logger.info(f"SQLAlchemy driver: {engine.dialect.driver}")
logger.info("SQLAlchemy engine created with connection pooling for PostgreSQL")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Add dependency for FastAPI to get a database session
def get_db():
    """
    Dependency function to get a database session.
    Yields a session that will be closed after the request is complete.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Initialize the database by creating all tables."""
    try:
        # Create all tables defined in models
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully")
        
        # Test connection
        test_connection()
    except Exception as e:
        print(f"Error initializing database: {e}")

# Add a function to test the connection
def test_connection():
    try:
        # Test SQLAlchemy connection
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            print(f"PostgreSQL connection successful: {result}")
        
        return True
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False

# Add a function to reset the connection pool
def reset_db_pool():
    """
    Dispose of the current connection pool and create a new one.
    This can help fix issues with stale connections.
    """
    global engine
    try:
        # Log current pool status
        logger.info(f"Current connection pool size: {engine.pool.size()}")
        logger.info(f"Current connection overflow: {engine.pool.overflow()}")
        
        # Dispose of all connections in the pool
        engine.dispose()
        logger.info("Connection pool disposed")
        
        # Create a new engine with the same settings
        engine = create_engine(
            DATABASE_URL,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=3600,
            pool_pre_ping=True
        )
        logger.info("New connection pool created")
        
        # Update the sessionmaker to use the new engine
        global SessionLocal
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Test the new connection
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            logger.info(f"New connection test successful: {result}")
        
        return True
    except Exception as e:
        logger.error(f"Error resetting connection pool: {e}")
        return False
