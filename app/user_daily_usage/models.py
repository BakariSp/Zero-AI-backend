# Import the UserDailyUsage model from app.models instead of redefining it
# This avoids the "Table already defined" error in SQLAlchemy

from app.models import UserDailyUsage

# Re-export the model
__all__ = ['UserDailyUsage'] 