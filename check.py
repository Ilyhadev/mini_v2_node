import struct
import sys

# Known Signatures
STANDARD_SIGNATURE = b'APDesc00'
ALT_SIGNATURE = bytes([0x40, 0xa2, 0xe4, 0xf1, 0x64, 0x68, 0x91, 0x06])
KOCHERGA_MAGIC = struct.pack("<Q", 0x5E4415146FC0C4C7)

def scan_firmware(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()

    print(f"Scanning {filepath} ({len(data)} bytes)...\n")
    
    # 1. Look for Kocherga Magic (Bootloader boundary)
    kocherga_idx = data.find(KOCHERGA_MAGIC)
    if kocherga_idx != -1:
        print(f"[+] Found Kocherga Magic at offset {kocherga_idx}")
    else:
        print("[-] Kocherga Magic not found.")

    # 2. Look for PX4 Descriptor
    found_desc = False
    
    # PX4 scans by casting pointers in 8-byte chunks. We mimic that here.
    for i in range(0, len(data) - 40, 8):
        chunk = data[i:i+8]
        
        is_standard = (chunk == STANDARD_SIGNATURE)
        is_alt = (chunk == ALT_SIGNATURE)
        
        if is_standard or is_alt:
            found_desc = True
            sig_name = "Standard ('APDesc00')" if is_standard else "Alternative (ALT_APD_SIGNATURE)"
            print(f"\n[+] Found {sig_name} Descriptor at offset {i}")
            
            # Extract exactly 40 bytes (36 bytes of data + 4 bytes natural struct padding)
            desc_data = data[i:i+48]
            
            # Format: 8s(Sig) Q(CRC) I(Size) I(VCS) B(Maj) B(Min) H(BoardID) 8s(Reserved) 4x(Padding)
            unpacked = struct.unpack("<8s Q I I B B H 16s 4x", desc_data)
            
            print(f"    Signature    : {unpacked[0]}")
            print(f"    Image CRC    : 0x{unpacked[1]:016X}")
            print(f"    Image Size   : {unpacked[2]} bytes")
            print(f"    VCS Commit   : 0x{unpacked[3]:08X}")
            print(f"    Version      : {unpacked[4]}.{unpacked[5]}")
            print(f"    Board ID     : {unpacked[6]}")
            print(f"    Reserved     : {unpacked[7].hex()}")
            
    if not found_desc:
        print("\n[-] No valid PX4 AppDescriptor found. (Checker will reject this file)")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python check_bin.py <path_to_bin>")
    else:
        scan_firmware(sys.argv[1])