#!/usr/bin/env python3
"""
Analyze capture: razer-naga-12btns-change-button-2.pcapng
Button 1 of 12-btn panel toggled between Disabled and Default.
Goal: Find what command "Default" uses (may not be 0x02:0x0c).
"""
import subprocess
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-2.pcapng"

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
    # Get ALL packets for Bus 2 Dev 3
    out = run([
        "-Y", "usb.bus_id==2 && usb.device_address==3",
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
        parsed["direction"] = "OUT" if "host" in parts[2] else "IN"
        all_parsed.append(parsed)

    print(f"Total Razer packets: {len(all_parsed)}")
    print(f"  OUT: {sum(1 for p in all_parsed if p['direction'] == 'OUT')}")
    print(f"  IN:  {sum(1 for p in all_parsed if p['direction'] == 'IN')}")

    # Step 1: Command distribution (all)
    print("\n" + "=" * 80)
    print("  COMMAND DISTRIBUTION (ALL)")
    print("=" * 80)
    cmd_counts = Counter((p["cmd_class"], p["cmd_id"], p["direction"]) for p in all_parsed)
    for (cls, cid, direction), count in sorted(cmd_counts.items()):
        cls_names = {0x00: "General", 0x02: "Macro/Btn", 0x03: "LED", 0x05: "Mouse",
                    0x06: "Keypad", 0x07: "CustomFX", 0x09: "DPI", 0x0f: "HyperProf", 0x15: "ExtCfg"}
        cls_name = cls_names.get(cls, f"0x{cls:02x}")
        print(f"  {cls_name:12s} 0x{cls:02x}:0x{cid:02x} [{direction}]: {count}")

    # Step 2: ALL non-LED OUT commands chronologically
    print("\n" + "=" * 80)
    print("  ALL NON-LED OUT COMMANDS (chronological)")
    print("=" * 80)
    interesting_out = sorted(
        [p for p in all_parsed
         if p["direction"] == "OUT"
         and not (p["cmd_class"] == 0x0f and p["cmd_id"] == 0x03)],
        key=lambda p: float(p["time"])
    )
    for p in interesting_out:
        cls_names = {0x00: "General", 0x02: "Macro/Btn", 0x03: "LED", 0x05: "Mouse",
                    0x06: "Keypad", 0x07: "CustomFX", 0x09: "DPI", 0x0f: "HyperProf", 0x15: "ExtCfg"}
        cls_name = cls_names.get(p["cmd_class"], f"0x{p['cmd_class']:02x}")
        b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 20), 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)
        marker = ""
        if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c:
            marker = " ** BTN_WRITE **"
        elif p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c:
            marker = " (btn_read)"
        print(f"  #{p['frame']:>7s} t={p['time']:>14s}s  {cls_name:10s} 0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} "
              f"size={p['data_size']:>2d}  [{payload_hex}]{marker}")

    # Step 3: ALL non-LED IN responses chronologically
    print("\n" + "=" * 80)
    print("  ALL NON-LED IN RESPONSES (chronological)")
    print("=" * 80)
    interesting_in = sorted(
        [p for p in all_parsed
         if p["direction"] == "IN"
         and not (p["cmd_class"] == 0x0f and p["cmd_id"] == 0x03)
         and not (p["cmd_class"] == 0x0f and p["cmd_id"] == 0x83)],
        key=lambda p: float(p["time"])
    )
    for p in interesting_in:
        cls_names = {0x00: "General", 0x02: "Macro/Btn", 0x03: "LED", 0x05: "Mouse",
                    0x06: "Keypad", 0x07: "CustomFX", 0x09: "DPI", 0x0f: "HyperProf", 0x15: "ExtCfg"}
        cls_name = cls_names.get(p["cmd_class"], f"0x{p['cmd_class']:02x}")
        b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 20), 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)
        status_names = {0: "NEW", 2: "BUSY", 3: "OK", 4: "FAIL", 5: "TIMEOUT"}
        status = status_names.get(p["status"], f"0x{p['status']:02x}")
        print(f"  #{p['frame']:>7s} t={p['time']:>14s}s  {cls_name:10s} 0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} "
              f"status={status:<7s} size={p['data_size']:>2d}  [{payload_hex}]")

    # Step 4: Button mapping writes specifically
    print("\n" + "=" * 80)
    print("  BUTTON MAPPING WRITES (0x02:0x0c)")
    print("=" * 80)
    writes = sorted(
        [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c and p["direction"] == "OUT"],
        key=lambda p: float(p["time"])
    )
    print(f"\n  Total writes: {len(writes)}")
    for i, p in enumerate(writes):
        b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)
        print(f"\n  Write #{i+1}: #{p['frame']} t={p['time']}s")
        print(f"    Raw: [{payload_hex}]")
        print(f"    Profile={b[0]}  Button=0x{b[1]:02x}  Layer={'HS' if b[2] else 'Normal'}")
        print(f"    Action type = 0x{b[3]:02x}")
        for j in range(3, min(len(b), 10)):
            print(f"      Byte[{j}] = 0x{b[j]:02x} ({b[j]:3d})")

    # Step 5: Look for ANY command that references 0x40 (expected button 1 of 12-panel)
    print("\n" + "=" * 80)
    print("  PACKETS REFERENCING BUTTON 0x40 (expected btn 1 of 12-panel)")
    print("=" * 80)
    for p in sorted(all_parsed, key=lambda x: float(x["time"])):
        if p["data_size"] < 2:
            continue
        btn_id = int(p["payload"][2:4], 16)
        if btn_id == 0x40:
            b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 20), 2)]
            payload_hex = " ".join(f"{x:02x}" for x in b)
            status_names = {0: "NEW", 2: "BUSY", 3: "OK", 4: "FAIL", 5: "TIMEOUT"}
            status = status_names.get(p["status"], f"0x{p['status']:02x}")
            print(f"  #{p['frame']:>7s} t={p['time']:>14s}s [{p['direction']}] "
                  f"0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} status={status:<7s} "
                  f"size={p['data_size']:>2d}  [{payload_hex}]")

    # Step 6: Also check for commands with button bytes in range 0x40-0x4b
    print("\n" + "=" * 80)
    print("  ALL BUTTON MAPPING (0x02:0x0c or 0x02:0x8c) WITH BUTTON IN 0x40-0x4b RANGE")
    print("=" * 80)
    for p in sorted(all_parsed, key=lambda x: float(x["time"])):
        if p["cmd_class"] != 0x02:
            continue
        if p["cmd_id"] not in (0x0c, 0x8c):
            continue
        if p["data_size"] < 2:
            continue
        btn_id = int(p["payload"][2:4], 16)
        if 0x40 <= btn_id <= 0x4b:
            b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 20), 2)]
            payload_hex = " ".join(f"{x:02x}" for x in b)
            status_names = {0: "NEW", 2: "BUSY", 3: "OK", 4: "FAIL", 5: "TIMEOUT"}
            status = status_names.get(p["status"], f"0x{p['status']:02x}")
            cmd_type = "WRITE" if p["cmd_id"] == 0x0c else "READ"
            print(f"  #{p['frame']:>7s} t={p['time']:>14s}s [{p['direction']}] {cmd_type} "
                  f"status={status:<7s} [{payload_hex}]")

if __name__ == "__main__":
    main()
