# Duplicate Card Removal Script

This script identifies and removes duplicate cards from learning paths in the Zero-AI backend. Duplicate cards can cause incorrect progress calculations and a confusing user experience.

## Problem Description

In some learning paths, the same card may appear in multiple sections. This can lead to several issues:

1. Progress calculations become inaccurate because the same card may be counted multiple times
2. Users may see the same content repeated in different sections
3. When a user completes a card in one section, its completion status in other sections may not be updated consistently

This script removes duplicates by keeping only the first occurrence of each card (the one with the lowest course_id, section_id, and order_index) and removing all subsequent occurrences.

## Usage

The script requires Python 3.6+ and the following packages:
- sqlalchemy
- pymysql

To install the required packages:

```bash
pip install sqlalchemy pymysql
```

### Running the Script

Basic usage:

```bash
python remove_duplicate_cards.py
```

This will scan all learning paths in the database and remove any duplicate cards found.

### Command Line Arguments

The script supports the following command line arguments:

- `--path-id ID`: Process only a specific learning path with the given ID
- `--dry-run`: Perform a dry run without making any changes to the database (recommended for testing)

Example:

```bash
# Run in dry-run mode for learning path 297
python remove_duplicate_cards.py --path-id 297 --dry-run

# Actually remove duplicates from learning path 297
python remove_duplicate_cards.py --path-id 297

# Process all learning paths without making changes
python remove_duplicate_cards.py --dry-run

# Process all learning paths and remove all duplicates
python remove_duplicate_cards.py
```

### Environment Variables

The script uses the following environment variables to connect to the database:

- `DB_USER`: Database username (default: 'root')
- `DB_PASSWORD`: Database password (default: 'root')
- `DB_HOST`: Database host (default: 'localhost')
- `DB_PORT`: Database port (default: '3306')
- `DB_NAME`: Database name (default: 'zerodb')

You can set these variables in your environment or modify the defaults in the script.

## What the Script Does

1. **Find duplicate cards**: Identifies cards that appear multiple times in a learning path
2. **Remove duplicates**: Keeps the first occurrence of each card and removes all others
3. **Update progress**: Recalculates progress for affected sections, courses, and learning paths
4. **Reindex cards**: Updates the order_index values of remaining cards to maintain proper sequence

## After Running the Script

After running the script, progress percentages for all affected sections, courses, and learning paths will be recalculated based on the updated card structure. This ensures that progress tracking remains accurate after duplicate removal.

## Safety Features

The script includes the following safety features:

1. **Dry run mode**: Preview changes without modifying the database
2. **Transaction handling**: All database operations are performed in transactions to ensure consistency
3. **Logging**: Detailed logs are provided to track the script's progress and any errors that occur

## Support

If you encounter any issues when running this script, please check the log output for error messages. For additional help, contact the Zero-AI backend team. 