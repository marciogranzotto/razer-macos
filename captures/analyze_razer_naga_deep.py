#!/usr/bin/env python3
"""
Razer Naga V2 Pro - Deep Protocol Analysis
Analyzes SET_REPORT/GET_REPORT feature reports (Razer proprietary protocol).
Uses usb.data_fragment field for 90-byte Razer command payloads.
"""

import subprocess
import os
from collections import Counter, defaultdict

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Documentos\razer-naga-6btns-change-button-1.pcapng"

def run_tshark(args, timeout=180):
    cmd = [TSHARK, "-r", PCAP] + args
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                            errors='replace')
    return result.stdout.strip()

def section(title):
    print(f"\n{'='*75}")
    print(f"  {title}")
    print(f"{'='*75}")

def subsection(title):
    print(f"\n--- {title} ---")

# Known Razer command classes
CMD_CLASS_NAMES = {
    0x00: "General",
    0x01: "Device Mode",
    0x02: "Macro",
    0x03: "Lighting/LED",
    0x04: "Keyboard Layout",
    0x05: "Mouse Config",
    0x06: "Keypad",
    0x07: "Custom Effects",
    0x08: "Profile",
    0x09: "DPI",
    0x0b: "Wireless/Dongle",
    0x0d: "Button Mapping",
    0x0f: "Hypershift/Profile",
}

# Known Razer command IDs (some common ones)
CMD_NAMES = {
    (0x00, 0x01): "Get Device Info",
    (0x00, 0x02): "Get Firmware Version",
    (0x00, 0x03): "Get Serial Number",
    (0x00, 0x06): "Get Device Mode",
    (0x00, 0x86): "Set Device Mode",
    (0x03, 0x00): "Get LED State",
    (0x03, 0x01): "Set LED State",
    (0x03, 0x02): "Get LED Effect",
    (0x03, 0x03): "Set LED Effect",
    (0x03, 0x04): "Get LED Color",
    (0x03, 0x05): "Set LED Color",
    (0x03, 0x0a): "Get LED Brightness",
    (0x03, 0x0b): "Set LED Brightness",
    (0x05, 0x01): "Get Mouse DPI XY",
    (0x05, 0x04): "Get Polling Rate",
    (0x05, 0x05): "Set Polling Rate",
    (0x05, 0x26): "Get DPI Stages",
    (0x05, 0xa6): "Set DPI Stages",
    (0x07, 0x01): "Hypershift State",
    (0x0b, 0x01): "Get Wireless Mode",
    (0x0b, 0x02): "Get Battery Level",
    (0x0b, 0x03): "Get Charging Status",
    (0x0d, 0x01): "Get Button Mapping",
    (0x0d, 0x02): "Set Button Mapping",
    (0x0f, 0x01): "Get Profile",
    (0x0f, 0x02): "Set Profile",
    (0x0f, 0x03): "Get/Set Hypershift Btn Mapping",
}


def parse_razer_payload(hex_data):
    """Parse 90-byte Razer protocol payload.

    Format:
    Byte 0:    Status (0x00=new, 0x02=busy, 0x03=ok, 0x04=fail, 0x05=timeout)
    Byte 1:    Transaction ID
    Byte 2-3:  Remaining packets (uint16 BE)
    Byte 4:    Protocol type (0x00)
    Byte 5:    Data size (number of meaningful data bytes)
    Byte 6:    Command class
    Byte 7:    Command ID
    Byte 8-87: Data payload (80 bytes)
    Byte 88:   CRC (XOR of bytes 2-87)
    Byte 89:   Reserved (0x00)
    """
    if len(hex_data) < 180:  # 90 bytes = 180 hex chars
        return None

    result = {
        "status": int(hex_data[0:2], 16),
        "transaction_id": int(hex_data[2:4], 16),
        "remaining_packets": int(hex_data[4:8], 16),
        "protocol_type": int(hex_data[8:10], 16),
        "data_size": int(hex_data[10:12], 16),
        "cmd_class": int(hex_data[12:14], 16),
        "cmd_id": int(hex_data[14:16], 16),
        "payload": hex_data[16:176],  # 80 bytes of data
        "crc": int(hex_data[176:178], 16),
        "reserved": int(hex_data[178:180], 16),
    }

    # Get human-readable names
    result["cmd_class_name"] = CMD_CLASS_NAMES.get(result["cmd_class"], f"Unknown(0x{result['cmd_class']:02x})")
    result["cmd_name"] = CMD_NAMES.get((result["cmd_class"], result["cmd_id"]), "")

    # Status names
    status_names = {0: "NEW", 2: "BUSY", 3: "OK", 4: "FAIL", 5: "TIMEOUT"}
    result["status_name"] = status_names.get(result["status"], f"0x{result['status']:02x}")

    return result


def analyze_razer_protocol():
    """Extract and analyze all Razer protocol packets."""
    section("RAZER NAGA V2 PRO - DEEP PROTOCOL ANALYSIS")
    print(f"  VID:PID = 0x1532:0x00a8")
    print(f"  File: {os.path.basename(PCAP)}")

    all_parsed = []

    for bus_id, dev_addr, label in [(3, 5, "Phase 1 (bus 3 dev 5)"), (2, 3, "Phase 2 (bus 2 dev 3)")]:
        subsection(f"{label}")

        # Get SET_REPORT and GET_REPORT feature reports with 90-byte data
        # Host -> Device (SET_REPORT): setup data direction = out
        out = run_tshark([
            "-Y", f"usb.bus_id == {bus_id} && usb.device_address == {dev_addr} && usb.data_len >= 90 && usb.data_len <= 98",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "frame.time_relative",
            "-e", "usb.src",
            "-e", "usb.dst",
            "-e", "usb.data_len",
            "-e", "usb.data_fragment",
            "-e", "usbhid.setup.bRequest",
            "-E", "separator=|"
        ])

        lines = [l for l in out.split("\n") if l.strip()]
        print(f"  Total Razer protocol packets: {len(lines)}")

        if not lines:
            continue

        out_commands = Counter()
        in_commands = Counter()
        command_sequence = []

        for line in lines:
            parts = line.split("|")
            if len(parts) < 6:
                continue

            frame = parts[0]
            time_rel = parts[1]
            src = parts[2]
            dst = parts[3]
            data_len = parts[4]
            data_frag = parts[5].replace(":", "")

            direction = "OUT" if src == "host" else "IN"

            parsed = parse_razer_payload(data_frag)
            if not parsed:
                continue

            parsed["frame"] = frame
            parsed["time"] = time_rel
            parsed["direction"] = direction
            parsed["phase"] = label

            if direction == "OUT":
                out_commands[(parsed["cmd_class"], parsed["cmd_id"])] += 1
            else:
                in_commands[(parsed["cmd_class"], parsed["cmd_id"])] += 1

            command_sequence.append(parsed)
            all_parsed.append(parsed)

        # Summary
        print(f"\n  OUT (Host -> Device) Command Summary:")
        print(f"  {'Class':<8} {'CmdID':<8} {'Count':<8} {'Class Name':<25} {'Command Name'}")
        print(f"  {'-'*8} {'-'*8} {'-'*8} {'-'*25} {'-'*30}")
        for (cls, cmd), count in sorted(out_commands.items()):
            cls_name = CMD_CLASS_NAMES.get(cls, f"Unknown")
            cmd_name = CMD_NAMES.get((cls, cmd), "")
            print(f"  0x{cls:02x}     0x{cmd:02x}     {count:<8} {cls_name:<25} {cmd_name}")

        print(f"\n  IN (Device -> Host) Response Summary:")
        print(f"  {'Class':<8} {'CmdID':<8} {'Count':<8} {'Class Name':<25} {'Command Name'}")
        print(f"  {'-'*8} {'-'*8} {'-'*8} {'-'*25} {'-'*30}")
        for (cls, cmd), count in sorted(in_commands.items()):
            cls_name = CMD_CLASS_NAMES.get(cls, f"Unknown")
            cmd_name = CMD_NAMES.get((cls, cmd), "")
            print(f"  0x{cls:02x}     0x{cmd:02x}     {count:<8} {cls_name:<25} {cmd_name}")

        # Show first 30 packets in detail
        print(f"\n  First 30 protocol packets:")
        for i, p in enumerate(command_sequence[:30]):
            print(f"    #{p['frame']:>6s} t={p['time']:>10s}s [{p['direction']:>3s}] "
                  f"status={p['status_name']:<7s} "
                  f"cls=0x{p['cmd_class']:02x}({p['cmd_class_name'][:12]:>12s}) "
                  f"cmd=0x{p['cmd_id']:02x} "
                  f"size={p['data_size']:>2d} "
                  f"data={p['payload'][:40]}{'...' if len(p['payload']) > 40 else ''}")

    # Analyze button mapping specifically
    section("BUTTON MAPPING ANALYSIS")

    button_mapping_packets = [p for p in all_parsed if p["cmd_class"] == 0x0f]

    if not button_mapping_packets:
        # Try other potential button-mapping classes
        for cls_id, cls_name in [(0x0d, "0x0d Button Mapping"), (0x05, "0x05 Mouse Config")]:
            pkts = [p for p in all_parsed if p["cmd_class"] == cls_id]
            if pkts:
                button_mapping_packets.extend(pkts)
                print(f"  Found {len(pkts)} packets with cmd_class={cls_name}")

    if not button_mapping_packets:
        print("  No dedicated button mapping commands found.")
        print("  Looking for all unique command classes used...")
        all_classes = set()
        for p in all_parsed:
            all_classes.add(p["cmd_class"])
        print(f"  Command classes present: {sorted([f'0x{c:02x}' for c in all_classes])}")

    # Show all button mapping packets in detail
    if button_mapping_packets:
        print(f"\n  Button Mapping Packets ({len(button_mapping_packets)} total):")
        for p in button_mapping_packets:
            print(f"\n    Frame #{p['frame']} [{p['direction']}] t={p['time']}s")
            print(f"    Status={p['status_name']} Class=0x{p['cmd_class']:02x} Cmd=0x{p['cmd_id']:02x} Size={p['data_size']}")
            # Show payload in groups of 16
            payload = p["payload"]
            meaningful = payload[:p["data_size"]*2]
            for j in range(0, len(meaningful), 32):
                chunk = meaningful[j:j+32]
                hex_spaced = " ".join(chunk[k:k+2] for k in range(0, len(chunk), 2))
                ascii_chars = ""
                for k in range(0, len(chunk), 2):
                    byte_val = int(chunk[k:k+2], 16)
                    ascii_chars += chr(byte_val) if 32 <= byte_val < 127 else "."
                print(f"    {j//2:04x}: {hex_spaced:<48s} {ascii_chars}")

    # Full protocol chronology with command class 0x0f or any SET operations
    section("CONFIGURATION CHANGE TIMELINE")
    print("  Showing all SET operations (potential button remapping)...")

    set_operations = [p for p in all_parsed
                      if p["direction"] == "OUT" and p["status"] == 0x00]

    # Group by time clusters
    if set_operations:
        bursts = []
        current_burst = [set_operations[0]]
        for i in range(1, len(set_operations)):
            try:
                t_curr = float(set_operations[i]["time"])
                t_prev = float(set_operations[i-1]["time"])
                if t_curr - t_prev > 1.0:
                    bursts.append(current_burst)
                    current_burst = [set_operations[i]]
                else:
                    current_burst.append(set_operations[i])
            except:
                current_burst.append(set_operations[i])
        bursts.append(current_burst)

        print(f"  Total SET operations: {len(set_operations)}")
        print(f"  Configuration bursts (gap > 1s): {len(bursts)}")

        for i, burst in enumerate(bursts):
            t_start = burst[0]["time"]
            t_end = burst[-1]["time"]

            # Summarize commands in this burst
            burst_cmds = Counter()
            for p in burst:
                burst_cmds[(p["cmd_class"], p["cmd_id"])] += 1

            print(f"\n  Burst {i+1}: t={t_start}s - t={t_end}s ({len(burst)} packets)")
            for (cls, cmd), count in burst_cmds.most_common():
                cls_name = CMD_CLASS_NAMES.get(cls, f"0x{cls:02x}")
                cmd_name = CMD_NAMES.get((cls, cmd), f"0x{cmd:02x}")
                print(f"    {cls_name} cmd={cmd_name or f'0x{cmd:02x}'}: {count}x")

            # Show a few sample packets from each burst
            for p in burst[:5]:
                print(f"      #{p['frame']:>6s} cls=0x{p['cmd_class']:02x} cmd=0x{p['cmd_id']:02x} "
                      f"size={p['data_size']:>2d} data={p['payload'][:48]}...")

    # Analyze mouse endpoint interrupt data
    section("MOUSE HID REPORT ANALYSIS")

    for bus_id, dev_addr, label in [(3, 5, "Phase 1"), (2, 3, "Phase 2")]:
        subsection(f"Mouse Reports - {label} (bus {bus_id} dev {dev_addr})")

        out = run_tshark([
            "-Y", f"usb.bus_id == {bus_id} && usb.device_address == {dev_addr} && usb.transfer_type == 0x01 && usb.endpoint_address == 0x81 && usb.data_len > 0",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "frame.time_relative",
            "-e", "usb.data_len",
            "-e", "usb.capdata",
            "-e", "usb.data_fragment",
            "-E", "separator=|",
            "-c", "5000"
        ])

        lines = [l for l in out.split("\n") if l.strip()]
        print(f"  Mouse interrupt reports: {len(lines)}")

        button_events = []
        prev_button_byte = None

        for line in lines:
            parts = line.split("|")
            data = ""
            for idx in [4, 3]:
                if len(parts) > idx and parts[idx]:
                    data = parts[idx].replace(":", "")
                    break

            if not data or len(data) < 2:
                continue

            button_byte = int(data[0:2], 16)

            if button_byte != 0 and button_byte != prev_button_byte:
                frame = parts[0]
                time_rel = parts[1]
                pressed = []
                if button_byte & 0x01: pressed.append("Left")
                if button_byte & 0x02: pressed.append("Right")
                if button_byte & 0x04: pressed.append("Middle")
                if button_byte & 0x08: pressed.append("Back(4)")
                if button_byte & 0x10: pressed.append("Forward(5)")
                if button_byte & 0x20: pressed.append("Btn6")
                if button_byte & 0x40: pressed.append("Btn7")
                if button_byte & 0x80: pressed.append("Btn8")

                button_events.append({
                    "frame": frame,
                    "time": time_rel,
                    "button_byte": button_byte,
                    "buttons": pressed,
                    "raw_data": data[:32]
                })

            prev_button_byte = button_byte

        if button_events:
            print(f"  Button press events (state changes): {len(button_events)}")
            print(f"\n  Button press timeline:")
            for evt in button_events[:50]:
                print(f"    #{evt['frame']:>6s} t={evt['time']:>10s}s "
                      f"buttons=0x{evt['button_byte']:02x} [{', '.join(evt['buttons'])}] "
                      f"raw={evt['raw_data']}")
            if len(button_events) > 50:
                print(f"    ... ({len(button_events) - 50} more events)")

    # Keyboard endpoint analysis (side buttons)
    section("KEYBOARD/SIDE-BUTTON HID REPORT ANALYSIS")

    for bus_id, dev_addr, label in [(3, 5, "Phase 1"), (2, 3, "Phase 2")]:
        for ep in ["0x82", "0x83"]:
            subsection(f"Endpoint {ep} - {label} (bus {bus_id} dev {dev_addr})")

            out = run_tshark([
                "-Y", f"usb.bus_id == {bus_id} && usb.device_address == {dev_addr} && usb.transfer_type == 0x01 && usb.endpoint_address == {ep} && usb.data_len > 0",
                "-T", "fields",
                "-e", "frame.number",
                "-e", "frame.time_relative",
                "-e", "usb.data_len",
                "-e", "usb.capdata",
                "-e", "usb.data_fragment",
                "-E", "separator=|"
            ])

            lines = [l for l in out.split("\n") if l.strip()]
            print(f"  Reports: {len(lines)}")

            if lines:
                for line in lines[:30]:
                    parts = line.split("|")
                    data = ""
                    for idx in [4, 3]:
                        if len(parts) > idx and parts[idx]:
                            data = parts[idx].replace(":", "")
                            break
                    frame = parts[0] if parts else "?"
                    time_rel = parts[1] if len(parts) > 1 else "?"
                    print(f"    #{frame:>6s} t={time_rel:>10s}s data={data}")

    section("ANALYSIS COMPLETE")


if __name__ == "__main__":
    analyze_razer_protocol()
