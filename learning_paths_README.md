# Learning Path Generation Scripts

This directory contains scripts for generating complete learning paths with courses, sections, and cards for the Zero AI recommendation system.

## Files

1. `learning_path_structures.json` - Contains predefined structures for all learning paths by interest category
2. `create_learning_paths_from_json.py` - Script to generate learning paths using the predefined structures
3. `create_interests_with_complete_paths_v2.py` - Alternative script that creates interests and learning paths

## Prerequisites

- Python 3.8+
- The Zero AI backend application must be properly installed and configured
- Database must be running and accessible

## Using the Scripts

### Generate Learning Paths from JSON Structure

This script reads the JSON file containing predefined structures and creates learning paths with courses, sections, and cards using the proper background task system. It also creates associations between interests and learning paths.

```bash
# Generate all learning paths (could take a long time)
python create_learning_paths_from_json.py

# Generate paths for a specific interest category
python create_learning_paths_from_json.py --interest tech_basics

# Generate a specific learning path
python create_learning_paths_from_json.py --interest tech_basics --path "Code Your First Website in 30 Days"

# Generate a limited number of paths (for testing)
python create_learning_paths_from_json.py --limit 2

# Adjust the timeout for each learning path generation (default: 180 seconds)
python create_learning_paths_from_json.py --timeout 300
```

#### Batch Processing Features

The script includes enhanced batch processing features for generating multiple learning paths:

1. **Progress Tracking** - Detailed progress information showing which path is currently being processed and how many are left
2. **Completion Statistics** - Counts of successful vs. failed path generations
3. **Time Tracking** - Duration of each path generation and total batch time
4. **Interest Summaries** - Shows the distribution of paths across different interest categories
5. **Timeout Control** - Adjust the timeout per path generation with the `--timeout` parameter
6. **Next Path Preview** - Shows which path will be generated next

When running in batch mode, the script will:
1. Show a summary of all paths to be processed
2. Display progress and status for each path as it's generated 
3. Create recommendation associations automatically
4. Show a final summary of results

### Alternative Method

The alternative script `create_interests_with_complete_paths_v2.py` provides similar functionality but with a different approach:

```bash
# Run the cleanup script first to reset the database
python cleanup_db.py

# Then generate learning paths with the alternative script
python create_interests_with_complete_paths_v2.py
```

## Process Overview

1. The script loads the predefined structures from the JSON file
2. For each learning path structure:
   - It creates a structured learning path request
   - Submits it to the background task system
   - Monitors the task for completion
   - Records the learning path ID for association creation
3. After all paths are generated, it creates interest-learning path associations
4. Updates the admin user's interests to include all categories

## Troubleshooting

- If the script times out waiting for a task to complete, you can increase the `task_timeout` parameter
- Check the logs for detailed information about the generation process
- If the script fails, you can retry with specific interest or path parameters
- For errors related to database connections, ensure the database is running and accessible

### Handling Foreign Key Constraint Errors

When cleaning up learning paths, you might encounter foreign key constraint errors like this:

```
sqlalchemy.exc.IntegrityError: (pymysql.err.IntegrityError) (1451, 'Cannot delete or update a parent row: a foreign key constraint fails (`zero-ai-database`.`backend_tasks`, CONSTRAINT `fk_user_tasks_learning_path_id` FOREIGN KEY (`learning_path_id`) REFERENCES `learning_paths` (`id`))')
```

This happens because there are tasks in the `backend_tasks` or `user_tasks` table that reference the learning paths you're trying to delete. To resolve this:

1. Use the updated `cleanup_learning_paths.py` script which handles these foreign key constraints:

```bash
# Clean up a specific learning path by ID
python cleanup_learning_paths.py 123

# Clean up a range of learning paths
python cleanup_learning_paths.py 123 125
```

2. If the script still fails, you can try a manual approach in your database:
   - First, set the foreign key reference to NULL in the tasks table:
   ```sql
   UPDATE backend_tasks SET learning_path_id = NULL WHERE learning_path_id = 123;
   -- or if you're using user_tasks:
   UPDATE user_tasks SET learning_path_id = NULL WHERE learning_path_id = 123;
   ```
   - Then try deleting the learning path again:
   ```sql
   DELETE FROM learning_paths WHERE id = 123;
   ```

3. If all else fails, you may need to temporarily disable foreign key checks (use with caution):
   ```sql
   SET FOREIGN_KEY_CHECKS = 0;
   DELETE FROM learning_paths WHERE id = 123;
   SET FOREIGN_KEY_CHECKS = 1;
   ```

## JSON Structure Format

The JSON file must follow this structure:

```json
{
  "interest_category": [
    {
      "title": "Learning Path Title",
      "courses": [
        {
          "title": "Course Title",
          "sections": [
            {"title": "Section Title"}
          ]
        }
      ]
    }
  ]
}
``` 