#!/usr/bin/env python3
"""
Capture #3 refined analysis - corrected action type decoding.
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
    0x1e: "1", 0x1f: "2", 0x20: "3", 0x21: "4", 0x22: "5", 0x23: "6",
    0x24: "7", 0x25: "8", 0x26: "9", 0x27: "0",
    0x28: "Enter", 0x29: "Escape", 0x2a: "Backspace", 0x2b: "Tab",
    0x2c: "Space",
    0x59: "KP1", 0x5a: "KP2", 0x5b: "KP3", 0x5c: "KP4",
    0x5d: "KP5", 0x5e: "KP6", 0x5f: "KP7", 0x60: "KP8",
    0x61: "KP9", 0x62: "KP0",
}

CONSUMER_CODES = {
    0x00cd: "Play/Pause", 0x00b5: "Next Track", 0x00b6: "Prev Track",
    0x00e9: "Volume Up", 0x00ea: "Volume Down", 0x00e2: "Mute",
}

def main():
    print("=" * 80)
    print("  REFINED ANALYSIS OF BUTTON MAPPING WRITES")
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

    writes = sorted(
        [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c],
        key=lambda p: float(p["time"])
    )

    print(f"\nTotal button mapping writes: {len(writes)}")
    print(f"\nUser's stated sequence:")
    print(f"  1. default '1' -> keyboard 'a'")
    print(f"  2. keyboard 'a' -> mouse button")
    print(f"  3. mouse button -> multimedia key")
    print(f"  4. multimedia key -> disabled")
    print(f"  5. disabled -> back to '1'")

    print(f"\n{'='*80}")
    print(f"  DETAILED BYTE-BY-BYTE ANALYSIS")
    print(f"{'='*80}")

    expected = [
        "keyboard 'a'",
        "mouse button",
        "multimedia key",
        "disabled",
        "back to '1'"
    ]

    for i, p in enumerate(writes):
        b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)
        exp = expected[i] if i < len(expected) else "?"

        print(f"\n  === Write #{i+1}: Expected '{exp}' ===")
        print(f"  Frame #{p['frame']}  t={p['time']}s")
        print(f"  Raw: [{payload_hex}]")
        print(f"  Byte[0] = 0x{b[0]:02x}  Profile: {b[0]}")
        print(f"  Byte[1] = 0x{b[1]:02x}  Button ID: 0x{b[1]:02x}")
        print(f"  Byte[2] = 0x{b[2]:02x}  Layer: {'Hypershift' if b[2] == 1 else 'Normal'}")
        print(f"  Byte[3] = 0x{b[3]:02x}  Action Type")
        for j in range(4, min(len(b), 10)):
            print(f"  Byte[{j}] = 0x{b[j]:02x}  Action param {j-3}")

    # Now correlate with expected actions
    print(f"\n{'='*80}")
    print(f"  PROTOCOL DEDUCTION")
    print(f"{'='*80}")

    print("""
  Write #1: default -> keyboard 'a'
    [01 50 00 02 02 00 04 00 00 00]
    Action type = 0x02 -> KEYBOARD KEY
    Byte[4] = 0x02: sub_type? Always 0x02 for keyboard?
    Byte[5] = 0x00: modifier byte (0 = no modifiers)
    Byte[6] = 0x04: HID keycode = 'a'
    Bytes[7-9] = 0x00: padding

  Write #2: keyboard 'a' -> mouse button
    [01 50 00 01 01 03 00 00 00 00]
    Action type = 0x01 -> MOUSE BUTTON
    Byte[4] = 0x01: sub_type? Always 0x01 for mouse?
    Byte[5] = 0x03: mouse button ID = Middle Click (3)

    Wait - user said "mouse button", which one?
    Could be Left=1, Right=2, Middle=3, Back=4, Forward=5
    0x03 = Middle Click if using standard HID mouse button numbering
    But if user chose "Mouse Button 4 (Back)" in Synapse,
    the value might map differently.

  Write #3: mouse button -> multimedia key
    [01 50 00 0a 02 00 cd 00 00 00]
    Action type = 0x0a -> MULTIMEDIA/CONSUMER KEY
    Byte[4] = 0x02: consumer usage page?
    Byte[5:6] = 0x00cd: consumer usage code = Play/Pause

    So consumer code = 0x00cd = Play/Pause
    Encoding: action_type=0x0a, then [page?][hi][lo]
    OR: [0x02][0x00][0xcd] where bytes 5-6 = big-endian consumer code

  Write #4: multimedia key -> disabled
    [01 50 00 00 00 00 00 00 00 00]
    Action type = 0x00 -> DISABLED
    All remaining bytes = 0x00
    """)

    # Check if there are any other 0x02 commands we might be missing
    print(f"\n{'='*80}")
    print(f"  ALL 0x02 CLASS COMMANDS")
    print(f"{'='*80}")

    macro_cmds = [p for p in all_parsed if p["cmd_class"] == 0x02]
    cmd_id_counts = Counter(p["cmd_id"] for p in macro_cmds)
    for cid, count in sorted(cmd_id_counts.items()):
        print(f"  0x02:0x{cid:02x} -> {count} packets")

    # Check for 0x05 class commands (profile-based button config)
    print(f"\n  0x05 class (Mouse Config) commands:")
    mc = [p for p in all_parsed if p["cmd_class"] == 0x05]
    if mc:
        for p in mc:
            b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
            print(f"    0x05:0x{p['cmd_id']:02x} [{' '.join(f'{x:02x}' for x in b)}]")
    else:
        print(f"    None found")

    # Check how the capture ends - was the last write "back to 1"?
    print(f"\n{'='*80}")
    print(f"  CAPTURE TIMING ANALYSIS")
    print(f"{'='*80}")

    # Get total capture duration
    last_frame = run(["-T", "fields", "-e", "frame.time_relative", "-c", "1",
                      "-Y", "frame.number==99999999"])
    # Get last packet time
    all_times = [float(p["time"]) for p in all_parsed]
    if all_times:
        print(f"  First Razer packet: {min(all_times):.3f}s")
        print(f"  Last Razer packet:  {max(all_times):.3f}s")
        print(f"  Write timestamps:")
        for i, p in enumerate(writes):
            t = float(p["time"])
            desc = expected[i] if i < len(expected) else "?"
            print(f"    Write #{i+1}: t={t:.3f}s  ({desc})")
            if i > 0:
                delta = t - float(writes[i-1]["time"])
                print(f"      (delta = {delta:.1f}s from previous)")

    # Check for other bus/dev for GET_REPORT responses
    print(f"\n{'='*80}")
    print(f"  LOOKING FOR GET_REPORT RESPONSES ON BUS 2")
    print(f"{'='*80}")

    # Try Bus 2 Dev 1 (keyboard interface of dongle)
    for dev in [1, 2, 3]:
        out3 = run([
            "-Y", f"usb.bus_id==2 && usb.device_address=={dev} && usb.src!=host",
            "-T", "fields",
            "-e", "frame.number", "-e", "usb.data_len", "-e", "usb.data_fragment",
            "-E", "separator=|",
            "-c", "5"
        ])
        lines3 = [l for l in out3.split("\n") if l.strip()]
        if lines3:
            print(f"\n  Dev {dev} responses (first 5):")
            for l in lines3:
                parts = l.split("|")
                dlen = parts[1] if len(parts) > 1 else "?"
                data_frag = parts[2] if len(parts) > 2 else ""
                # Try to parse as Razer
                if data_frag:
                    parsed = parse_razer(data_frag)
                    if parsed:
                        print(f"    Frame={parts[0]} dlen={dlen} -> Razer 0x{parsed['cmd_class']:02x}:0x{parsed['cmd_id']:02x} status=0x{parsed['status']:02x}")
                    else:
                        print(f"    Frame={parts[0]} dlen={dlen} (not Razer)")
                else:
                    print(f"    Frame={parts[0]} dlen={dlen}")


if __name__ == "__main__":
    main()
