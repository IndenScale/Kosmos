#!/bin/bash

# Frontend Development Server Startup Script
# This script starts the Vite development server with proper log management

# Define paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOG_FILE="$PROJECT_ROOT/logs/frontend_dev_server.log"

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_ROOT/logs"

# Change to frontend directory
cd "$FRONTEND_DIR"

# Clear previous logs
> "$LOG_FILE"

# Start Vite development server
echo "Starting Vite development server..."
echo "Logs will be written to: $LOG_FILE"
echo "Access the application at: http://localhost:3000"

# Run Vite in foreground and redirect output to log file
npx vite >> "$LOG_FILE" 2>&1