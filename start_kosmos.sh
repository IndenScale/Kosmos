#!/bin/bash

echo "Starting Kosmos frontend..."
# Start the frontend in a new terminal window or a background process
# For a new terminal window (macOS example, adjust for Linux/Windows):
# osascript -e 'tell application "Terminal" to do script "cd ~/Kosmos/frontend && npm start"' &
# For running in the background (output will be in the current terminal, but non-blocking):
nohup sh -c 'cd ~/Kosmos/frontend && npm start' > ~/kosmos_frontend.log 2>&1 &

# Give the frontend a moment to start (optional, adjust as needed)
sleep 5

echo "Starting Kosmos backend..."
# Start the backend
cd ~/Kosmos
nohup sh -c 'cd ~/Kosmos && uvicorn app.main:app --port 8000 --host 0.0.0.0' > ~/kosmos_backend.log 2>&1 &

echo "Kosmos frontend and backend started."
echo "Frontend output will be in its own terminal or in the background of this terminal."
echo "Backend is running in the background of this terminal."
echo "To stop the backend, you may need to find its process ID (e.g., using 'lsof -i :8000' or 'ps aux | grep uvicorn') and kill it."
