#!/bin/bash

# ==============================================================================
# Kosmos Service Management Script (V2)
#
# A unified script to start, stop, restart, and check the status of all
# or individual Kosmos backend services.
#
# Usage:
#   ./kosmos_service.sh <command> [service_name]
#
# Commands:
#   start       - Start all services or a specific service
#   stop        - Stop all services or a specific service
#   restart     - Restart all services or a specific service
#   status      - Show the status of all services or a specific service
#   clear-queues - Clear all Dramatiq message queues (independent command)
#
# Examples:
#   ./kosmos_service.sh start
#   ./kosmos_service.sh stop dramatiq_workers
#   ./kosmos_service.sh status api_server
#   ./kosmos_service.sh clear-queues
# ==============================================================================

# --- Configuration ---
PID_DIR=".pids"
LOG_DIR="logs"
VENV_PATH=".venv/bin/activate"

# Define all services in an associative array for easy management.
# [FINAL FIX v3] Use dedicated, executable wrapper scripts for all python-based services.
declare -A SERVICES=(
    ["api_server"]="uvicorn backend.app.main:app --host 0.0.0.0 --port 8011"
    ["assessment_server"]="uvicorn assessment_service.app.main:app --host 0.0.0.0 --port 8015"
    ["dramatiq_content_extraction_worker"]="./scripts/run_dramatiq_content_extraction.sh"
    ["dramatiq_asset_analysis_worker"]="./scripts/run_dramatiq_asset_analysis.sh"
    ["dramatiq_chunking_worker"]="./scripts/run_dramatiq_chunking.sh"
    ["dramatiq_indexing_worker"]="./scripts/run_dramatiq_indexing.sh"
    ["event_relay"]="./scripts/run_event_relay.sh"
    ["trigger_content_extraction"]="./scripts/run_trigger_content_extraction.sh"
    ["trigger_chunking"]="./scripts/run_trigger_chunking.sh"
    ["trigger_indexing"]="./scripts/run_trigger_indexing.sh"
    ["trigger_asset_analysis"]="./scripts/run_trigger_asset_analysis.sh"
    ["periodiq_assessment_broker"]="python -m periodiq assessment_service.app.broker"
    ["dramatiq_assessment_broker_default"]="python -m dramatiq assessment_service.app.broker --queues default --processes 1 --threads 1"
    ["dramatiq_assessment_broker_agents"]="python -m dramatiq assessment_service.app.broker --queues agent_runners --processes 2 --threads 2"
    ["frontend_dev_server"]="./scripts/run_frontend_dev_server.sh"
)

# --- Helper Functions ---

print_status() {
    local COLOR_GREEN='\033[0;32m'
    local COLOR_RED='\033[0;31m'
    local COLOR_YELLOW='\033[0;33m'
    local COLOR_NC='\033[0m'

    case "$1" in
        RUNNING) echo -e "[ ${COLOR_GREEN}RUNNING${COLOR_NC} ]";;
        STOPPED) echo -e "[ ${COLOR_RED}STOPPED${COLOR_NC} ]";;
        *) echo -e "[ ${COLOR_YELLOW}$1${COLOR_NC} ]";;
    esac
}

is_running() {
    [ -n "$1" ] && kill -0 "$1" 2>/dev/null
}

# --- Single Service Functions ---

start_service() {
    local service_name=$1
    local pid_file="$PID_DIR/$service_name.pid"
    local log_file="$LOG_DIR/$service_name.log"

    if [ -f "$pid_file" ] && is_running "$(cat "$pid_file")"; then
        echo "Service '$service_name' is already running with PID $(cat "$pid_file")."
        return
    fi

    echo -n "Starting '$service_name'... "

    nohup ${SERVICES[$service_name]} > "$log_file" 2>&1 &
    local pid=$!

    echo "$pid" > "$pid_file"
    echo "OK. PID: $pid, Log: $log_file"
}

stop_service() {
    local service_name=$1
    local pid_file="$PID_DIR/$service_name.pid"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if is_running "$pid"; then
            echo -n "Stopping '$service_name' (PID: $pid)... "
            kill "$pid"
            sleep 2
            if is_running "$pid"; then
                echo "Forcing kill..."
                kill -9 "$pid"
            fi
            echo "OK."
        else
            echo "Service '$service_name' has a PID file but is not running. Cleaning up."
        fi
        rm "$pid_file"
    else
        echo "Service '$service_name' is not running (no PID file)."
    fi
}

status_service() {
    local service_name=$1
    local pid_file="$PID_DIR/$service_name.pid"

    printf "% -35s % -10s % -10s\n" "SERVICE" "STATUS" "PID"
    echo "-------------------------------------------------------"

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if is_running "$pid"; then
            printf "% -35s % -10s % -10s\n" "$service_name" "$(print_status RUNNING)" "$pid"
        else
            printf "% -35s % -10s % -10s\n" "$service_name" "$(print_status STOPPED)" " (stale PID file)"
        fi
    else
        printf "% -35s % -10s % -10s\n" "$service_name" "$(print_status STOPPED)" "N/A"
    fi
}

# --- Main Logic ---

COMMAND=$1
SERVICE_NAME=$2

# Create necessary directories
mkdir -p "$PID_DIR"
mkdir -p "$LOG_DIR"

# Activate virtual environment if it exists
if [ -f "$VENV_PATH" ]; then
    source "$VENV_PATH"
fi

# [CRITICAL FIX] Set PYTHONPATH to the project's root directory.
# This ensures that `python -m` can correctly find the `backend` package.
export PYTHONPATH=$(pwd)
echo "--- [Service Script] PYTHONPATH set to: $PYTHONPATH"

# Determine which services to operate on
if [ -n "$SERVICE_NAME" ]; then
    if [[ -z "${SERVICES[$SERVICE_NAME]}" ]]
    then
        echo "Error: Service '$SERVICE_NAME' not found."
        echo "Available services: ${!SERVICES[@]}"
        exit 1
    fi
    service_list=("$SERVICE_NAME")
else
    # Get all keys from the associative array
    service_list=("${!SERVICES[@]}")
fi

# Execute the command
case "$COMMAND" in
    start)
        echo "Starting services: ${service_list[*]}"
        for service in "${service_list[@]}"; do
            start_service "$service"
        done
        ;;
    stop)
        echo "Stopping services: ${service_list[*]}"
        for service in "${service_list[@]}"; do
            stop_service "$service"
        done
        ;;
    restart)
        echo "Restarting services: ${service_list[*]}"
        for service in "${service_list[@]}"; do
            stop_service "$service"
            sleep 1
            start_service "$service"
        done
        ;;
    status)
        if [ -n "$SERVICE_NAME" ]; then
            status_service "$SERVICE_NAME"
        else
            status_service # Call the original multi-service status function
        fi
        ;;
    clear-queues)
        echo "Clearing all Dramatiq queues..."
        python -c "from backend.app.tasks.broker import clear_all_queues; print(f'Cleared {clear_all_queues()} keys')"
        ;;
    *)
        echo "Invalid command: $COMMAND"
        echo "Usage: $0 {start|stop|restart|status|clear-queues} [service_name]"
        exit 1
        ;;
esac

# A small hack to fix the status function for all services
if [ "$COMMAND" == "status" ] && [ -z "$SERVICE_NAME" ]; then
    printf "% -35s % -10s % -10s\n" "SERVICE" "STATUS" "PID"
    echo "-------------------------------------------------------"
    for service in "${!SERVICES[@]}"; do
        pid_file="$PID_DIR/$service.pid"
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            if is_running "$pid"; then
                printf "% -35s % -10s % -10s\n" "$service" "$(print_status RUNNING)" "$pid"
            else
                printf "% -35s % -10s % -10s\n" "$service" "$(print_status STOPPED)" " (stale PID file)"
            fi
        else
            printf "% -35s % -10s % -10s\n" "$service" "$(print_status STOPPED)" "N/A"
        fi
    done
fi


exit 0