# This file is intentionally left empty to make the directory a Python package 

# First import models to make them available when importing from app
from app import models

# Then import the setup module for initializing database relationships after models
# This helps resolve circular import issues
from app import setup

# Initialize database relationships
setup.setup_database_relationships()

# Import user_daily_usage at the very end to avoid circular imports
import app.user_daily_usage 