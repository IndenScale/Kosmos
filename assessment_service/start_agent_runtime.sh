#!/bin/bash

# Agent Runtime Startup Script for Docker Container
# This script starts both the scheduler process and the worker process in parallel
# Designed for containerized deployment with proper signal handling

set -e

echo "Starting Agent Runtime with three processes in container..."

# Function to handle cleanup on exit
cleanup() {
    echo "Received shutdown signal, stopping processes..."
    
    # Send SIGTERM to all child processes
    if [ ! -z "$SCHEDULER_PID" ] && kill -0 $SCHEDULER_PID 2>/dev/null; then
        echo "Stopping scheduler process (PID: $SCHEDULER_PID)..."
        kill -TERM $SCHEDULER_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$WORKER_PID" ] && kill -0 $WORKER_PID 2>/dev/null; then
        echo "Stopping worker process (PID: $WORKER_PID)..."
        kill -TERM $WORKER_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$PERIODIQ_PID" ] && kill -0 $PERIODIQ_PID 2>/dev/null; then
        echo "Stopping periodiq timer process (PID: $PERIODIQ_PID)..."
        kill -TERM $PERIODIQ_PID 2>/dev/null || true
    fi
    
    # Wait for processes to terminate gracefully
    local timeout=30
    local count=0
    while [ $count -lt $timeout ]; do
        local running=0
        if [ ! -z "$SCHEDULER_PID" ] && kill -0 $SCHEDULER_PID 2>/dev/null; then
            running=$((running + 1))
        fi
        if [ ! -z "$WORKER_PID" ] && kill -0 $WORKER_PID 2>/dev/null; then
            running=$((running + 1))
        fi
        if [ ! -z "$PERIODIQ_PID" ] && kill -0 $PERIODIQ_PID 2>/dev/null; then
            running=$((running + 1))
        fi
        
        if [ $running -eq 0 ]; then
            echo "All processes stopped gracefully."
            exit 0
        fi
        
        sleep 1
        count=$((count + 1))
    done
    
    # Force kill if processes don't stop gracefully
    echo "Force killing remaining processes..."
    [ ! -z "$SCHEDULER_PID" ] && kill -KILL $SCHEDULER_PID 2>/dev/null || true
    [ ! -z "$WORKER_PID" ] && kill -KILL $WORKER_PID 2>/dev/null || true
    [ ! -z "$PERIODIQ_PID" ] && kill -KILL $PERIODIQ_PID 2>/dev/null || true
    
    echo "Agent Runtime stopped."
    exit 0
}

# Set up signal handlers for graceful shutdown
trap cleanup SIGTERM SIGINT SIGQUIT

# Create logs directory if it doesn't exist
mkdir -p /app/logs/assessment_service

# Change to the correct working directory to ensure Python can find the assessment_service module
cd /app

# Verify Python can find the module before starting processes
echo "Verifying Python module path..."
python -c "import assessment_service.app.broker; print('Module import successful')" || {
    echo "ERROR: Cannot import assessment_service.app.broker"
    echo "Current directory: $(pwd)"
    echo "Python path: $PYTHONPATH"
    echo "Directory contents:"
    ls -la /app/
    exit 1
}

# Start the scheduler process (handles periodic task scheduling)
echo "Starting scheduler process (default queue)..."
dramatiq assessment_service.app.broker --queues default --processes 1 --threads 1 &
SCHEDULER_PID=$!

# Start the agent worker process (handles agent execution tasks)
echo "Starting agent worker process (agent_runners queue)..."
dramatiq assessment_service.app.broker --queues agent_runners --processes 1 --threads 1 &
WORKER_PID=$!

# Start the periodiq timer process (handles periodic task scheduling)
echo "Starting periodiq timer process..."
periodiq assessment_service.app.broker &
PERIODIQ_PID=$!

echo "All three processes started successfully:"
echo "  Scheduler PID: $SCHEDULER_PID"
echo "  Worker PID: $WORKER_PID"
echo "  Periodiq Timer PID: $PERIODIQ_PID"
echo "Container is ready to process tasks..."

# Wait for all three processes (this keeps the container running)
wait $SCHEDULER_PID $WORKER_PID $PERIODIQ_PID

echo "Agent Runtime container stopped."