import serial
import time

# --- Configuration ---
CANUSB_PORT = '/dev/ttyACM0'  # Change this to your CANUSB port
BAUDRATE = 1000000
READ_TIMEOUT = 2.0


def send_command(ser, command_str):
    """Sends a command string followed by [CR]."""
    ser.write((command_str + '\r').encode('ascii'))
    print(f"Sent: {command_str}")


def read_response(ser, timeout=READ_TIMEOUT):
    """Reads a response ending with [CR] or timeout."""
    start_time = time.time()
    response = bytearray()
    while time.time() - start_time < timeout:
        if ser.in_waiting:
            char = ser.read(1)
            response += char
            if char == b'\r':
                break
    return bytes(response) if response else None


def response_text(response):
    if response is None:
        return "None"
    return f"{response!r} hex={response.hex(' ')}"


def response_payload(response):
    if response is None:
        return None
    return response.rstrip(b'\r')


def main():
    try:
        print(f"Connecting to {CANUSB_PORT}...")
        ser = serial.Serial(CANUSB_PORT, baudrate=BAUDRATE,
                            timeout=READ_TIMEOUT)
        print("Connected.")

        # --- Initialize CANUSB ---
        # Clear buffer
        for _ in range(3):
            ser.write(b'\r')
        time.sleep(0.1)

        # Check version
        send_command(ser, 'V')
        version = read_response(ser)
        print(f"Version: {response_text(version)}")
        if not version:
            raise Exception("Cannot communicate with CANUSB")

        # Set speed to 250kbps
        send_command(ser, 'S5')
        if read_response(ser) != b'\r':
            raise Exception("Cannot set CAN speed")
        print("Speed set to 250kbps.")

        # Open CAN channel
        send_command(ser, 'O')
        if read_response(ser) != b'\r':
            raise Exception("Cannot open CAN channel")
        print("CAN channel opened.")

        # --- Send FAULT_STATUS Read Request ---
        # Device Address: 0x03
        # Request ID: 0x000C0103
        # Command: little endian. See docs for command codes
        # CANUSB Format: Tiiiiiiiildd... -> T000C0103[command len (2) + params len][params]
        request_id = "000C01FF"
        data_cmd = "0000"
        dlc = "2"
        request_cmd = "T000000002017F"

        send_command(ser, request_cmd)
        response = read_response(ser)
        response_data = response_payload(response)
        print(f"TX response: {response_text(response)}")
        if response_data not in (b'z', b'Z'):
            print(f"Error sending request: {response_text(response)}")
        else:
            print("FAULT_STATUS request sent (acknowledged by CANUSB).")

        # --- Listen for Reply ---
        print("Listening for reply...")
        reply = read_response(ser, timeout=2.0)  # Listen for 1 sec for reply
        if reply:
            print(f"Received Raw Reply: {response_text(reply)}")
            # Parse reply: Expected format Tiiiiiiiilldd... where l=dlc, dd=data
            # On practice if len <= 0xF then it will be: Tiiiiiiiildd...
            reply_str = reply.decode('ascii', errors='replace').strip()
            if reply_str.startswith('T') and len(reply_str) >= 12:
                try:
                    # Yet hardcoded on examples whith data len <= F and param len <= 4
                    id_hex = reply_str[1:9]
                    dlc_hex = reply_str[9:10]
                    data_hex = reply_str[14:18]  # Remove trailing [CR]

                    print(f"  - ID (Hex): 0x{id_hex}")
                    print(f"  - DLC: {int(dlc_hex, 16)}")
                    print(f"  - Raw Data (Hex): {data_hex}")

                except ValueError:
                    print("  -> Error parsing reply data.")
            else:
                print("  -> Unexpected reply format.")
        else:
            print("No reply received within timeout.")

    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        try:
            # Close CAN channel on CANUSB
            send_command(ser, 'C')
            read_response(ser)  # Read the response to 'C'
            ser.close()
            print("Serial connection closed.")
        except:
            pass


if __name__ == "__main__":
    main()
