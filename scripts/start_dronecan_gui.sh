#!/bin/bash
# Simple wrapper to start DroneCAN GUI with custom DSDL

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Activate virtual environment
source "$PROJECT_ROOT/.venv/bin/activate"

# Load custom DSDL first
echo "Loading custom DSDL definitions..."
python "$SCRIPT_DIR/add_custom_msg.py"

# Start the GUI tool
echo "Starting DroneCAN GUI Tool..."
dronecan_gui_tool "$@"