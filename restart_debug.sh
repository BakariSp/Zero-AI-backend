#!/bin/bash

# Set environment variables for debugging
export LOG_LEVEL=DEBUG
export PYTHONUNBUFFERED=1

# Kill any existing API server
pkill -f "uvicorn main:app"

# Start the API server with enhanced debugging
echo "Starting API server with enhanced debugging..."
uvicorn main:app --reload --log-level debug 