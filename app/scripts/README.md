# Learning Path Export Scripts

This directory contains scripts for exporting learning paths from the database, with the ability to exclude specific users' learning paths.

## Scripts Overview

1. **get_learning_paths.py** - Main entry point script with command-line options
2. **get_all_learning_paths_except_users.py** - Standard implementation
3. **get_all_learning_paths_except_users_alt.py** - More efficient implementation using SQL subqueries
4. **run_export.ps1** - PowerShell script for Windows users
5. **run_export.bat** - Batch file wrapper for Windows users

## Usage

### Basic Usage

#### On Linux/macOS:

Run the main script to export all learning paths except those belonging to users with ID 1 or 13:

```bash
# Make sure you're in the project root directory (Zero-AI-backend)
cd /c/ACCD/MyProject/Zero-AI-backend

# Run as a module (recommended method)
python -m app.scripts.get_learning_paths
```

#### On Windows:

**Option 1**: Use the batch file (easiest)

```
# Navigate to the scripts directory
cd C:\ACCD\MyProject\Zero-AI-backend\app\scripts

# Run the batch file
run_export.bat
```

**Option 2**: Use PowerShell directly

```powershell
# Navigate to the scripts directory
cd C:\ACCD\MyProject\Zero-AI-backend\app\scripts

# Run the PowerShell script
.\run_export.ps1
```

**Option 3**: Run the Python module directly

```powershell
# Navigate to the project root
cd C:\ACCD\MyProject\Zero-AI-backend

# Run the Python module
python -m app.scripts.get_learning_paths
```

### Command-line Options

All methods support the same command-line options:

```
--exclude-users=1,13     # Comma-separated list of user IDs to exclude
--method=efficient       # Method to use: "standard" or "efficient"
--format=both            # Output format: "json", "csv", or "both"
--output-dir=./output    # Directory to save output files
--summary-only           # Only display summary, don't export files
```

### Examples

#### Exclude different users (e.g., users with IDs 2 and 5)

```
# Using batch file
run_export.bat --exclude-users=2,5

# Using PowerShell
.\run_export.ps1 --exclude-users=2,5

# Using Python directly
python -m app.scripts.get_learning_paths --exclude-users=2,5
```

#### Use the standard method and output only to JSON

```
run_export.bat --method=standard --format=json
```

#### Only display summary information (no exports)

```
run_export.bat --summary-only
```

#### Save output to a custom directory

```
run_export.bat --output-dir=C:\path\to\exports
```

## Running Individual Scripts

If you want to run one of the implementation scripts directly:

```bash
# Standard implementation
python -m app.scripts.get_all_learning_paths_except_users

# Efficient implementation
python -m app.scripts.get_all_learning_paths_except_users_alt
```

## Output

By default, the scripts will:

1. Display a summary of the learning paths found
2. Export the learning paths to JSON and CSV files in the specified output directory

### Output Files

- `learning_paths_export.json` - JSON file containing all retrieved learning paths
- `learning_paths_export.csv` - CSV file containing all retrieved learning paths

The summary includes:
- Total number of learning paths
- Number of template paths and user custom paths
- Breakdown by category
- Breakdown by difficulty level

## Implementation Details

### Standard Method (`get_all_learning_paths_except_users.py`)

This implementation:
1. Queries all learning paths
2. Queries all learning path IDs assigned to excluded users
3. Filters learning paths that are in the excluded list

### Efficient Method (`get_all_learning_paths_except_users_alt.py`)

This implementation:
1. Creates a SQL subquery to find learning paths assigned to excluded users
2. Uses a single query with a NOT IN clause to get all learning paths not in the subquery

The efficient method generally performs better, especially with larger datasets.

## Troubleshooting

### Windows-Specific Issues

1. **PowerShell Execution Policy**:
   If you get a security error when running the PowerShell script, you may need to adjust your execution policy:
   ```powershell
   # Run this in an Administrator PowerShell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```

2. **Module Import Errors**:  
   The batch and PowerShell scripts automatically set up the Python path. If running the Python module directly,
   you may need to set the PYTHONPATH environment variable:
   ```powershell
   $env:PYTHONPATH = "C:\ACCD\MyProject\Zero-AI-backend;$env:PYTHONPATH"
   ```

### Import Errors

If you get errors like `No module named 'get_all_learning_paths_except_users_alt'`, make sure you:

1. Run the script as a module from the project root directory:
   ```bash
   cd /c/ACCD/MyProject/Zero-AI-backend
   python -m app.scripts.get_learning_paths
   ```

2. Make sure the PYTHONPATH includes the project root:
   ```bash
   export PYTHONPATH=/c/ACCD/MyProject/Zero-AI-backend:$PYTHONPATH
   ```

### Database Connection Issues

If you encounter database connection errors:

1. Verify the database configuration in `app/db.py`
2. Make sure the SSL certificate file exists at the specified path
3. Check that your database server is running and accessible

### Empty Results

If no learning paths are returned:

1. Check that the database has learning paths
2. Verify that there are learning paths not assigned to the excluded users
3. Try running with different user IDs to exclude 