#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

source "$PROJECT_ROOT/.venv/bin/activate"

echo "Starting DroneCAN GUI with final DSDL loading..."
python "$SCRIPT_DIR/add_custom_msg.py" --baudrate 1000000