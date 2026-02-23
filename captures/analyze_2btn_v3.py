#!/usr/bin/env python3
"""
Analyze 2-button capture. Bus 4 Dev 1 has Razer data.
Extract via raw parsing since tshark filters aren't matching data_len==98.
Also look for panel swap commands.
"""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-2btns-change-button-1.pcapng"

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

# Get ALL packets for bus 4 dev 1 with data
out = run([
    "-Y", "usb.bus_id==4 && usb.device_address==1",
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

print(f"Total Razer packets from data_fragment: {len(all_parsed)}")

if len(all_parsed) == 0:
    print("No data_fragment matches. Trying raw hex dump approach...")
    # Get frame numbers for packets with large data
    out2 = run([
        "-Y", "usb.bus_id==4 && usb.device_address==1 && usb.endpoint_address==0x00",
        "-T", "fields",
        "-e", "frame.number", "-e", "frame.time_relative",
        "-e", "usb.src", "-e", "usb.dst",
        "-e", "usb.data_len",
        "-E", "separator=|"
    ])

    frames_98 = []
    for line in out2.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        dl = parts[4].strip() if len(parts) > 4 else "0"
        if dl in ("98", "90"):
            frames_98.append({
                "frame": parts[0].strip(),
                "time": parts[1].strip(),
                "src": parts[2].strip() if len(parts) > 2 else "",
                "dst": parts[3].strip() if len(parts) > 3 else "",
                "data_len": dl,
            })

    print(f"Frames with data_len 98 or 90 on ep 0x00: {len(frames_98)}")

    # Raw hex dump approach: extract Razer payload from raw bytes
    for f in frames_98:
        hexdump = run(["-Y", f"frame.number=={f['frame']}", "-x"])
        raw = ""
        for hl in hexdump.split("\n"):
            if hl and hl[0:4].strip() and not hl.startswith("Frame"):
                hex_part = hl[6:53].strip()
                raw += hex_part.replace(" ", "")

        # USBPcap header: 27 bytes for responses, 27+8=35 for SET_REPORT requests
        direction = "OUT" if "host" in f["src"] else "IN"
        if f["data_len"] == "98":
            # SET_REPORT: 27-byte USBPcap header + 8-byte setup + 90-byte payload
            razer_start = (27 + 8) * 2  # 70 hex chars
        else:
            # GET_REPORT response: 27-byte header + 90-byte payload
            razer_start = 27 * 2  # 54 hex chars

        razer_hex = raw[razer_start:razer_start+180]
        p = parse_razer(razer_hex)
        if p:
            p["frame"] = f["frame"]
            p["time"] = f["time"]
            p["direction"] = direction
            all_parsed.append(p)

    print(f"After raw hex extraction: {len(all_parsed)} Razer packets")

# Command distribution
from collections import Counter
print("\n" + "=" * 80)
print("  COMMAND DISTRIBUTION")
print("=" * 80)
cmd_counts = Counter((p["cmd_class"], p["cmd_id"], p["direction"]) for p in all_parsed)
for (cls, cid, direction), count in sorted(cmd_counts.items()):
    cls_names = {0x00: "General", 0x02: "Macro/Btn", 0x03: "LED", 0x05: "Mouse",
                0x06: "Keypad", 0x07: "CustomFX", 0x09: "DPI", 0x0f: "HyperProf"}
    cls_name = cls_names.get(cls, f"0x{cls:02x}")
    print(f"  {cls_name:12s} 0x{cls:02x}:0x{cid:02x} [{direction}]: {count}")

# ALL non-LED commands
print("\n" + "=" * 80)
print("  ALL NON-LED COMMANDS (chronological)")
print("=" * 80)
interesting = sorted(
    [p for p in all_parsed
     if not (p["cmd_class"] == 0x0f and p["cmd_id"] in (0x03, 0x83))],
    key=lambda p: float(p["time"])
)
for p in interesting:
    cls_names = {0x00: "General", 0x02: "Macro/Btn", 0x03: "LED", 0x05: "Mouse",
                0x06: "Keypad", 0x07: "CustomFX", 0x09: "DPI", 0x0f: "HyperProf"}
    cls_name = cls_names.get(p["cmd_class"], f"0x{p['cmd_class']:02x}")
    ds = p["data_size"]
    b = [int(p["payload"][j:j+2], 16) for j in range(0, min(ds*2, 20), 2)]
    payload_hex = " ".join(f"{x:02x}" for x in b)
    marker = ""
    if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c:
        marker = " ** BTN_WRITE **"
    elif p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c:
        marker = " (btn_read)"
    status_names = {0: "NEW", 2: "BUSY", 3: "OK", 4: "FAIL", 5: "TIMEOUT"}
    sn = status_names.get(p["status"], f"0x{p['status']:02x}")
    print(f"  #{p['frame']:>7s} t={p['time']:>14s}s [{p['direction']}] status={sn:<5s} "
          f"{cls_name:10s} 0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} "
          f"size={ds:>2d}  [{payload_hex}]{marker}")

# Button writes detail
print("\n" + "=" * 80)
print("  BUTTON MAPPING WRITES (0x02:0x0c) — DETAILED")
print("=" * 80)
writes = sorted(
    [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c and p["direction"] == "OUT"],
    key=lambda p: float(p["time"])
)

action_names = {
    0x00: "Disabled", 0x01: "Mouse Button", 0x02: "Keyboard Key",
    0x03: "Macro Play Once", 0x06: "Sensitivity Clutch",
    0x0a: "Multimedia", 0x0c: "Hypershift", 0x12: "Scroll Wheel",
}
key_names = {
    0x04: 'a', 0x05: 'b', 0x1e: '1', 0x1f: '2', 0x20: '3',
    0x2e: '=', 0x28: 'Enter', 0x29: 'Esc',
    0x3a: 'F1', 0x3b: 'F2', 0x3c: 'F3', 0x3d: 'F4',
}
mouse_names = {0x01: "Left", 0x02: "Right", 0x03: "Middle", 0x04: "Back (Btn4)", 0x05: "Forward (Btn5)"}

print(f"\nTotal writes: {len(writes)}")
for i, p in enumerate(writes):
    b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
    payload_hex = " ".join(f"{x:02x}" for x in b)
    action_type = b[3] if len(b) > 3 else 0
    action = action_names.get(action_type, f"Unknown 0x{action_type:02x}")
    detail = ""
    if action_type == 0x02 and len(b) > 6:
        detail = f" -> key '{key_names.get(b[6], f'0x{b[6]:02x}')}'"
    elif action_type == 0x01 and len(b) > 5:
        detail = f" -> {mouse_names.get(b[5], f'btn {b[5]}')}"
    print(f"\n  Write #{i+1}: #{p['frame']} t={p['time']}s")
    print(f"    Raw: [{payload_hex}]")
    print(f"    Profile={b[0]}  Button=0x{b[1]:02x}  Layer={'HS' if b[2] else 'Normal'}")
    print(f"    Action: {action}{detail}")

# Summary
print(f"\n{'=' * 80}")
print(f"  SUMMARY")
print(f"{'=' * 80}")
if writes:
    btn_ids = sorted(set(int(p["payload"][2:4], 16) for p in writes))
    print(f"  2-button panel Button IDs: {', '.join(f'0x{x:02x}' for x in btn_ids)}")
    print(f"  Total writes: {len(writes)}")
    if len(writes) == 4:
        print(f"  4 writes for 4 actions = 'Default' DOES send a write from non-disabled state!")
    elif len(writes) == 2:
        print(f"  2 writes for 4 actions = 'Default' sends NO write even from non-disabled")
