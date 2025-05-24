#!/bin/bash

# Create the SQLite directory if it doesn't exist
mkdir -p sqlite_db

# Run database migrations or initialization (can be expanded later)
echo "Initializing database..."

# Start the application
echo "Starting the application..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} 