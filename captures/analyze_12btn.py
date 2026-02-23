#!/usr/bin/env python3
"""
Analyze capture: razer-naga-12btns-change-button-1.pcapng
12-button panel, changed button 12 through 10 action types.
"""
import subprocess
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-1.pcapng"

def run(args, timeout=600):
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

def main():
    # Step 1: Find the device
    print("=" * 80)
    print("  STEP 1: IDENTIFY DEVICE")
    print("=" * 80)

    # Check first few packets to identify bus/dev
    out = run(["-c", "30", "-T", "fields",
               "-e", "frame.number", "-e", "usb.bus_id", "-e", "usb.device_address",
               "-e", "usb.data_len", "-e", "usb.src", "-e", "usb.dst",
               "-E", "separator=|"])
    print("First 30 packets:")
    for line in out.split("\n"):
        if line.strip():
            print(f"  {line}")

    # Known from packet inspection: Bus 2 Dev 3
    bus, dev = 2, 3
    print(f"Using Bus {bus} Dev {dev} (known from packet inspection)")

    # Step 2: Extract all Razer protocol packets
    print("\n" + "=" * 80)
    print("  STEP 2: EXTRACT RAZER PACKETS")
    print("=" * 80)

    all_parsed = []
    # Don't filter by data_len (tshark comparison issues), get all and filter in Python
    out = run([
        "-Y", f"usb.bus_id=={bus} && usb.device_address=={dev}",
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
        parsed["frame"] = parts[0].strip()
        parsed["time"] = parts[1].strip()
        parsed["direction"] = "OUT" if "host" in parts[2] else "IN"
        all_parsed.append(parsed)

    print(f"Total Razer packets: {len(all_parsed)}")
    print(f"  OUT: {sum(1 for p in all_parsed if p['direction'] == 'OUT')}")
    print(f"  IN:  {sum(1 for p in all_parsed if p['direction'] == 'IN')}")

    # Step 3: Command distribution
    print("\n" + "=" * 80)
    print("  STEP 3: COMMAND DISTRIBUTION")
    print("=" * 80)

    cmd_counts = Counter((p["cmd_class"], p["cmd_id"], p["direction"]) for p in all_parsed)
    for (cls, cid, direction), count in sorted(cmd_counts.items()):
        cls_names = {0x00: "General", 0x02: "Macro/Btn", 0x03: "LED", 0x05: "Mouse",
                    0x07: "CustomFX", 0x09: "DPI", 0x0f: "HyperProf", 0x15: "ExtCfg"}
        cls_name = cls_names.get(cls, f"0x{cls:02x}")
        print(f"  {cls_name:12s} 0x{cls:02x}:0x{cid:02x} [{direction}]: {count}")

    # Step 4: Button mapping WRITES
    print("\n" + "=" * 80)
    print("  STEP 4: BUTTON MAPPING WRITES (0x02:0x0c)")
    print("  Expected 10 changes to button 12 of 12-btn panel")
    print("=" * 80)

    writes = sorted(
        [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c and p["direction"] == "OUT"],
        key=lambda p: float(p["time"])
    )
    print(f"\nTotal writes: {len(writes)}")

    expected = [
        'Keyboard "a"',
        'Mouse "Scroll Click" (Middle)',
        'Scrolling "Cycle Up Scroll Wheel Stages"',
        'Sensitivity Clutch (X=800, Y=2550 DPI)',
        'Macro 1 - Play once',
        'Macro 1 - Queue',
        'Razer Hypershift modifier',
        'Multimedia Volume Down',
        'Disable',
        'Default ("=" key)',
    ]

    for i, p in enumerate(writes):
        b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)

        exp = expected[i] if i < len(expected) else "?"

        print(f"\n  === Write #{i+1}: Expected: {exp} ===")
        print(f"  Frame #{p['frame']}  t={p['time']}s")
        print(f"  Raw: [{payload_hex}]")
        print(f"  Profile={b[0]}  Button=0x{b[1]:02x}  Layer={'HS' if b[2] else 'Normal'}")
        print(f"  Action type = 0x{b[3]:02x}")
        for j in range(3, min(len(b), 10)):
            print(f"    Byte[{j}] = 0x{b[j]:02x} ({b[j]:3d})")

    # Step 5: Button mapping READS (to see default bindings and button IDs)
    print("\n" + "=" * 80)
    print("  STEP 5: BUTTON MAPPING READS (0x02:0x8c)")
    print("=" * 80)

    reads_out = sorted(
        [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c and p["direction"] == "OUT"],
        key=lambda p: float(p["time"])
    )
    reads_in = sorted(
        [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c and p["direction"] == "IN"],
        key=lambda p: float(p["time"])
    )
    print(f"\n  Read requests (OUT): {len(reads_out)}")
    print(f"  Read responses (IN): {len(reads_in)}")

    if reads_out:
        print("\n  Read requests (button IDs queried):")
        for p in reads_out:
            b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
            profile = b[0] if len(b) > 0 else 0
            button_id = b[1] if len(b) > 1 else 0
            hypershift = b[2] if len(b) > 2 else 0
            hs_str = "HS" if hypershift == 1 else "NL"
            print(f"    P{profile} Btn=0x{button_id:02x} {hs_str}")

    if reads_in:
        print("\n  Read responses (current bindings):")
        for p in reads_in:
            b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
            payload_hex = " ".join(f"{x:02x}" for x in b)
            if len(b) < 4:
                continue
            print(f"    Btn=0x{b[1]:02x} {'HS' if b[2] else 'NL'} type=0x{b[3]:02x} [{payload_hex}]")

    # Step 6: DPI commands (for sensitivity clutch)
    print("\n" + "=" * 80)
    print("  STEP 6: DPI COMMANDS (0x09)")
    print("=" * 80)

    dpi_cmds = sorted(
        [p for p in all_parsed if p["cmd_class"] == 0x09],
        key=lambda p: float(p["time"])
    )
    print(f"\n  Total DPI commands: {len(dpi_cmds)}")
    for p in dpi_cmds:
        b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 40), 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)
        print(f"    #{p['frame']} t={p['time']}s [{p['direction']}] 0x09:0x{p['cmd_id']:02x} size={p['data_size']} [{payload_hex}]")

    # Step 7: Macro commands
    print("\n" + "=" * 80)
    print("  STEP 7: MACRO-RELATED COMMANDS (0x02:0x16, 0x02:0x12, etc)")
    print("=" * 80)

    macro_cmds = sorted(
        [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] != 0x0c and p["cmd_id"] != 0x8c],
        key=lambda p: float(p["time"])
    )
    print(f"\n  Total other 0x02 commands: {len(macro_cmds)}")
    for p in macro_cmds:
        b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 40), 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)
        print(f"    #{p['frame']} t={p['time']}s [{p['direction']}] 0x02:0x{p['cmd_id']:02x} size={p['data_size']} [{payload_hex}]")

    # Step 8: Profile/Hypershift commands
    print("\n" + "=" * 80)
    print("  STEP 8: PROFILE/HYPERSHIFT COMMANDS (0x0f)")
    print("=" * 80)

    prof_cmds = sorted(
        [p for p in all_parsed if p["cmd_class"] == 0x0f and p["cmd_id"] != 0x03 and p["cmd_id"] != 0x83],
        key=lambda p: float(p["time"])
    )
    print(f"\n  Total 0x0f commands (excl LED): {len(prof_cmds)}")
    for p in prof_cmds:
        b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 40), 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)
        print(f"    #{p['frame']} t={p['time']}s [{p['direction']}] 0x0f:0x{p['cmd_id']:02x} size={p['data_size']} [{payload_hex}]")

    # Step 9: Chronological timeline of non-LED commands
    print("\n" + "=" * 80)
    print("  STEP 9: CHRONOLOGICAL TIMELINE (non-LED OUT)")
    print("=" * 80)

    interesting = sorted(
        [p for p in all_parsed
         if p["direction"] == "OUT"
         and not (p["cmd_class"] == 0x0f and p["cmd_id"] == 0x03)],
        key=lambda p: float(p["time"])
    )

    for p in interesting:
        cls_names = {0x00: "General", 0x02: "Macro/Btn", 0x03: "LED", 0x05: "Mouse",
                    0x07: "CustomFX", 0x09: "DPI", 0x0f: "HyperProf", 0x15: "ExtCfg"}
        cls_name = cls_names.get(p["cmd_class"], f"0x{p['cmd_class']:02x}")
        b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 20), 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)

        marker = ""
        if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c:
            marker = " ** BTN_WRITE **"
        elif p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c:
            marker = " (btn_read)"
        elif p["cmd_class"] == 0x09:
            marker = " (DPI)"

        print(f"  #{p['frame']:>7s} t={p['time']:>14s}s  {cls_name:10s} 0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} "
              f"size={p['data_size']:>2d}  [{payload_hex}]{marker}")


if __name__ == "__main__":
    main()
