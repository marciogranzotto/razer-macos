#!/usr/bin/env python3
"""
Analyze capture #2: razer-naga-6btns-change-button-2.pcapng
User performed: default "1" -> "a" -> mouse button -> multimedia key -> disabled -> back to "1"
Focus on 0x02:0x0c (button mapping WRITE) commands.
"""
import subprocess
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-6btns-change-button-2.pcapng"

def run(args, timeout=300):
    cmd = [TSHARK, "-r", PCAP] + args
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
    0x00: "None", 0x04: "a", 0x05: "b", 0x06: "c", 0x07: "d", 0x08: "e",
    0x1e: "1", 0x1f: "2", 0x20: "3", 0x21: "4", 0x22: "5", 0x23: "6",
    0x24: "7", 0x25: "8", 0x26: "9", 0x27: "0",
    0x28: "Enter", 0x29: "Escape", 0x2a: "Backspace", 0x2b: "Tab",
    0x2c: "Space",
    0x50: "Left", 0x51: "Down", 0x52: "Up", 0x4f: "Right",
    0x59: "KP1", 0x5a: "KP2", 0x5b: "KP3", 0x5c: "KP4",
    0x5d: "KP5", 0x5e: "KP6", 0x5f: "KP7", 0x60: "KP8",
    0x61: "KP9", 0x62: "KP0",
}

CONSUMER_CODES = {
    0x00cd: "Play/Pause", 0x00b5: "Next Track", 0x00b6: "Prev Track",
    0x00e9: "Volume Up", 0x00ea: "Volume Down", 0x00e2: "Mute",
    0x0183: "Media Player", 0x018a: "Email", 0x0192: "Calculator",
    0x0194: "Local Browser", 0x0221: "Search", 0x0223: "Home Page",
    0x0224: "Back", 0x0225: "Forward", 0x0226: "Stop", 0x0227: "Refresh",
}

def main():
    # Step 1: Find the right bus/device for this capture
    print("=" * 75)
    print("  STEP 1: IDENTIFY DEVICE IN CAPTURE")
    print("=" * 75)

    # This capture was on USBPcap5 only, try common addresses
    all_parsed = []
    for bus in range(1, 10):
        for dev in range(1, 10):
            out = run([
                "-Y", f"usb.bus_id=={bus} && usb.device_address=={dev} && usb.data_len>=90 && usb.data_len<=98",
                "-T", "fields", "-e", "frame.number",
                "-E", "separator=|",
                "-c", "5"  # just check first 5
            ])
            count = len([l for l in out.split("\n") if l.strip()])
            if count > 0:
                print(f"  Bus {bus} Dev {dev}: {count}+ Razer-sized packets")

    # Based on previous finding, capture 2 is on Bus 5 Dev 2
    # But let's try all combinations that had packets
    print("\n  Trying Bus 5 Dev 2 (expected from previous analysis)...")

    for bus, dev in [(5, 2), (1, 2), (2, 2), (3, 2), (1, 1), (2, 1)]:
        out = run([
            "-Y", f"usb.bus_id=={bus} && usb.device_address=={dev} && usb.data_len>=90 && usb.data_len<=98",
            "-T", "fields",
            "-e", "frame.number", "-e", "frame.time_relative",
            "-e", "usb.src", "-e", "usb.dst",
            "-e", "usb.data_fragment",
            "-E", "separator=|"
        ])
        for line in out.split("\n"):
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) < 5 or not parts[4]:
                continue
            parsed = parse_razer(parts[4])
            if not parsed:
                continue
            parsed["frame"] = parts[0]
            parsed["time"] = parts[1]
            parsed["direction"] = "OUT" if parts[2] == "host" else "IN"
            parsed["bus_dev"] = f"{bus}.{dev}"
            all_parsed.append(parsed)

    print(f"\n  Total Razer protocol packets found: {len(all_parsed)}")
    if not all_parsed:
        print("  ERROR: No packets found! Trying broader search...")
        # Try without bus/dev filter
        out = run([
            "-Y", "usb.data_len>=90 && usb.data_len<=98",
            "-T", "fields",
            "-e", "frame.number", "-e", "frame.time_relative",
            "-e", "usb.src", "-e", "usb.dst",
            "-e", "usb.bus_id", "-e", "usb.device_address",
            "-e", "usb.data_fragment",
            "-E", "separator=|",
            "-c", "20"
        ])
        print("  First 20 packets with data_len 90-98:")
        for line in out.split("\n"):
            if line.strip():
                parts = line.split("|")
                if len(parts) >= 7 and parts[6]:
                    parsed = parse_razer(parts[6])
                    if parsed:
                        print(f"    Bus={parts[4]} Dev={parts[5]} Frame={parts[0]} "
                              f"cls=0x{parsed['cmd_class']:02x} id=0x{parsed['cmd_id']:02x}")
                        parsed["frame"] = parts[0]
                        parsed["time"] = parts[1]
                        parsed["direction"] = "OUT" if parts[2] == "host" else "IN"
                        parsed["bus_dev"] = f"{parts[4]}.{parts[5]}"
                        all_parsed.append(parsed)

        if not all_parsed:
            print("  Still no packets. Exiting.")
            return

    # Group by bus_dev
    by_bus = Counter(p["bus_dev"] for p in all_parsed)
    print(f"  Packets by bus.dev: {dict(by_bus)}")

    # =========================================================================
    print("\n" + "=" * 75)
    print("  STEP 2: ALL COMMAND CLASSES AND IDS")
    print("=" * 75)

    cmd_counts = Counter((p["cmd_class"], p["cmd_id"], p["direction"]) for p in all_parsed)
    for (cls, cid, direction), count in sorted(cmd_counts.items()):
        print(f"  0x{cls:02x}:0x{cid:02x} [{direction}]: {count}")

    # =========================================================================
    print("\n" + "=" * 75)
    print("  STEP 3: BUTTON MAPPING WRITE COMMANDS (0x02:0x0c)")
    print("=" * 75)

    writes = [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c and p["direction"] == "OUT"]
    print(f"\n  Total 0x02:0x0c OUT (write) commands: {len(writes)}")

    for p in writes:
        b = [int(p["payload"][i:i+2], 16) for i in range(0, p["data_size"]*2, 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)

        profile = b[0] if len(b) > 0 else -1
        button_id = b[1] if len(b) > 1 else -1
        hypershift = b[2] if len(b) > 2 else -1
        action_type = b[3] if len(b) > 3 else -1

        # Decode action
        action_desc = "?"
        if action_type == 0x00:
            action_desc = "DISABLED (no action)"
        elif action_type == 0x01:
            # Mouse button
            mouse_btn = b[4] if len(b) > 4 else 0
            mouse_names = {0x01: "Left Click", 0x02: "Right Click", 0x03: "Middle Click",
                          0x04: "Back", 0x05: "Forward", 0x06: "Btn6", 0x07: "Btn7",
                          0x08: "Btn8", 0x09: "Btn9"}
            action_desc = f"MOUSE BUTTON: {mouse_names.get(mouse_btn, f'0x{mouse_btn:02x}')}"
        elif action_type == 0x02:
            # Keyboard key
            modifier = b[4] if len(b) > 4 else 0
            keycode = b[6] if len(b) > 6 else 0
            key_name = HID_KEYCODES.get(keycode, f"0x{keycode:02x}")
            mod_parts = []
            if modifier & 0x01: mod_parts.append("LCtrl")
            if modifier & 0x02: mod_parts.append("LShift")
            if modifier & 0x04: mod_parts.append("LAlt")
            if modifier & 0x08: mod_parts.append("LGui")
            if modifier & 0x10: mod_parts.append("RCtrl")
            if modifier & 0x20: mod_parts.append("RShift")
            if modifier & 0x40: mod_parts.append("RAlt")
            if modifier & 0x80: mod_parts.append("RGui")
            mod_str = "+".join(mod_parts) + "+" if mod_parts else ""
            action_desc = f"KEYBOARD: {mod_str}{key_name}"
        elif action_type == 0x03:
            # Consumer/Multimedia key
            consumer_code = (b[4] << 8 | b[5]) if len(b) > 5 else 0
            consumer_name = CONSUMER_CODES.get(consumer_code, f"0x{consumer_code:04x}")
            action_desc = f"MULTIMEDIA: {consumer_name}"
        elif action_type == 0x05:
            action_desc = "DEFAULT (restore default binding)"
        elif action_type == 0x0a:
            action_desc = "MACRO"
        elif action_type == 0x0b:
            action_desc = "DOUBLE-CLICK"

        hs_str = "Hypershift" if hypershift == 1 else "Normal"
        print(f"\n  #{p['frame']:>6s} t={p['time']:>12s}s  [{payload_hex}]")
        print(f"    Profile={profile} Button=0x{button_id:02x} Layer={hs_str}")
        print(f"    Action: {action_desc}")

    # =========================================================================
    print("\n" + "=" * 75)
    print("  STEP 4: BUTTON MAPPING READ COMMANDS (0x02:0x8c)")
    print("=" * 75)

    reads_out = [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c and p["direction"] == "OUT"]
    reads_in = [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c and p["direction"] == "IN"]
    print(f"\n  Read requests (OUT): {len(reads_out)}")
    print(f"  Read responses (IN): {len(reads_in)}")

    # Show unique read requests
    unique_reads = {}
    for p in reads_out:
        b = [int(p["payload"][i:i+2], 16) for i in range(0, p["data_size"]*2, 2)]
        key = tuple(b[:3])  # profile, button_id, hypershift
        if key not in unique_reads:
            unique_reads[key] = p

    print(f"  Unique button reads: {len(unique_reads)}")
    for (profile, btn_id, hs), p in sorted(unique_reads.items()):
        hs_str = "HS" if hs == 1 else "NL"
        print(f"    Profile={profile} Button=0x{btn_id:02x} Layer={hs_str}")

    # Show read responses with actual bindings
    print("\n  Read responses (current bindings):")
    for p in reads_in[:50]:  # First 50 responses
        b = [int(p["payload"][i:i+2], 16) for i in range(0, p["data_size"]*2, 2)]
        if len(b) < 4:
            continue
        profile = b[0]
        button_id = b[1]
        hypershift = b[2]
        action_type = b[3]
        payload_hex = " ".join(f"{x:02x}" for x in b)

        action_desc = "?"
        if action_type == 0x00:
            action_desc = "Disabled"
        elif action_type == 0x01:
            mouse_btn = b[4] if len(b) > 4 else 0
            mouse_names = {0x01: "Left", 0x02: "Right", 0x03: "Middle",
                          0x04: "Back", 0x05: "Forward"}
            action_desc = f"Mouse:{mouse_names.get(mouse_btn, f'0x{mouse_btn:02x}')}"
        elif action_type == 0x02:
            keycode = b[6] if len(b) > 6 else 0
            key_name = HID_KEYCODES.get(keycode, f"0x{keycode:02x}")
            action_desc = f"Key:{key_name}"
        elif action_type == 0x03:
            consumer_code = (b[4] << 8 | b[5]) if len(b) > 5 else 0
            action_desc = f"Media:0x{consumer_code:04x}"
        elif action_type == 0x05:
            action_desc = "Default"

        hs_str = "HS" if hypershift == 1 else "NL"
        print(f"    Btn=0x{button_id:02x} {hs_str} -> {action_desc:20s}  [{payload_hex}]")

    # =========================================================================
    print("\n" + "=" * 75)
    print("  STEP 5: OTHER INTERESTING COMMANDS")
    print("=" * 75)

    # 0x02:0x16 - macro config / commit
    macro_16 = [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x16 and p["direction"] == "OUT"]
    print(f"\n  0x02:0x16 (Macro commit) OUT: {len(macro_16)}")
    for p in macro_16:
        b = [int(p["payload"][i:i+2], 16) for i in range(0, p["data_size"]*2, 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)
        print(f"    #{p['frame']:>6s} t={p['time']:>12s}s  [{payload_hex}]")

    # 0x0f:0x02 - profile
    prof = [p for p in all_parsed if p["cmd_class"] == 0x0f and p["cmd_id"] == 0x02 and p["direction"] == "OUT"]
    print(f"\n  0x0f:0x02 (Profile) OUT: {len(prof)}")
    for p in prof:
        b = [int(p["payload"][i:i+2], 16) for i in range(0, p["data_size"]*2, 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)
        print(f"    #{p['frame']:>6s} t={p['time']:>12s}s  [{payload_hex}]")

    # 0x0f:0x04 and 0x0f:0x84
    for cid in [0x04, 0x84]:
        cmds = [p for p in all_parsed if p["cmd_class"] == 0x0f and p["cmd_id"] == cid]
        print(f"\n  0x0f:0x{cid:02x} (total): {len(cmds)}")
        for p in cmds:
            b = [int(p["payload"][i:i+2], 16) for i in range(0, p["data_size"]*2, 2)]
            payload_hex = " ".join(f"{x:02x}" for x in b)
            print(f"    #{p['frame']:>6s} t={p['time']:>12s}s [{p['direction']}] [{payload_hex}]")

    # =========================================================================
    print("\n" + "=" * 75)
    print("  STEP 6: CHRONOLOGICAL TIMELINE OF BUTTON CHANGES")
    print("=" * 75)
    print("  Expected sequence: default '1' -> 'a' -> mouse btn -> multimedia -> disabled -> '1'")

    # Get all non-LED, non-read commands sorted by time
    interesting = [p for p in all_parsed
                   if p["direction"] == "OUT"
                   and not (p["cmd_class"] == 0x0f and p["cmd_id"] == 0x03)  # skip LED
                   and not (p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c)  # skip reads
                   ]
    interesting.sort(key=lambda p: float(p["time"]))

    CMD_NAMES = {
        (0x02, 0x0c): "BTN_WRITE",
        (0x02, 0x16): "MACRO_CFG",
        (0x0f, 0x02): "PROFILE",
        (0x0f, 0x04): "HS_CFG",
        (0x0f, 0x80): "PROF_READ",
        (0x0f, 0x84): "HS_READ",
    }

    for p in interesting:
        cmd_name = CMD_NAMES.get((p["cmd_class"], p["cmd_id"]), f"0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x}")
        b = [int(p["payload"][i:i+2], 16) for i in range(0, min(p["data_size"]*2, 20), 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)
        print(f"  #{p['frame']:>6s} t={p['time']:>12s}s  {cmd_name:<12s} size={p['data_size']:>2d}  [{payload_hex}]")

    # =========================================================================
    print("\n" + "=" * 75)
    print("  SUMMARY")
    print("=" * 75)
    print(f"  Total packets: {len(all_parsed)}")
    print(f"  Write commands (0x02:0x0c): {len(writes)}")
    print(f"  Read requests (0x02:0x8c): {len(reads_out)}")
    print(f"  Read responses (0x02:0x8c): {len(reads_in)}")


if __name__ == "__main__":
    main()
