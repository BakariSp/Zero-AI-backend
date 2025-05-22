import os
from dotenv import load_dotenv
import urllib.parse

# Load environment variables - make sure this happens before accessing env vars
print("Loading environment variables from .env file...")
load_dotenv(override=True)  # override=True ensures .env takes precedence over system environment variables

# Get database connection parameters
DB_USER = os.getenv("DB_USER", "default-user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "default-password")
DB_HOST = os.getenv("DB_HOST", "default-host")
DB_PORT = os.getenv("DB_PORT", "default-port")
DB_NAME = os.getenv("DB_NAME", "default-db")
DATABASE_URL = os.getenv("DATABASE_URL", "default-url")

# Print them (mask password)
masked_password = "********" if DB_PASSWORD else "not-set"
masked_url = DATABASE_URL.replace(DB_PASSWORD, "********") if DB_PASSWORD and DB_PASSWORD in DATABASE_URL else DATABASE_URL

print("=== DATABASE CONNECTION PARAMETERS ===")
print(f"DB_USER: {DB_USER}")
print(f"DB_PASSWORD: {masked_password}")
print(f"DB_HOST: {DB_HOST}")
print(f"DB_PORT: {DB_PORT}")
print(f"DB_NAME: {DB_NAME}")
print(f"DATABASE_URL: {masked_url}")

# Check if the DATABASE_URL is being constructed correctly in app/db.py
encoded_password = urllib.parse.quote_plus(DB_PASSWORD) if DB_PASSWORD else ""
constructed_url = f"postgresql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
masked_constructed_url = constructed_url.replace(encoded_password, "********") if encoded_password else constructed_url

print("\n=== CONSTRUCTED DATABASE URL ===")
print(f"Encoded Password: {'(encoded, masked)' if encoded_password else 'not-set'}")
print(f"Constructed URL: {masked_constructed_url}")

print("\n=== ENVIRONMENT CHECK ===")
if "mysql" in DB_HOST.lower():
    print("⚠️ WARNING: DB_HOST still contains 'mysql' - this might be the old Azure MySQL host")
    
if "mysql" in DATABASE_URL.lower():
    print("⚠️ WARNING: DATABASE_URL still contains 'mysql' - this might be pointing to Azure MySQL")
    
if "supabase" in DB_HOST.lower() or "pooler.supabase.com" in DB_HOST.lower():
    print("✅ DB_HOST contains 'supabase' - this looks correct")
    
if "supabase" in DATABASE_URL.lower() or "pooler.supabase.com" in DATABASE_URL.lower():
    print("✅ DATABASE_URL contains 'supabase' - this looks correct")
    
if constructed_url != DATABASE_URL and encoded_password:
    print("⚠️ WARNING: Constructed URL does not match DATABASE_URL in environment")
    print("   This suggests the environment variables might not be loaded correctly") 

# Check AI service configuration
print("\n=== AI SERVICE CONFIGURATION ===")
# Check if Zhipu AI is enabled
USE_ZHIPU_AI = os.getenv("USE_ZHIPU_AI", "false").lower() == "true"
if USE_ZHIPU_AI:
    print("✓ Zhipu AI (GLM-4) is ENABLED")
    # Check Zhipu AI configuration
    ZHIPU_AI_API_KEY = os.getenv("ZHIPU_AI_API_KEY")
    ZHIPU_AI_MODEL = os.getenv("ZHIPU_AI_MODEL")
    ZHIPU_AI_CARD_MODEL = os.getenv("ZHIPU_AI_CARD_MODEL")
    
    if not ZHIPU_AI_API_KEY or ZHIPU_AI_API_KEY == "your_zhipu_api_key_here":
        print("⚠️ WARNING: ZHIPU_AI_API_KEY is not set or has default value")
        print("   Set a valid Zhipu AI API key in the .env file")
    else:
        # Check if API key has the correct format (ID.SECRET)
        if "." in ZHIPU_AI_API_KEY and len(ZHIPU_AI_API_KEY.split(".")) == 2:
            print("✅ ZHIPU_AI_API_KEY appears to have correct format (ID.SECRET)")
        else:
            print("⚠️ WARNING: ZHIPU_AI_API_KEY does not have the expected format (ID.SECRET)")
    
    print(f"- ZHIPU_AI_MODEL: {ZHIPU_AI_MODEL or 'Not set, will use default: glm-4'}")
    print(f"- ZHIPU_AI_CARD_MODEL: {ZHIPU_AI_CARD_MODEL or 'Not set, will use default: glm-4'}")
else:
    print("✓ Azure OpenAI is ENABLED (default)")
    # Check Azure OpenAI configuration
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    
    if not AZURE_OPENAI_API_KEY:
        print("⚠️ WARNING: AZURE_OPENAI_API_KEY is not set")
    
    if not AZURE_OPENAI_ENDPOINT:
        print("⚠️ WARNING: AZURE_OPENAI_ENDPOINT is not set")
    
    if not AZURE_OPENAI_DEPLOYMENT_NAME:
        print("⚠️ WARNING: AZURE_OPENAI_DEPLOYMENT_NAME is not set")
    
    print(f"- AZURE_OPENAI_DEPLOYMENT_NAME: {AZURE_OPENAI_DEPLOYMENT_NAME or 'Not set'}")

print("\nEnvironment check completed.") 