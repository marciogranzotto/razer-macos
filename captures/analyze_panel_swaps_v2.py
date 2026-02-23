#!/usr/bin/env python3
"""
Analyze panel swap capture via raw hex extraction.
Bus 4, data_fragment empty — need to parse raw frame bytes.
Swaps: 2-btn -> 6-btn -> 12-btn -> 2-btn
"""
import subprocess
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-pannel-swaps.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

def parse_razer(hex_str):
    """Parse 180 hex chars (90 bytes) as Razer frame."""
    if len(hex_str) < 180:
        return None
    return {
        "status": int(hex_str[0:2], 16), "trans_id": int(hex_str[2:4], 16),
        "remaining": int(hex_str[4:8], 16), "proto_type": int(hex_str[8:10], 16),
        "data_size": int(hex_str[10:12], 16), "cmd_class": int(hex_str[12:14], 16),
        "cmd_id": int(hex_str[14:16], 16), "payload": hex_str[16:176],
        "crc": int(hex_str[176:178], 16), "end": int(hex_str[178:180], 16),
    }

def extract_hex_from_dump(hexdump):
    """Extract raw bytes from tshark -x output."""
    raw = ""
    for hl in hexdump.split("\n"):
        if hl and len(hl) > 6 and hl[4:6] == "  ":
            hex_part = hl[6:53].strip()
            raw += hex_part.replace(" ", "")
    return raw

# Find which device has 98-byte data (Razer SET_REPORT)
for dev in [1, 2, 3]:
    out = run([
        "-Y", f"usb.bus_id==4 && usb.device_address=={dev}",
        "-T", "fields",
        "-e", "usb.data_len", "-e", "usb.endpoint_address",
        "-E", "separator=|"
    ])
    len_counts = Counter()
    for line in out.split("\n"):
        if not line.strip():
            continue
        dl = line.split("|")[0].strip()
        len_counts[dl] += 1
    interesting_lens = {k: v for k, v in len_counts.items() if k in ("90", "98", "8", "16", "64")}
    if interesting_lens:
        print(f"Dev {dev}: {dict(sorted(interesting_lens.items()))}")

# Dev 1 should have the Razer data. Get all frames with data_len=98 or 90
print("\n" + "=" * 80)
print("  EXTRACTING RAZER FRAMES FROM RAW HEX (Dev 1)")
print("=" * 80)

TARGET_DEV = 1

# Get frame list for data_len 98 and 90
out = run([
    "-Y", f"usb.bus_id==4 && usb.device_address=={TARGET_DEV} && usb.endpoint_address==0x00",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.dst",
    "-e", "usb.data_len",
    "-E", "separator=|"
])

frame_list = []
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    dl = parts[4].strip() if len(parts) > 4 else "0"
    if dl in ("98", "90"):
        frame_list.append({
            "frame": parts[0].strip(),
            "time": parts[1].strip(),
            "src": parts[2].strip() if len(parts) > 2 else "",
            "data_len": dl,
        })

print(f"Frames with data_len 98/90: {len(frame_list)}")

# Extract Razer data from raw hex
all_parsed = []
for f in frame_list:
    hexdump = run(["-Y", f"frame.number=={f['frame']}", "-x"])
    raw = extract_hex_from_dump(hexdump)

    direction = "OUT" if "host" in f["src"] else "IN"
    if f["data_len"] == "98":
        razer_hex = raw[70:]  # 35 bytes header * 2
    else:
        razer_hex = raw[54:]  # 27 bytes header * 2

    p = parse_razer(razer_hex)
    if p:
        p["frame"] = f["frame"]
        p["time"] = f["time"]
        p["direction"] = direction
        all_parsed.append(p)

print(f"Parsed Razer frames: {len(all_parsed)}")

# Command distribution
print("\n" + "=" * 80)
print("  COMMAND DISTRIBUTION")
print("=" * 80)
cmd_counts = Counter((p["cmd_class"], p["cmd_id"], p["direction"]) for p in all_parsed)
for (cls, cid, direction), count in sorted(cmd_counts.items()):
    cls_names = {0x00: "General", 0x02: "Macro/Btn", 0x03: "LED", 0x05: "Mouse",
                0x06: "Keypad", 0x07: "CustomFX", 0x09: "DPI", 0x0f: "HyperProf"}
    cls_name = cls_names.get(cls, f"0x{cls:02x}")
    print(f"  {cls_name:12s} 0x{cls:02x}:0x{cid:02x} [{direction}]: {count}")

# ALL non-LED commands chronologically with swap detection
print("\n" + "=" * 80)
print("  ALL NON-LED COMMANDS (chronological)")
print("=" * 80)
interesting = sorted(
    [p for p in all_parsed
     if not (p["cmd_class"] == 0x0f and p["cmd_id"] in (0x03, 0x83))],
    key=lambda p: float(p["time"])
)

prev_time = 0
swap_num = 0
swap_labels = {1: "SWAP 1: 2-btn -> 6-btn",
               2: "SWAP 2: 6-btn -> 12-btn",
               3: "SWAP 3: 12-btn -> 2-btn"}

for p in interesting:
    t = float(p["time"])
    if t - prev_time > 3 and prev_time > 0:
        swap_num += 1
        label = swap_labels.get(swap_num, f"GAP ({t - prev_time:.0f}s)")
        print(f"\n  {'─' * 60}")
        print(f"  ▶ {label}")
        print(f"  {'─' * 60}")
    prev_time = t

    cls_names = {0x00: "General", 0x02: "Macro/Btn", 0x03: "LED", 0x05: "Mouse",
                0x06: "Keypad", 0x07: "CustomFX", 0x09: "DPI", 0x0f: "HyperProf"}
    cls_name = cls_names.get(p["cmd_class"], f"0x{p['cmd_class']:02x}")
    ds = p["data_size"]
    max_bytes = min(ds, 40)
    b = [int(p["payload"][j:j+2], 16) for j in range(0, max_bytes*2, 2)]
    payload_hex = " ".join(f"{x:02x}" for x in b)
    if ds > max_bytes:
        payload_hex += " ..."

    status_names = {0: "NEW", 2: "BUSY", 3: "OK", 4: "FAIL", 5: "TIMEOUT"}
    sn = status_names.get(p["status"], f"0x{p['status']:02x}")

    print(f"  #{p['frame']:>7s} t={t:>10.3f}s [{p['direction']}] {sn:<5s} "
          f"{cls_name:10s} 0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} "
          f"size={ds:>2d}  [{payload_hex}]")

# Detail on 0x00:0xbf
bf_cmds = [p for p in all_parsed if p["cmd_class"] == 0x00 and p["cmd_id"] == 0xbf]
if bf_cmds:
    print(f"\n{'=' * 80}")
    print(f"  DETAIL: 0x00:0xbf COMMANDS ({len(bf_cmds)} total)")
    print(f"{'=' * 80}")
    for p in sorted(bf_cmds, key=lambda x: float(x["time"])):
        ds = p["data_size"]
        full = [int(p["payload"][j:j+2], 16) for j in range(0, min(ds*2, 160), 2)]
        nz = [(i, v) for i, v in enumerate(full) if v != 0]
        print(f"  #{p['frame']:>7s} t={float(p['time']):>10.3f}s [{p['direction']}] "
              f"status=0x{p['status']:02x} size={ds}")
        if nz:
            print(f"    Non-zero: {nz}")
        else:
            print(f"    (all zeros)")
