# This program looks for uavcan_vendor_specific_types directory in repo and loads .uavcan definitions from it
# Make sure that:
# - There is one directory uavcan_vendor_specific_types in whole project including submodules
# - Naming of the .uavcan file is correct: [msg_id].[name].uavcan
# - Make sure that id and signature in serialisation/deserialisation file is correct.
# For example see: Libs/Dronecan/include/com/rl/vibration/Measurement.h

#!/usr/bin/env python3
#!/usr/bin/env python3
#!/usr/bin/env python3
"""
Simple DSDL loader using the correct DroneCAN/Yakut approach
"""

import os
import sys

# Find the custom DSDL path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
custom_dsdl_path = os.path.join(project_root, 'uavcan_vendor_specific_types')

print(f"Looking for DSDL in: {custom_dsdl_path}")

if os.path.isdir(custom_dsdl_path):
    print(f"Found custom DSDL at: {custom_dsdl_path}")
    
    # Method 1: Set environment variable for Yakut
    os.environ['YAKUT_PATH'] = custom_dsdl_path
    print("✓ Set YAKUT_PATH environment variable")
    
    # Method 2: Try to load directly with DroneCAN
    try:
        import dronecan
        from dronecan.dsdl import parse_dsdl_namespace
        
        # Parse the custom DSDL namespace
        parsed_namespace = parse_dsdl_namespace(custom_dsdl_path)
        print("✓ Custom DSDL namespace parsed successfully")
        
        # Try to access our custom message
        try:
            # This will work if the DSDL is properly structured
            from dronecan.com.rl.vibration import Vibration
            print(f"✓ Custom vibration message loaded!")
            print(f"  ID: {Vibration.dtid}, Signature: {hex(Vibration.data_type_signature)}")
        except ImportError as e:
            print(f"⚠ Could not import custom message directly: {e}")
            print("  This is normal if DSDL needs compilation first")
            
    except Exception as e:
        print(f"⚠ DroneCAN DSDL parsing failed: {e}")
        
else:
    print(f"❌ Custom DSDL path not found: {custom_dsdl_path}")

print("DSDL loading complete.")