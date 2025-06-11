#!/bin/bash

# Startup script for full application
# Usage: .scripts/startup.sh

# Configuration
BACKEND_DIR="."
FRONTEND_DIR="./frontend"
BACKEND_LOG="backend.log"
FRONTEND_LOG="frontend.log"
BACKEND_PID="backend.pid"
FRONTEND_PID="frontend.pid"

# Start backend
start_backend() {
    echo "Starting backend..."
    cd $BACKEND_DIR
    nohup uvicorn main:app --host 0.0.0.0 > $BACKEND_LOG 2>&1 &
    echo $! > $BACKEND_PID
    echo "Backend started (PID: $(cat $BACKEND_PID))"
}

# Start frontend
start_frontend() {
    echo "Starting frontend..."
    cd $FRONTEND_DIR
    nohup npm start > $FRONTEND_LOG 2>&1 &
    echo $! > $FRONTEND_PID
    echo "Frontend started (PID: $(cat $FRONTEND_PID))"
}

# Main execution
start_backend
start_frontend

echo "Application started successfully"
echo "Backend log: $BACKEND_DIR/$BACKEND_LOG"
echo "Frontend log: $FRONTEND_DIR/$FRONTEND_LOG"