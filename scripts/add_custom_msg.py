# This program looks for uavcan_vendor_specific_types directory in repo and loads .uavcan definitions from it
# Make sure that:
# - There is one directory uavcan_vendor_specific_types in whole project including submodules
# - Naming of the .uavcan file is correct: [msg_id].[name].uavcan
# - Make sure that id and signature in serialisation/deserialisation file is correct.
# For example see: Libs/Dronecan/include/com/rl/vibration/Measurement.h

#!/usr/bin/env python3
import os
import sys
import struct
import dronecan
from dronecan import dsdl
from dronecan.dsdl import parser

def load_custom_dsdl():
    """Load custom DSDL properly with all required attributes"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, '..'))
    custom_dsdl_path = os.path.join(repo_root, 'uavcan_vendor_specific_types')
    
    print(f"Loading custom DSDL from: {custom_dsdl_path}")
    
    # Parse the custom DSDL
    custom_types = parser.parse_namespaces([custom_dsdl_path])
    
    # Add custom types properly
    for dtype in custom_types:
        # Add to TYPENAMES
        dronecan.TYPENAMES[dtype.full_name] = dtype
        
        # Add to DATATYPES if it has a DTID
        if dtype.default_dtid:
            dronecan.DATATYPES[(dtype.default_dtid, dtype.kind)] = dtype
            
            # Calculate base_crc like the original load_dsdl does
            dtype.base_crc = dsdl.crc16_from_bytes(struct.pack("<Q", dtype.get_data_type_signature()))
            
            print(f"Added: {dtype.full_name} (DTID: {dtype.default_dtid}, CRC: {hex(dtype.base_crc)})")
        
        # Also need to set up instantiation methods like original load_dsdl
        def create_instance_closure(closure_type, _mode=None):
            def create_instance(*args, **kwargs):
                if _mode:
                    assert '_mode' not in kwargs, 'Mode cannot be supplied to service type instantiation helper'
                    kwargs['_mode'] = _mode
                return dronecan.transport.CompoundValue(closure_type, *args, **kwargs)
            return create_instance

        dtype._instantiate = create_instance_closure(dtype)

        if dtype.kind == dtype.KIND_SERVICE:
            dtype.Request = create_instance_closure(dtype, _mode='request')
            dtype.Response = create_instance_closure(dtype, _mode='response')
    
    print(f"Total types after: {len(dronecan.DATATYPES)}")

def main():
    load_custom_dsdl()
    
    # Verify everything works
    print("\nVerifying message availability and functionality:")
    
    # Test standard messages
    standard_messages = [
        'uavcan.protocol.NodeStatus',
        'uavcan.protocol.GetNodeInfo', 
        'uavcan.equipment.ahrs.RawIMU'
    ]
    
    for msg_name in standard_messages:
        if msg_name in dronecan.TYPENAMES:
            dtype = dronecan.TYPENAMES[msg_name]
            has_crc = hasattr(dtype, 'base_crc')
            print(f"{msg_name} (CRC: {has_crc})")
        else:
            print(f"{msg_name}")
    
    # Run GUI tool
    from dronecan_gui_tool.main import main as gui_main
    
    # Remove --dsdl to prevent double-loading
    filtered_args = [arg for arg in sys.argv[1:] if not arg.startswith('--dsdl')]
    sys.argv = [sys.argv[0]] + filtered_args
    
    print(f"\nStarting GUI tool...")
    return gui_main()

if __name__ == '__main__':
    sys.exit(main())
    