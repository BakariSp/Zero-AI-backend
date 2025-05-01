from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
import ssl

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

# Get SSL certificate path
SSL_CERT = os.path.join(os.getcwd(), "DigiCertGlobalRootCA.crt.pem")
if not os.path.exists(SSL_CERT):
    raise ValueError(f"SSL certificate not found at {SSL_CERT}")

# Create SSL context
ssl_context = ssl.create_default_context(cafile=SSL_CERT)
ssl_args = {'ssl': ssl_context}

# Modify DATABASE_URL to include SSL
if 'mysql' in DATABASE_URL:
    if '?' in DATABASE_URL:
        DATABASE_URL += "&ssl_ca=" + SSL_CERT
    else:
        DATABASE_URL += "?ssl_ca=" + SSL_CERT

print(f"Connecting to database...")
engine = create_engine(DATABASE_URL, connect_args=ssl_args)

# Check if the column already exists
with engine.connect() as connection:
    # Check if subscription_type column exists
    result = connection.execute(text("""
        SELECT COUNT(*) as count
        FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE()
        AND TABLE_NAME = 'users' 
        AND COLUMN_NAME = 'subscription_type'
    """))
    column_exists = result.scalar() > 0
    
    if column_exists:
        print("The 'subscription_type' column already exists in the users table.")
    else:
        # Add the subscription_type column
        print("Adding 'subscription_type' column to the users table...")
        connection.execute(text("""
            ALTER TABLE users 
            ADD COLUMN subscription_type VARCHAR(20) DEFAULT 'free'
        """))
        connection.commit()
        print("Column added successfully!")

print("Done.") 