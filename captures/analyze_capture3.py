#!/usr/bin/env python3
"""
Analyze capture #3: razer-naga-6btns-change-button-3.pcapng
This capture has the Razer dongle on Bus 2 Dev 3.
User performed: default "1" -> "a" -> mouse button -> multimedia key -> disabled -> back to "1"
Focus on 0x02:0x0c (button mapping WRITE) commands.
"""
import subprocess
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-6btns-change-button-3.pcapng"

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
    0x09: "f", 0x0a: "g", 0x0b: "h", 0x0c: "i", 0x0d: "j",
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

MOUSE_BUTTONS = {
    0x01: "Left Click", 0x02: "Right Click", 0x03: "Middle Click",
    0x04: "Back (Button 4)", 0x05: "Forward (Button 5)",
    0x06: "Button 6", 0x07: "Button 7",
    0x08: "Button 8", 0x09: "Button 9",
}

def decode_action(b):
    """Decode button action from payload bytes starting at index 3."""
    if len(b) < 4:
        return "? (too short)"
    action_type = b[3]

    if action_type == 0x00:
        return "DISABLED (no action)"
    elif action_type == 0x01:
        # Mouse button
        mouse_btn = b[4] if len(b) > 4 else 0
        return f"MOUSE BUTTON: {MOUSE_BUTTONS.get(mouse_btn, f'0x{mouse_btn:02x}')}"
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
        return f"KEYBOARD: {mod_str}{key_name} (mod=0x{modifier:02x} key=0x{keycode:02x})"
    elif action_type == 0x03:
        # Consumer/Multimedia key
        if len(b) > 5:
            consumer_code = (b[4] << 8) | b[5]
        else:
            consumer_code = 0
        consumer_name = CONSUMER_CODES.get(consumer_code, f"0x{consumer_code:04x}")
        return f"MULTIMEDIA: {consumer_name} (code=0x{consumer_code:04x})"
    elif action_type == 0x05:
        sub = b[4] if len(b) > 4 else 0
        param = b[5] if len(b) > 5 else 0
        return f"DEFAULT (restore default, sub=0x{sub:02x} param=0x{param:02x})"
    elif action_type == 0x06:
        return "HYPERSHIFT (toggle Hypershift layer)"
    elif action_type == 0x0a:
        return "MACRO"
    elif action_type == 0x0b:
        return "DOUBLE-CLICK"
    else:
        return f"UNKNOWN type=0x{action_type:02x}"


def main():
    print("=" * 80)
    print("  RAZER NAGA V2 PRO - CAPTURE #3 ANALYSIS")
    print("  razer-naga-6btns-change-button-3.pcapng")
    print("=" * 80)

    # Get all Razer protocol packets from Bus 2 Dev 3
    all_parsed = []
    out = run([
        "-Y", "usb.bus_id==2 && usb.device_address==3 && usb.data_len>=90 && usb.data_len<=98",
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
        all_parsed.append(parsed)

    print(f"\nTotal Razer protocol packets: {len(all_parsed)}")
    out_pkts = [p for p in all_parsed if p["direction"] == "OUT"]
    in_pkts = [p for p in all_parsed if p["direction"] == "IN"]
    print(f"  OUT (host->device): {len(out_pkts)}")
    print(f"  IN  (device->host): {len(in_pkts)}")

    # Also try to get response packets via GET_REPORT
    # These come back on the same endpoint with the Razer payload
    get_report_responses = []
    out2 = run([
        "-Y", "usb.bus_id==2 && usb.device_address==3 && usb.src!=host && usb.data_len>=90",
        "-T", "fields",
        "-e", "frame.number", "-e", "frame.time_relative",
        "-e", "usb.src", "-e", "usb.dst",
        "-e", "usb.data_fragment",
        "-E", "separator=|"
    ])
    for line in out2.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 5 or not parts[4]:
            continue
        parsed = parse_razer(parts[4])
        if parsed:
            parsed["frame"] = parts[0]
            parsed["time"] = parts[1]
            parsed["direction"] = "IN"
            if parsed not in all_parsed:
                get_report_responses.append(parsed)
                all_parsed.append(parsed)

    if get_report_responses:
        print(f"  Additional GET_REPORT responses: {len(get_report_responses)}")

    # =========================================================================
    print("\n" + "=" * 80)
    print("  COMMAND DISTRIBUTION")
    print("=" * 80)

    cmd_counts = Counter((p["cmd_class"], p["cmd_id"], p["direction"]) for p in all_parsed)
    for (cls, cid, direction), count in sorted(cmd_counts.items()):
        cls_names = {0x00: "General", 0x02: "Macro", 0x03: "LED", 0x05: "Mouse",
                    0x0f: "HyperProf", 0x15: "ExtCfg"}
        cls_name = cls_names.get(cls, f"0x{cls:02x}")
        print(f"  {cls_name:12s} 0x{cls:02x}:0x{cid:02x} [{direction}]: {count}")

    # =========================================================================
    print("\n" + "=" * 80)
    print("  BUTTON MAPPING WRITE COMMANDS (0x02:0x0c)")
    print("  Expected: 5 changes (default->a, ->mouse, ->multimedia, ->disabled, ->1)")
    print("=" * 80)

    writes = sorted(
        [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c and p["direction"] == "OUT"],
        key=lambda p: float(p["time"])
    )
    print(f"\n  Total button mapping WRITE commands: {len(writes)}")

    for i, p in enumerate(writes):
        b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)

        profile = b[0] if len(b) > 0 else -1
        button_id = b[1] if len(b) > 1 else -1
        hypershift = b[2] if len(b) > 2 else -1

        hs_str = "Hypershift" if hypershift == 1 else "Normal"
        action_desc = decode_action(b)

        print(f"\n  --- Write #{i+1} ---")
        print(f"  Frame #{p['frame']:>6s}  t={p['time']:>12s}s")
        print(f"  Raw:     [{payload_hex}]")
        print(f"  Profile: {profile}")
        print(f"  Button:  0x{button_id:02x}")
        print(f"  Layer:   {hs_str}")
        print(f"  Action:  {action_desc}")

    # =========================================================================
    print("\n" + "=" * 80)
    print("  BUTTON MAPPING READ RESPONSES (0x02:0x8c IN)")
    print("=" * 80)

    reads_in = sorted(
        [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c and p["direction"] == "IN"],
        key=lambda p: float(p["time"])
    )
    reads_out = [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c and p["direction"] == "OUT"]
    print(f"\n  Read requests (OUT): {len(reads_out)}")
    print(f"  Read responses (IN): {len(reads_in)}")

    if reads_in:
        print("\n  Current button bindings from read responses:")
        for p in reads_in:
            b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
            if len(b) < 4:
                continue
            profile = b[0]
            button_id = b[1]
            hypershift = b[2]
            hs_str = "HS" if hypershift == 1 else "NL"
            action_desc = decode_action(b)
            payload_hex = " ".join(f"{x:02x}" for x in b)
            print(f"    Btn=0x{button_id:02x} {hs_str} -> {action_desc}")
            print(f"      [{payload_hex}]")

    # =========================================================================
    print("\n" + "=" * 80)
    print("  CHRONOLOGICAL TIMELINE (non-LED, non-read)")
    print("=" * 80)

    interesting = sorted(
        [p for p in all_parsed
         if p["direction"] == "OUT"
         and not (p["cmd_class"] == 0x0f and p["cmd_id"] == 0x03)
         and not (p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c)],
        key=lambda p: float(p["time"])
    )

    CMD_NAMES = {
        (0x02, 0x0c): "BTN_WRITE",
        (0x02, 0x16): "MACRO_CFG",
        (0x0f, 0x02): "PROFILE",
        (0x0f, 0x04): "HS_CFG",
        (0x0f, 0x80): "PROF_READ",
        (0x0f, 0x84): "HS_READ",
        (0x00, 0x00): "DEVICE_INFO",
    }

    for p in interesting:
        cmd_name = CMD_NAMES.get((p["cmd_class"], p["cmd_id"]),
                                 f"0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x}")
        b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 20), 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)

        extra = ""
        if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c:
            extra = " << " + decode_action(b)

        print(f"  #{p['frame']:>6s} t={p['time']:>12s}s  {cmd_name:<12s} size={p['data_size']:>2d}  [{payload_hex}]{extra}")

    # =========================================================================
    print("\n" + "=" * 80)
    print("  SUMMARY: BUTTON MAPPING PROTOCOL SPECIFICATION")
    print("=" * 80)
    print("""
  Command Class: 0x02 (Macro/Button Config)
  Write Command ID: 0x0c
  Read Command ID:  0x8c (0x80 | 0x0c)
  Data Size: 10

  Payload Structure:
  Byte[0]: Profile slot (0x01 = profile 1)
  Byte[1]: Button ID
  Byte[2]: Layer (0x00 = Normal, 0x01 = Hypershift)
  Byte[3]: Action type
  Byte[4-9]: Action parameters (vary by type)

  Action Types:
  0x00 = Disabled
  0x01 = Mouse button      [type:1][button_id:1][00 00 00 00]
  0x02 = Keyboard key       [type:1][modifier:1][00][keycode:1][00 00]
  0x03 = Multimedia/Consumer [type:1][consumer_hi:1][consumer_lo:1][00 00 00]
  0x05 = Default (restore)  [type:1][sub:1][param:1][00 00 00]
  0x06 = Hypershift toggle

  Button IDs (6-button side panel):
  0x50 = Side button 1 (top)
  0x51 = Side button 2
  0x52 = Side button 3
  0x53 = Side button 4
  0x54 = Side button 5
  0x55 = Side button 6 (bottom)
    """)


if __name__ == "__main__":
    main()
