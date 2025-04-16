import os
import mysql.connector
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import pymysql

# EXPLICITLY set the username without the server suffix
DB_USER = "fmqfmvlobx"  # Hardcoded without server suffix
DB_PASSWORD = os.getenv("DB_PASSWORD", "zero-ai0430")
DB_HOST = os.getenv("DB_HOST", "zero-ai-server.mysql.database.azure.com")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "zero-ai-database")
SSL_CA = os.path.abspath(os.getenv("SSL_CA", "DigiCertGlobalRootCA.crt.pem"))

# Create MySQL connection - using the format that worked in cloudshell
def get_mysql_connection():
    return mysql.connector.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        ssl_ca=SSL_CA,
        ssl_disabled=False
    )

# For SQLAlchemy, create a connection string that works with the same parameters
engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
    connect_args={
        "ssl": {"ca": SSL_CA}
    }
)

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
        # Try direct MySQL connector first
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        print(f"MySQL Connector connection successful: {result}")
        
        # Then try SQLAlchemy
        with engine.connect() as connection:
            result = connection.execute("SELECT 1").scalar()
            print(f"SQLAlchemy connection successful: {result}")
        
        return True
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False
