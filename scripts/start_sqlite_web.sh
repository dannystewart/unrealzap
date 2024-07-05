#!/bin/bash

# Configuration
REMOTE_USER="danny"
REMOTE_HOST="zapper"
REMOTE_DB_PATH="/home/danny/bug-zapper/bug_zapper.db"
REMOTE_PORT=8080
LOCAL_PORT=8080
SQLITE_WEB_PATH="/home/danny/.pyenv/shims/sqlite_web"

# Function to check if a port is in use
port_in_use() {
    lsof -i :"$1" >/dev/null 2>&1
}

# Find an available local port
while port_in_use $LOCAL_PORT; do
    LOCAL_PORT=$((LOCAL_PORT + 1))
done

# Start SQLite Web on the remote machine
echo "Starting SQLite Web on remote machine..."
ssh -f $REMOTE_USER@$REMOTE_HOST "$SQLITE_WEB_PATH $REMOTE_DB_PATH --host 127.0.0.1 --port $REMOTE_PORT >/dev/null 2>&1 &"

# Create SSH tunnel in the background
echo "Creating SSH tunnel..."
ssh -nNT -L $LOCAL_PORT:localhost:$REMOTE_PORT $REMOTE_USER@$REMOTE_HOST &

# Store the SSH tunnel process ID
SSH_PID=$!

# Wait a moment for the tunnel to establish
sleep 2

# Open web browser (works on macOS)
echo "Opening SQLite Web in your default browser..."
open "http://localhost:$LOCAL_PORT"

echo "SQLite Web is now running. Access it at http://localhost:$LOCAL_PORT"
echo "Press Ctrl+C to stop the SSH tunnel and exit."

# Wait for user to terminate
trap 'kill $SSH_PID' EXIT
wait $SSH_PID
