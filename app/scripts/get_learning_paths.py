#!/usr/bin/env python
"""
Entry point script for retrieving learning paths not assigned to specific users.
This script allows you to run either implementation and specify custom user IDs to exclude.

Usage:
  python get_learning_paths.py [--exclude-users=1,13] [--method=standard|efficient] [--format=json|csv|both]
"""

import os
import sys
import argparse
import logging
import time
from typing import List

# Add the parent directory to the Python path so we can import our app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Retrieve learning paths not assigned to specific users."
    )
    
    parser.add_argument(
        "--exclude-users", 
        type=str, 
        default="1,13",
        help="Comma-separated list of user IDs to exclude (default: 1,13)"
    )
    
    parser.add_argument(
        "--method", 
        type=str, 
        choices=["standard", "efficient"], 
        default="efficient",
        help="Method to use for querying (standard or efficient) (default: efficient)"
    )
    
    parser.add_argument(
        "--format", 
        type=str, 
        choices=["json", "csv", "both"], 
        default="both",
        help="Output format (json, csv, or both) (default: both)"
    )
    
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./output",
        help="Directory to save output files (default: ./output)"
    )
    
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Only display summary, don't export files"
    )
    
    return parser.parse_args()

def main():
    """Main function to run the script."""
    args = parse_arguments()
    
    # Parse excluded user IDs
    excluded_user_ids = [int(uid.strip()) for uid in args.exclude_users.split(",")]
    
    # Ensure output directory exists
    if not args.summary_only and not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    logger.info(f"Retrieving learning paths excluding users: {excluded_user_ids}")
    logger.info(f"Method: {args.method}")
    logger.info(f"Output format: {args.format}")
    
    # Import the appropriate modules
    try:
        # We need to delay imports to ensure command-line args are processed first
        from app.db import SessionLocal
        
        # Fix the imports to use the fully qualified module paths
        if args.method == "standard":
            from app.scripts.get_all_learning_paths_except_users import (
                get_all_learning_paths_except_users as get_paths,
                export_as_json
            )
            from app.scripts.get_all_learning_paths_except_users_alt import (
                print_summary,
                export_to_csv
            )
        else:  # efficient
            from app.scripts.get_all_learning_paths_except_users_alt import (
                get_learning_paths_not_owned_by_users as get_paths,
                print_summary,
                export_to_csv
            )
            from app.scripts.get_all_learning_paths_except_users import export_as_json
        
        # Create database session
        db = SessionLocal()
        
        try:
            # Time the operation
            start_time = time.time()
            
            # Get learning paths
            learning_paths = get_paths(db, excluded_user_ids)
            
            # Calculate elapsed time
            elapsed_time = time.time() - start_time
            
            logger.info(f"Found {len(learning_paths)} learning paths (in {elapsed_time:.2f} seconds)")
            
            # Print summary
            print_summary(learning_paths)
            
            # Export results if not summary only
            if not args.summary_only and learning_paths:
                if args.format in ["json", "both"]:
                    json_path = os.path.join(args.output_dir, "learning_paths_export.json")
                    export_as_json(learning_paths, json_path)
                
                if args.format in ["csv", "both"]:
                    csv_path = os.path.join(args.output_dir, "learning_paths_export.csv")
                    export_to_csv(learning_paths, csv_path)
        
        except Exception as e:
            logger.error(f"Error: {str(e)}", exc_info=True)
        finally:
            db.close()
    
    except ImportError as e:
        logger.error(f"Error importing modules: {str(e)}")
        logger.error("Make sure you're running this script from the correct directory")
        sys.exit(1)

if __name__ == "__main__":
    main() 