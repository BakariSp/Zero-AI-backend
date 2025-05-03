import os
from dotenv import load_dotenv
import sys

# Try to load environment variables from .env file (for local development)
load_dotenv()

# List of critical environment variables
critical_vars = [
    "DATABASE_URL",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "SECRET_KEY",
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "FRONTEND_URL"
]

# List of optional but recommended environment variables
recommended_vars = [
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_API_VERSION",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "MICROSOFT_CLIENT_ID",
    "MICROSOFT_CLIENT_SECRET",
    "JWT_SECRET_KEY",
    "SESSION_SECRET_KEY"
]

print("Checking environment variables...")
print("\nCritical variables:")
missing_critical = []
for var in critical_vars:
    value = os.getenv(var)
    if value:
        # Show first few characters only for sensitive info
        if "SECRET" in var or "KEY" in var or "PASSWORD" in var:
            display_value = f"{value[:3]}...{value[-3:]}" if len(value) > 6 else "***"
        else:
            display_value = value
        print(f"✅ {var}: {display_value}")
    else:
        print(f"❌ {var}: MISSING")
        missing_critical.append(var)

print("\nRecommended variables:")
for var in recommended_vars:
    value = os.getenv(var)
    if value:
        # Show first few characters only for sensitive info
        if "SECRET" in var or "KEY" in var or "PASSWORD" in var:
            display_value = f"{value[:3]}...{value[-3:]}" if len(value) > 6 else "***"
        else:
            display_value = value
        print(f"✅ {var}: {display_value}")
    else:
        print(f"⚠️ {var}: Not set")

# Exit with error if critical variables are missing
if missing_critical:
    print(f"\n❌ ERROR: Missing critical environment variables: {', '.join(missing_critical)}")
    print("Please configure these in your Azure App Service Configuration settings.")
    sys.exit(1)
else:
    print("\n✅ All critical environment variables are set.")

print("\nYour Python version:", sys.version)
print("Running in directory:", os.getcwd()) 