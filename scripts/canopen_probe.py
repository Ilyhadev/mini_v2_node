#!/usr/bin/env python3
"""Probe a quiet CANopen device over python-can.

Typical use with an SLCAN adapter:

    python scripts/canopen_probe.py \
        --channel /dev/serial/by-id/usb-STMicroelectronics_STM32_STLink_066AFF505372485067051653-if02@1000000 \
        --bitrate 250000 --node-id 0x7F --scan-sdo

    python scripts/canopen_probe.py \
        --channel /dev/serial/by-id/usb-STMicroelectronics_STM32_STLink_066AFF505372485067051653-if02@1000000 \
        --bitrate 250000 --scan-nmt --scan-sdo

    python scripts/canopen_probe.py \
        --channel /dev/serial/by-id/usb-STMicroelectronics_STM32_STLink_066AFF505372485067051653-if02@1000000 \
        --bitrate 250000 --poke-all

    python scripts/canopen_probe.py \
        --channel /dev/serial/by-id/usb-STMicroelectronics_STM32_STLink_066AFF505372485067051653-if02@1000000 \
        --bitrate 250000 --spam-pdo-start

    python scripts/canopen_probe.py \
        --channel /dev/serial/by-id/usb-STMicroelectronics_STM32_STLink_066AFF505372485067051653-if02@1000000 \
        --bitrate 250000 --tx-flood

    python scripts/canopen_probe.py \
        --channel /dev/serial/by-id/usb-STMicroelectronics_STM32_STLink_066AFF505372485067051653-if02@1000000 \
        --lawicel-tx-test
"""

import argparse
import contextlib
import time
from collections import Counter

import can


DEFAULT_BITRATES = [125000, 250000, 500000, 1000000]
LAWICEL_BITRATE_CODES = {
    10000: "S0",
    20000: "S1",
    50000: "S2",
    100000: "S3",
    125000: "S4",
    250000: "S5",
    500000: "S6",
    750000: "S7",
    1000000: "S8",
}
NMT_COMMANDS = [
    (0x01, "start"),
    (0x80, "pre-operational"),
    (0x02, "stop"),
    (0x82, "reset communication"),
    (0x81, "reset node"),
]
SDO_OBJECTS = [
    (0x1000, 0x00, "device type"),
    (0x1001, 0x00, "error register"),
    (0x1008, 0x00, "manufacturer device name"),
    (0x1009, 0x00, "manufacturer hardware version"),
    (0x100A, 0x00, "manufacturer software version"),
    (0x1017, 0x00, "producer heartbeat time"),
    (0x1018, 0x01, "vendor id"),
    (0x1018, 0x02, "product code"),
    (0x1018, 0x03, "revision"),
    (0x1018, 0x04, "serial"),
    (0x1800, 0x01, "TPDO1 COB-ID"),
    (0x1800, 0x05, "TPDO1 event timer"),
    (0x2110, 0x01, "angle 1 MSB"),
    (0x2110, 0x02, "angle 1 LSB"),
    (0x2110, 0x07, "angle error"),
]


def parse_u16(value):
    return int(value, 0)


def parse_hex_bytes(value):
    value = value.replace(":", "").replace(" ", "")
    if len(value) % 2:
        raise argparse.ArgumentTypeError("hex byte string must have an even number of digits")
    return bytes.fromhex(value)


def parse_slcan_channel(channel):
    if "@" not in channel:
        return channel, 115200

    port, baudrate = channel.rsplit("@", 1)
    return port, int(baudrate)


def classify(frame):
    if frame.is_extended_id:
        return "extended"

    cob_id = frame.arbitration_id
    node_id = cob_id & 0x7F
    function = cob_id & 0x780

    if cob_id == 0x000 and frame.dlc == 2:
        target = "all" if frame.data[1] == 0 else str(frame.data[1])
        return f"NMT target={target}"
    if cob_id == 0x080 and frame.dlc == 0:
        return "SYNC"
    if function == 0x080 and node_id:
        return f"EMCY node={node_id}"
    if function == 0x180 and node_id:
        return f"TPDO1 node={node_id}"
    if function == 0x280 and node_id:
        return f"TPDO2 node={node_id}"
    if function == 0x380 and node_id:
        return f"TPDO3 node={node_id}"
    if function == 0x480 and node_id:
        return f"TPDO4 node={node_id}"
    if function == 0x580 and node_id:
        return f"SDO response node={node_id}"
    if function == 0x600 and node_id:
        return f"SDO request node={node_id}"
    if function == 0x700 and node_id and frame.dlc == 1:
        states = {
            0x00: "boot-up",
            0x04: "stopped",
            0x05: "operational",
            0x7F: "pre-operational",
        }
        state = states.get(frame.data[0], f"0x{frame.data[0]:02X}")
        return f"heartbeat node={node_id} state={state}"
    if cob_id == 0x7E4:
        return "LSS response"
    if cob_id == 0x7E5:
        return "LSS request"

    return "raw"


def format_frame(frame, started_at):
    data = " ".join(f"{byte:02X}" for byte in frame.data)
    ext = "x" if frame.is_extended_id else "s"
    elapsed = frame.timestamp - started_at if started_at else 0.0
    return (
        f"{elapsed:8.3f}s id=0x{frame.arbitration_id:08X}/{ext} "
        f"dlc={frame.dlc} data=[{data:<23}] {classify(frame)}"
    )


def recv_until(bus, deadline, started_at, seen, *, quiet=False):
    frames = []
    while time.monotonic() < deadline:
        frame = bus.recv(timeout=min(0.05, max(0.0, deadline - time.monotonic())))
        if frame is None:
            continue

        frames.append(frame)
        seen[classify(frame)] += 1
        if not quiet:
            print(format_frame(frame, started_at), flush=True)
    return frames


def send_frame(bus, arbitration_id, data=b""):
    bus.send(can.Message(arbitration_id=arbitration_id, data=bytes(data), is_extended_id=False))


def send_nmt(bus, command, node_id):
    send_frame(bus, 0x000, [command, node_id])


def send_nmt_start(bus, node_id):
    send_nmt(bus, 0x01, node_id)


def send_sync(bus):
    send_frame(bus, 0x080)


def send_sdo_upload(bus, node_id, index, subindex):
    send_frame(
        bus,
        0x600 + node_id,
        [0x40, index & 0xFF, (index >> 8) & 0xFF, subindex, 0x00, 0x00, 0x00, 0x00],
    )


def send_lss_inquire_node_id(bus):
    # This only works when a single LSS-capable CANopen slave is connected.
    send_frame(bus, 0x7E5, [0x04, 0x01, 0, 0, 0, 0, 0, 0])
    send_frame(bus, 0x7E5, [0x5E, 0, 0, 0, 0, 0, 0, 0])
    send_frame(bus, 0x7E5, [0x04, 0x00, 0, 0, 0, 0, 0, 0])


def scan_nmt_nodes(bus, args, started_at, seen):
    print(f"scan NMT start nodes {args.first_node}..{args.last_node}", flush=True)
    frames_seen = 0
    for node_id in range(args.first_node, args.last_node + 1):
        print(f"send NMT start 0x{node_id:02X}", flush=True)
        send_nmt_start(bus, node_id)
        frames_seen += len(recv_until(bus, time.monotonic() + args.nmt_gap, started_at, seen))

    frames_seen += len(recv_until(bus, time.monotonic() + args.after_nmt, started_at, seen))
    return frames_seen


def poke_all(bus, args, started_at, seen):
    print("poke all: broadcast NMT commands", flush=True)
    frames_seen = 0
    for command, name in NMT_COMMANDS:
        print(f"send NMT {name} all", flush=True)
        send_nmt(bus, command, 0x00)
        frames_seen += len(recv_until(bus, time.monotonic() + args.poke_gap, started_at, seen))

    print("poke all: targeted NMT start sweep", flush=True)
    for node_id in range(args.first_node, args.last_node + 1):
        send_nmt_start(bus, node_id)
        frames_seen += len(recv_until(bus, time.monotonic() + args.poke_gap, started_at, seen))

    print(f"poke all: {args.sync_count} SYNC frames", flush=True)
    for _ in range(args.sync_count):
        send_sync(bus)
        frames_seen += len(recv_until(bus, time.monotonic() + args.sync_period, started_at, seen))

    print("poke all: LSS inquire node-id", flush=True)
    send_lss_inquire_node_id(bus)
    frames_seen += len(recv_until(bus, time.monotonic() + args.after_sdo, started_at, seen))

    print(f"poke all: SDO read scan nodes {args.first_node}..{args.last_node}", flush=True)
    for node_id in range(args.first_node, args.last_node + 1):
        for index, subindex, _name in SDO_OBJECTS:
            send_sdo_upload(bus, node_id, index, subindex)
            frames_seen += len(
                recv_until(
                    bus,
                    time.monotonic() + args.sdo_gap,
                    started_at,
                    seen,
                    quiet=args.quiet_sdo_misses,
                )
            )

    frames_seen += len(recv_until(bus, time.monotonic() + args.after_sdo, started_at, seen))
    return frames_seen


def spam_pdo_start(bus, args, started_at, seen):
    target = "all" if args.node_id == 0 else f"0x{args.node_id:02X}"
    print(
        f"spam PDO start: {args.spam_count} NMT start cycles, target {target}, "
        "expect TPDO1 on 0x1FF",
        flush=True,
    )

    frames_seen = 0
    for attempt in range(1, args.spam_count + 1):
        print(f"spam attempt {attempt}/{args.spam_count}: NMT start {target}", flush=True)
        send_nmt_start(bus, args.node_id)
        if args.spam_broadcast:
            print(f"spam attempt {attempt}/{args.spam_count}: NMT start all", flush=True)
            send_nmt_start(bus, 0x00)
        frames_seen += len(recv_until(bus, time.monotonic() + args.spam_listen, started_at, seen))

    frames_seen += len(recv_until(bus, time.monotonic() + args.after_nmt, started_at, seen))
    return frames_seen


def tx_flood(bus, args, started_at, seen):
    print(
        f"TX flood: id=0x{args.flood_id:X}, data={args.flood_data.hex(' ').upper()}, "
        f"rate={args.flood_rate:.1f} Hz, duration={args.flood_duration:.1f}s",
        flush=True,
    )

    frame = can.Message(
        arbitration_id=args.flood_id,
        data=args.flood_data,
        is_extended_id=args.flood_extended,
    )
    deadline = time.monotonic() + args.flood_duration
    period = 1.0 / args.flood_rate if args.flood_rate > 0 else 0.0
    next_tx = time.monotonic()
    frames_seen = 0
    sent = 0

    while time.monotonic() < deadline:
        bus.send(frame)
        sent += 1

        frame_rx = bus.recv(timeout=0)
        if frame_rx is not None:
            frames_seen += 1
            seen[classify(frame_rx)] += 1
            print(format_frame(frame_rx, started_at), flush=True)

        if period > 0:
            next_tx += period
            sleep_time = next_tx - time.monotonic()
            if sleep_time > 0:
                time.sleep(sleep_time)

    frames_seen += len(recv_until(bus, time.monotonic() + args.after_flood, started_at, seen))
    print(f"TX flood sent {sent} frames", flush=True)
    return frames_seen


def slcan_ping(args):
    import serial

    port, baudrate = parse_slcan_channel(args.channel)
    print(f"SLCAN ping: port={port}, serial_baud={baudrate}", flush=True)

    with serial.serial_for_url(port, baudrate=baudrate, timeout=args.slcan_timeout) as ser:
        time.sleep(args.settle)
        ser.reset_input_buffer()
        ser.write(b"\r")
        ser.flush()

        for command, name in [
            (b"V\r", "hardware/software version"),
            (b"N\r", "serial number"),
            (b"F\r", "status flags"),
        ]:
            ser.write(command)
            ser.flush()
            response = ser.read_until(b"\r")
            printable = response.replace(b"\r", b"\\r")
            print(f"{command.decode().strip():>2} {name}: {printable!r}", flush=True)


def lawicel_exchange(ser, command, timeout):
    ser.timeout = timeout
    ser.write(command.encode() + b"\r")
    ser.flush()
    response = ser.read_until(b"\r")
    printable = response.replace(b"\r", b"\\r")
    print(f"{command:<16} -> {printable!r}", flush=True)
    return response


def lawicel_tx_test(args):
    import serial

    if args.lawicel_bitrate not in LAWICEL_BITRATE_CODES:
        supported = ", ".join(str(rate) for rate in sorted(LAWICEL_BITRATE_CODES))
        raise SystemExit(f"unsupported LAWICEL bitrate {args.lawicel_bitrate}; choose one of {supported}")

    port, baudrate = parse_slcan_channel(args.channel)
    bitrate_command = LAWICEL_BITRATE_CODES[args.lawicel_bitrate]
    tx_command = f"t{args.lawicel_id:03X}{len(args.lawicel_data)}{args.lawicel_data.hex().upper()}"

    print(
        f"LAWICEL TX test: port={port}, serial_baud={baudrate}, "
        f"can_bitrate={args.lawicel_bitrate}",
        flush=True,
    )

    with serial.serial_for_url(port, baudrate=baudrate, timeout=args.slcan_timeout) as ser:
        time.sleep(args.settle)
        ser.reset_input_buffer()

        for command in ["", "", "V", "C", bitrate_command, "O", "F"]:
            lawicel_exchange(ser, command, args.slcan_timeout)

        for counter in range(args.lawicel_count):
            response = lawicel_exchange(ser, tx_command, args.slcan_timeout)
            if response.startswith(b"\x07"):
                print(f"adapter rejected TX command at attempt {counter + 1}", flush=True)
                break
            time.sleep(args.lawicel_gap)

        lawicel_exchange(ser, "F", args.slcan_timeout)


def probe_bitrate(args, bitrate):
    print(f"\n=== bitrate {bitrate} bit/s ===", flush=True)
    try:
        bus = can.interface.Bus(
            args.channel,
            interface=args.interface,
            bitrate=bitrate,
            receive_own_messages=False,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"open failed: {exc}")
        return 0

    seen = Counter()
    started_at = None
    frames_seen = 0

    try:
        time.sleep(args.settle)
        started_at = time.time()

        print(f"passive listen {args.passive:.1f}s", flush=True)
        frames_seen += len(recv_until(bus, time.monotonic() + args.passive, started_at, seen))

        if args.tx_flood:
            frames_seen += tx_flood(bus, args, started_at, seen)
        elif args.spam_pdo_start:
            frames_seen += spam_pdo_start(bus, args, started_at, seen)
        elif args.poke_all:
            frames_seen += poke_all(bus, args, started_at, seen)
        elif args.scan_nmt:
            frames_seen += scan_nmt_nodes(bus, args, started_at, seen)
        else:
            target = "all" if args.node_id == 0 else f"0x{args.node_id:02X}"
            print(f"send NMT start {target}", flush=True)
            send_nmt_start(bus, args.node_id)
            frames_seen += len(recv_until(bus, time.monotonic() + args.after_nmt, started_at, seen))

        if args.sync:
            print(f"send {args.sync_count} SYNC frames", flush=True)
            for _ in range(args.sync_count):
                send_sync(bus)
                frames_seen += len(recv_until(bus, time.monotonic() + args.sync_period, started_at, seen))

        if args.lss:
            print("send LSS inquire node-id", flush=True)
            send_lss_inquire_node_id(bus)
            frames_seen += len(recv_until(bus, time.monotonic() + args.after_sdo, started_at, seen))

        if args.scan_sdo:
            print(f"scan SDO nodes {args.first_node}..{args.last_node}", flush=True)
            for node_id in range(args.first_node, args.last_node + 1):
                for index, subindex, _name in SDO_OBJECTS:
                    send_sdo_upload(bus, node_id, index, subindex)
                    frames_seen += len(
                        recv_until(
                            bus,
                            time.monotonic() + args.sdo_gap,
                            started_at,
                            seen,
                            quiet=args.quiet_sdo_misses,
                        )
                    )
            frames_seen += len(recv_until(bus, time.monotonic() + args.after_sdo, started_at, seen))

        if seen:
            summary = ", ".join(f"{name}: {count}" for name, count in sorted(seen.items()))
            print(f"summary: {summary}", flush=True)
        else:
            print("summary: no frames seen", flush=True)

        return frames_seen
    except can.CanError as exc:
        print(f"CAN error: {exc}", flush=True)
        return frames_seen
    finally:
        with contextlib.suppress(Exception):
            bus.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--channel",
        required=True,
        help="CAN channel, for example /dev/ttyACM0@115200 for python-can slcan",
    )
    parser.add_argument("--interface", default="slcan", help="python-can interface")
    parser.add_argument(
        "--bitrate",
        type=int,
        action="append",
        dest="bitrates",
        help="CAN bitrate to test. May be passed more than once.",
    )
    parser.add_argument("--passive", type=float, default=2.0, help="passive listen time per bitrate")
    parser.add_argument("--after-nmt", type=float, default=2.0, help="listen time after NMT start")
    parser.add_argument(
        "--poke-all",
        action="store_true",
        help="send non-persistent CANopen stimuli across broadcast and node IDs",
    )
    parser.add_argument("--poke-gap", type=float, default=0.05, help="listen gap after each poke-all frame")
    parser.add_argument(
        "--spam-pdo-start",
        action="store_true",
        help="repeatedly send NMT start and listen for the documented 0x1FF TPDO",
    )
    parser.add_argument("--spam-count", type=int, default=20, help="number of NMT start cycles")
    parser.add_argument(
        "--spam-listen",
        type=float,
        default=0.25,
        help="listen time after each spammed NMT start",
    )
    parser.add_argument(
        "--spam-broadcast",
        action="store_true",
        help="also send broadcast NMT start in each spam cycle",
    )
    parser.add_argument("--tx-flood", action="store_true", help="send a high-rate CAN frame stream")
    parser.add_argument("--flood-id", type=parse_u16, default=0x000, help="CAN ID for --tx-flood")
    parser.add_argument(
        "--flood-data",
        type=parse_hex_bytes,
        default=bytes([0x01, 0x7F]),
        help="hex payload for --tx-flood, for example 017F",
    )
    parser.add_argument("--flood-rate", type=float, default=500.0, help="TX flood frame rate in Hz")
    parser.add_argument("--flood-duration", type=float, default=5.0, help="TX flood duration in seconds")
    parser.add_argument("--flood-extended", action="store_true", help="use extended frame ID for --tx-flood")
    parser.add_argument("--after-flood", type=float, default=0.5, help="listen time after TX flood")
    parser.add_argument("--slcan-ping", action="store_true", help="query raw SLCAN adapter status over serial")
    parser.add_argument("--slcan-timeout", type=float, default=0.2, help="raw SLCAN serial read timeout")
    parser.add_argument("--lawicel-tx-test", action="store_true", help="raw LAWICEL setup/open/TX with responses")
    parser.add_argument("--lawicel-bitrate", type=int, default=250000, help="CAN bitrate for raw LAWICEL setup")
    parser.add_argument("--lawicel-id", type=parse_u16, default=0x000, help="11-bit CAN ID for raw LAWICEL TX")
    parser.add_argument(
        "--lawicel-data",
        type=parse_hex_bytes,
        default=bytes([0x01, 0x7F]),
        help="hex payload for raw LAWICEL TX",
    )
    parser.add_argument("--lawicel-count", type=int, default=20, help="number of raw LAWICEL TX commands")
    parser.add_argument("--lawicel-gap", type=float, default=0.1, help="gap after each raw LAWICEL TX command")
    parser.add_argument("--scan-nmt", action="store_true", help="send targeted NMT start to each scanned node")
    parser.add_argument("--nmt-gap", type=float, default=0.1, help="listen gap after each scanned NMT start")
    parser.add_argument(
        "--node-id",
        type=parse_u16,
        default=0x7F,
        help="NMT target node ID. Use 0 for CANopen broadcast.",
    )
    parser.add_argument("--settle", type=float, default=0.2, help="delay after opening the adapter")
    parser.add_argument("--sync", action="store_true", help="send CANopen SYNC frames")
    parser.add_argument("--sync-count", type=int, default=5, help="number of SYNC frames to send")
    parser.add_argument("--sync-period", type=float, default=0.1, help="delay after each SYNC frame")
    parser.add_argument("--lss", action="store_true", help="try a simple LSS node-id inquiry")
    parser.add_argument("--scan-sdo", action="store_true", help="query common SDO objects")
    parser.add_argument("--first-node", type=parse_u16, default=1, help="first SDO node ID to query")
    parser.add_argument("--last-node", type=parse_u16, default=127, help="last SDO node ID to query")
    parser.add_argument("--sdo-gap", type=float, default=0.02, help="listen gap after each SDO request")
    parser.add_argument("--after-sdo", type=float, default=0.5, help="listen time after SDO/LSS activity")
    parser.add_argument(
        "--quiet-sdo-misses",
        action="store_true",
        help="do not print frames received during individual SDO waits",
    )

    args = parser.parse_args()
    if args.slcan_ping:
        slcan_ping(args)
        return
    if args.lawicel_tx_test:
        lawicel_tx_test(args)
        return

    bitrates = args.bitrates or DEFAULT_BITRATES

    total_seen = 0
    for bitrate in bitrates:
        total_seen += probe_bitrate(args, bitrate)

    if total_seen == 0:
        print("\nNo CAN frames detected at tested bitrates.")
        print("Try power-cycling the device while the passive listener is already running.")


if __name__ == "__main__":
    main()
