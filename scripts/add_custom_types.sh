#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Create symlink in home directory to our custom DSDL
CUSTOM_DSDL_SOURCE="$PROJECT_ROOT/Libs/Dronecan/include/libdcnode/uavcan_vendor_specific_types"
CUSTOM_DSDL_TARGET="$HOME/dronecan_vendor_specific_types"

echo "Setting up custom DSDL symlink..."
if [ -L "$CUSTOM_DSDL_TARGET" ]; then
    echo "Symlink already exists: $CUSTOM_DSDL_TARGET"
elif [ -d "$CUSTOM_DSDL_SOURCE" ]; then
    ln -s "$CUSTOM_DSDL_SOURCE" "$CUSTOM_DSDL_TARGET"
    echo "Created symlink: $CUSTOM_DSDL_TARGET -> $CUSTOM_DSDL_SOURCE"
else
    echo "Custom DSDL source not found: $CUSTOM_DSDL_SOURCE"
fi
