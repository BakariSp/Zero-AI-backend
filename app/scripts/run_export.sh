#!/bin/bash
# Script to run the learning path export

# Get the absolute path to the project root
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Change to the project root directory
cd "$ROOT_DIR"

# Set up Python path
export PYTHONPATH="$ROOT_DIR:$PYTHONPATH"

# Parse arguments
EXCLUDE_USERS="1,13"
METHOD="efficient"
FORMAT="both"
OUTPUT_DIR="./output"
SUMMARY_ONLY=false

# Process named arguments
for arg in "$@"; do
  case $arg in
    --exclude-users=*)
    EXCLUDE_USERS="${arg#*=}"
    shift
    ;;
    --method=*)
    METHOD="${arg#*=}"
    shift
    ;;
    --format=*)
    FORMAT="${arg#*=}"
    shift
    ;;
    --output-dir=*)
    OUTPUT_DIR="${arg#*=}"
    shift
    ;;
    --summary-only)
    SUMMARY_ONLY=true
    shift
    ;;
    *)
    # Unknown option
    ;;
  esac
done

# Build the command
CMD="python -m app.scripts.get_learning_paths --exclude-users=$EXCLUDE_USERS --method=$METHOD --format=$FORMAT --output-dir=$OUTPUT_DIR"

if [ "$SUMMARY_ONLY" = true ]; then
  CMD="$CMD --summary-only"
fi

# Print the command being executed
echo "Executing: $CMD"
echo "From directory: $ROOT_DIR"
echo "------------------------"

# Run the command
$CMD

# Check exit status
if [ $? -eq 0 ]; then
  echo "------------------------"
  echo "Export completed successfully."
  
  # Show output directory if files were exported
  if [ "$SUMMARY_ONLY" = false ]; then
    echo "Output files can be found in: $OUTPUT_DIR"
    
    # List files in the output directory if it exists
    if [ -d "$OUTPUT_DIR" ]; then
      echo "Files generated:"
      ls -la "$OUTPUT_DIR"
    fi
  fi
else
  echo "------------------------"
  echo "Export failed with error code $?."
fi 