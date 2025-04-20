# Example: Inside the run_migrations_online() function (or wherever target_metadata is set)

# Import your Base from where it's defined
from app.db import Base
# IMPORTANT: Make sure all your models are imported *before* this line,
# so they register themselves with Base.metadata.
# You might need to import them directly or import a module that imports them.
# Example:
import app.models # If this imports User, LearningPath etc.
import app.tasks.models # Explicitly import the new models file

# Assign your Base's metadata to target_metadata
target_metadata = Base.metadata

# ... rest of the env.py configuration ... 