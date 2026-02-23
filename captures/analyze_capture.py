#!/usr/bin/env python3
"""
Analyze Razer Naga V2 Pro USB capture for button mapping commands.
Usage: python analyze_capture.py <pcapng_file> [bus_id] [device_address]

If bus_id/device_address not given, auto-detects by looking for Razer VID 0x1532.
"""
import subprocess
import sys
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"

def run(pcap, args, timeout=300):
    cmd = [TSHARK, "-r", pcap] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

def parse_razer(hex_data):
    d = hex_data.replace(":", "")
    if len(d) < 180:
        return None
    return {
        "status": int(d[0:2], 16), "trans_id": int(d[2:4], 16),
        "remaining": int(d[4:8], 16), "proto_type": int(d[8:10], 16),
        "data_size": int(d[10:12], 16), "cmd_class": int(d[12:14], 16),
        "cmd_id": int(d[14:16], 16), "payload": d[16:176],
        "crc": int(d[176:178], 16), "end": int(d[178:180], 16),
    }

HID_KEYCODES = {
    0x00: "None",
    0x04: "a", 0x05: "b", 0x06: "c", 0x07: "d", 0x08: "e", 0x09: "f",
    0x0a: "g", 0x0b: "h", 0x0c: "i", 0x0d: "j", 0x0e: "k", 0x0f: "l",
    0x10: "m", 0x11: "n", 0x12: "o", 0x13: "p", 0x14: "q", 0x15: "r",
    0x16: "s", 0x17: "t", 0x18: "u", 0x19: "v", 0x1a: "w", 0x1b: "x",
    0x1c: "y", 0x1d: "z",
    0x1e: "1", 0x1f: "2", 0x20: "3", 0x21: "4", 0x22: "5", 0x23: "6",
    0x24: "7", 0x25: "8", 0x26: "9", 0x27: "0",
    0x28: "Enter", 0x29: "Escape", 0x2a: "Backspace", 0x2b: "Tab",
    0x2c: "Space", 0x2d: "-", 0x2e: "=", 0x2f: "[", 0x30: "]",
    0x39: "CapsLock",
    0x3a: "F1", 0x3b: "F2", 0x3c: "F3", 0x3d: "F4", 0x3e: "F5", 0x3f: "F6",
    0x40: "F7", 0x41: "F8", 0x42: "F9", 0x43: "F10", 0x44: "F11", 0x45: "F12",
    0x49: "Insert", 0x4a: "Home", 0x4b: "PageUp",
    0x4c: "Delete", 0x4d: "End", 0x4e: "PageDown",
    0x4f: "Right", 0x50: "Left", 0x51: "Down", 0x52: "Up",
    0x53: "NumLock",
    0x54: "KP /", 0x55: "KP *", 0x56: "KP -", 0x57: "KP +",
    0x58: "KP Enter",
    0x59: "KP 1", 0x5a: "KP 2", 0x5b: "KP 3", 0x5c: "KP 4",
    0x5d: "KP 5", 0x5e: "KP 6", 0x5f: "KP 7", 0x60: "KP 8",
    0x61: "KP 9", 0x62: "KP 0",
}

MOUSE_BUTTONS = {
    0x01: "Left Click", 0x02: "Right Click", 0x03: "Middle Click",
    0x04: "Mouse 4 (Back)", 0x05: "Mouse 5 (Forward)",
    0x06: "Mouse 6", 0x07: "Mouse 7", 0x08: "Mouse 8",
    0x09: "DPI Up", 0x0a: "DPI Down",
}

MULTIMEDIA_KEYS = {
    0xb5: "Next Track", 0xb6: "Prev Track", 0xb7: "Stop",
    0xcd: "Play/Pause", 0xe2: "Mute", 0xe9: "Volume Up", 0xea: "Volume Down",
    0x83: "Media Select", 0x8a: "Email", 0x92: "Calculator",
    0x94: "My Computer", 0x21: "Search", 0x23: "Home Page",
    0x24: "Back", 0x25: "Forward", 0x26: "Stop", 0x27: "Refresh",
}

CMD_CLASS_NAMES = {
    0x00: "General", 0x01: "DevMode", 0x02: "Macro",
    0x03: "LED", 0x04: "KbdLayout", 0x05: "Mouse",
    0x06: "Keypad", 0x07: "CustomFX", 0x08: "Profile",
    0x09: "DPI", 0x0b: "Wireless", 0x0d: "BtnMap",
    0x0f: "HyperProf", 0x15: "ExtCfg",
}

STATUS_NAMES = {0: "NEW", 2: "BUSY", 3: "OK", 4: "FAIL", 5: "TIMEOUT"}

ACTION_TYPES = {
    0x00: "Disabled/Default",
    0x01: "Mouse Button",
    0x02: "Keyboard Key",
    0x03: "Macro",
    0x04: "Profile Switch",
    0x05: "DPI Switch",
    0x06: "Hypershift Toggle",
    0x0a: "Multimedia Key",
    0x0b: "Double-Click",
}

def decode_action(b):
    """Decode the action bytes from a button mapping command.
    b = full payload bytes list, action starts at index 3."""
    if len(b) < 7:
        return f"(too short: {len(b)} bytes)"

    action_type = b[3]
    action_name = ACTION_TYPES.get(action_type, f"Unknown(0x{action_type:02x})")
    sub = b[4]
    param1 = b[5] if len(b) > 5 else 0
    param2 = b[6] if len(b) > 6 else 0

    detail = ""
    if action_type == 0x00:
        detail = "-> Disabled/Default"
    elif action_type == 0x01:
        btn_name = MOUSE_BUTTONS.get(param2, f"Button 0x{param2:02x}")
        detail = f"-> Mouse: {btn_name}"
    elif action_type == 0x02:
        key_name = HID_KEYCODES.get(param2, f"Key 0x{param2:02x}")
        modifier = f" (mod=0x{param1:02x})" if param1 else ""
        detail = f"-> Keyboard: {key_name}{modifier}"
    elif action_type == 0x0a:
        mm_name = MULTIMEDIA_KEYS.get(param2, f"MM 0x{param2:02x}")
        detail = f"-> Multimedia: {mm_name}"
    elif action_type == 0x06:
        detail = "-> Hypershift Toggle"
    elif action_type == 0x05:
        detail = f"-> DPI Switch (0x{param2:02x})"
    else:
        detail = f"-> sub=0x{sub:02x} p1=0x{param1:02x} p2=0x{param2:02x}"

    return f"{action_name} {detail}"

def find_device(pcap):
    """Auto-detect bus_id and device_address for Razer device."""
    # Try common bus/device combos
    for bus in range(1, 10):
        for dev in range(1, 10):
            out = run(pcap, [
                "-Y", f"usb.bus_id=={bus} && usb.device_address=={dev} && usb.data_len>=90 && usb.data_len<=98",
                "-T", "fields", "-e", "frame.number",
                "-c", "1"
            ])
            if out.strip():
                # Verify it has Razer-like data
                out2 = run(pcap, [
                    "-Y", f"usb.bus_id=={bus} && usb.device_address=={dev} && usb.data_len>=90 && usb.data_len<=98",
                    "-T", "fields", "-e", "usb.data_fragment",
                    "-c", "5"
                ])
                for line in out2.split("\n"):
                    d = line.strip().replace(":", "")
                    if len(d) >= 180:
                        # Check end marker is 0x00
                        if int(d[178:180], 16) == 0x00:
                            print(f"Found Razer device on bus={bus} dev={dev}")
                            return bus, dev
    return None, None

def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_capture.py <pcapng_file> [bus_id] [device_address]")
        sys.exit(1)

    pcap = sys.argv[1]

    if len(sys.argv) >= 4:
        bus = int(sys.argv[2])
        dev = int(sys.argv[3])
    else:
        print("Auto-detecting Razer device...")
        bus, dev = find_device(pcap)
        if bus is None:
            print("ERROR: Could not find Razer device in capture!")
            sys.exit(1)

    print(f"\nAnalyzing: {pcap}")
    print(f"Device: bus={bus} dev={dev}")

    # Extract all Razer protocol packets
    out = run(pcap, [
        "-Y", f"usb.bus_id=={bus} && usb.device_address=={dev} && usb.data_len>=90 && usb.data_len<=98",
        "-T", "fields",
        "-e", "frame.number", "-e", "frame.time_relative",
        "-e", "usb.src", "-e", "usb.dst",
        "-e", "usb.data_fragment",
        "-E", "separator=|"
    ])

    all_parsed = []
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 5 or not parts[4]:
            continue
        parsed = parse_razer(parts[4])
        if not parsed:
            continue
        parsed["frame"] = parts[0].strip()
        parsed["time"] = parts[1].strip()
        parsed["direction"] = "OUT" if parts[2].strip() == "host" else "IN"
        all_parsed.append(parsed)

    print(f"Total Razer protocol packets: {len(all_parsed)}")

    # Command summary
    print("\n" + "=" * 80)
    print("  COMMAND SUMMARY")
    print("=" * 80)
    cmd_counts = Counter()
    for p in all_parsed:
        key = (p["cmd_class"], p["cmd_id"], p["direction"])
        cmd_counts[key] += 1

    for (cls, cmd, direction), count in sorted(cmd_counts.items()):
        cls_name = CMD_CLASS_NAMES.get(cls, f"0x{cls:02x}")
        print(f"  {cls_name:<12s} 0x{cls:02x}:0x{cmd:02x} [{direction}] x{count}")

    # =========================================================================
    print("\n" + "=" * 80)
    print("  BUTTON MAPPING WRITES (0x02:0x0c)")
    print("=" * 80)

    writes = [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c and p["direction"] == "OUT"]
    print(f"Total write commands: {len(writes)}")

    for i, p in enumerate(writes):
        b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)

        profile = b[0] if len(b) > 0 else "?"
        button_id = b[1] if len(b) > 1 else 0
        hypershift = b[2] if len(b) > 2 else 0

        layer = "HYPERSHIFT" if hypershift == 1 else "Normal"
        action_desc = decode_action(b)

        print(f"\n  [{i+1}] Frame #{p['frame']} t={p['time']}s")
        print(f"      Profile={profile} Button=0x{button_id:02x} Layer={layer}")
        print(f"      Action: {action_desc}")
        print(f"      Raw: [{payload_hex}]")

    # =========================================================================
    print("\n" + "=" * 80)
    print("  BUTTON MAPPING READS (0x02:0x8c) - RESPONSES")
    print("=" * 80)

    reads_resp = [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c and p["direction"] == "IN" and p["status"] == 3]
    print(f"Total read responses (status=OK): {len(reads_resp)}")

    # Group by button_id to show unique mappings
    button_mappings = {}
    for p in reads_resp:
        b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
        if len(b) >= 3:
            key = (b[0], b[1], b[2])  # profile, button_id, hypershift
            button_mappings[key] = (b, p)

    print(f"Unique button mappings read: {len(button_mappings)}")

    # Show non-default mappings (where action type != 0x00 or interesting)
    print("\n  All button mappings read back:")
    for (profile, btn_id, hs), (b, p) in sorted(button_mappings.items()):
        layer = "HS" if hs else "NM"
        action_desc = decode_action(b)
        payload_hex = " ".join(f"{x:02x}" for x in b)
        print(f"    P{profile} Btn=0x{btn_id:02x} [{layer}] {action_desc}  [{payload_hex}]")

    # =========================================================================
    print("\n" + "=" * 80)
    print("  MACRO/COMMIT COMMANDS (0x02:0x16)")
    print("=" * 80)

    commits = [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x16]
    print(f"Total 0x02:0x16 commands: {len(commits)}")
    for p in commits:
        b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)
        print(f"  #{p['frame']} t={p['time']}s [{p['direction']}] [{payload_hex}]")

    # =========================================================================
    print("\n" + "=" * 80)
    print("  PROFILE/HYPERSHIFT COMMANDS (0x0f:*)")
    print("=" * 80)

    prof_cmds = [p for p in all_parsed if p["cmd_class"] == 0x0f
                 and p["cmd_id"] != 0x03  # Skip LED color data
                 and p["cmd_id"] != 0x83]  # Skip LED read responses
    print(f"Total 0x0f commands (excl LED): {len(prof_cmds)}")
    for p in prof_cmds:
        b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 40), 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)
        status = STATUS_NAMES.get(p["status"], f"0x{p['status']:02x}")
        print(f"  #{p['frame']:>6s} t={p['time']:>12s}s [{p['direction']}] 0x0f:0x{p['cmd_id']:02x} "
              f"status={status:<7s} size={p['data_size']:>2d}  [{payload_hex}]")

    # =========================================================================
    print("\n" + "=" * 80)
    print("  CHRONOLOGICAL WRITE TIMELINE")
    print("=" * 80)
    print("  All non-LED OUT commands in time order:")

    out_cmds = [p for p in all_parsed
                if p["direction"] == "OUT"
                and not (p["cmd_class"] == 0x0f and p["cmd_id"] == 0x03)]
    out_cmds.sort(key=lambda p: float(p["time"]))

    for p in out_cmds:
        cls_name = CMD_CLASS_NAMES.get(p["cmd_class"], f"0x{p['cmd_class']:02x}")
        b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 40), 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)

        extra = ""
        if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c:
            extra = f"  ** BUTTON WRITE: {decode_action(b)}"

        print(f"  #{p['frame']:>6s} t={p['time']:>12s}s  {cls_name:<10s} 0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} "
              f"size={p['data_size']:>2d}  [{payload_hex}]{extra}")

    # =========================================================================
    print("\n" + "=" * 80)
    print("  PROTOCOL SUMMARY")
    print("=" * 80)

    print(f"\n  Total packets: {len(all_parsed)}")
    print(f"  Button writes (0x02:0x0c): {len(writes)}")
    print(f"  Button reads (0x02:0x8c OK): {len(reads_resp)}")
    print(f"  Commit/macro (0x02:0x16): {len(commits)}")

    if writes:
        print("\n  === DECODED BUTTON MAPPING CHANGES ===")
        for i, p in enumerate(writes):
            b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
            profile = b[0]
            button_id = b[1]
            hypershift = b[2]
            layer = "Hypershift" if hypershift else "Normal"
            print(f"  Change {i+1}: Button 0x{button_id:02x}, {layer} layer -> {decode_action(b)}")
            print(f"    Raw payload: {' '.join(f'{x:02x}' for x in b)}")


if __name__ == "__main__":
    main()
