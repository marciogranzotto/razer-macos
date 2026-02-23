#!/usr/bin/env python3
"""
Panel swap analysis - get ALL frames for dev 1 ep 0x00, filter by size in Python.
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
    if len(hex_str) < 180:
        return None
    return {
        "status": int(hex_str[0:2], 16), "trans_id": int(hex_str[2:4], 16),
        "remaining": int(hex_str[4:8], 16), "proto_type": int(hex_str[8:10], 16),
        "data_size": int(hex_str[10:12], 16), "cmd_class": int(hex_str[12:14], 16),
        "cmd_id": int(hex_str[14:16], 16), "payload": hex_str[16:176],
        "crc": int(hex_str[176:178], 16), "end": int(hex_str[178:180], 16),
    }

# Get ALL packets for dev 1 - no data_len filter
out = run([
    "-Y", "usb.bus_id==4 && usb.device_address==1",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.dst",
    "-e", "usb.data_len", "-e", "usb.data_fragment",
    "-E", "separator=|"
])

all_parsed = []
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    if len(parts) < 6:
        continue
    data_len = parts[4].strip()
    data_frag = parts[5].strip() if len(parts) > 5 else ""
    d = data_frag.replace(":", "")

    # Only process 98-byte packets (Razer SET_REPORT with 8-byte setup)
    if len(d) < 180:
        continue

    # For SET_REPORT (98 bytes), data_fragment should contain just the 90-byte payload
    # But with USBPcap it sometimes includes the setup bytes
    # Try parsing from start
    p = parse_razer(d[:180])
    if not p:
        continue

    # Validate: end marker should be 0x00
    if p["end"] != 0x00:
        # Try with 16-char offset (8 setup bytes)
        if len(d) >= 196:
            p = parse_razer(d[16:196])
            if not p or p["end"] != 0x00:
                continue

    p["frame"] = parts[0].strip()
    p["time"] = parts[1].strip()
    p["direction"] = "OUT" if "host" in parts[2] else "IN"
    p["raw_len"] = len(d) // 2
    all_parsed.append(p)

print(f"Total Razer packets: {len(all_parsed)}")

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

# ALL non-0x0b commands (0x0b:0x0f seems to be the LED equivalent here)
print("\n" + "=" * 80)
print("  ALL NON-LED COMMANDS (excluding 0x0b:0x0f)")
print("=" * 80)
interesting = sorted(
    [p for p in all_parsed if not (p["cmd_class"] == 0x0b and p["cmd_id"] == 0x0f)],
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
        print(f"  ▶ {label} (gap={t - prev_time:.1f}s)")
        print(f"  {'─' * 60}")
    prev_time = t

    ds = p["data_size"]
    max_bytes = min(ds, 40)
    b = [int(p["payload"][j:j+2], 16) for j in range(0, max_bytes*2, 2)]
    payload_hex = " ".join(f"{x:02x}" for x in b)
    if ds > max_bytes:
        payload_hex += " ..."

    status_names = {0: "NEW", 2: "BUSY", 3: "OK", 4: "FAIL", 5: "TIMEOUT"}
    sn = status_names.get(p["status"], f"0x{p['status']:02x}")

    print(f"  #{p['frame']:>7s} t={t:>10.3f}s [{p['direction']}] {sn:<5s} "
          f"0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} "
          f"size={ds:>2d}  [{payload_hex}]")

# Check the 0x01:0x00 commands - these might be panel-related
print(f"\n{'=' * 80}")
print(f"  0x01:0x00 COMMANDS (potential panel detection)")
print(f"{'=' * 80}")
cmds_01 = [p for p in all_parsed if p["cmd_class"] == 0x01 and p["cmd_id"] == 0x00]
for p in sorted(cmds_01, key=lambda x: float(x["time"])):
    ds = p["data_size"]
    full = [int(p["payload"][j:j+2], 16) for j in range(0, min(ds*2, 20), 2)]
    ph = " ".join(f"{x:02x}" for x in full) if full else "(empty)"
    print(f"  #{p['frame']:>7s} t={float(p['time']):>10.3f}s [{p['direction']}] "
          f"status=0x{p['status']:02x} size={ds} [{ph}]")

# Check the 0x02:0x07 commands
print(f"\n{'=' * 80}")
print(f"  0x02:0x07 COMMANDS")
print(f"{'=' * 80}")
cmds_02_07 = [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x07]
for p in sorted(cmds_02_07, key=lambda x: float(x["time"])):
    ds = p["data_size"]
    full = [int(p["payload"][j:j+2], 16) for j in range(0, min(ds*2, 20), 2)]
    ph = " ".join(f"{x:02x}" for x in full) if full else "(empty)"
    print(f"  #{p['frame']:>7s} t={float(p['time']):>10.3f}s [{p['direction']}] "
          f"status=0x{p['status']:02x} size={ds} [{ph}]")

# Also check responses (90-byte frames on ep 0x80)
print(f"\n{'=' * 80}")
print(f"  CHECKING RESPONSES (ep 0x80)")
print(f"{'=' * 80}")
# These won't be in data_fragment. Try raw hex approach for a few.
out2 = run([
    "-Y", "usb.bus_id==4 && usb.device_address==1 && usb.endpoint_address==0x80 && usb.data_len==90",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-E", "separator=|"
])
resp_frames = []
for line in out2.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    resp_frames.append(parts[0].strip())

# Hmm, this filter might not work either. Use the frame list approach
print(f"  Response frames found by filter: {len(resp_frames)}")

# Try getting ALL ep 0x80 frames
out3 = run([
    "-Y", "usb.bus_id==4 && usb.device_address==1",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.endpoint_address", "-e", "usb.data_len",
    "-E", "separator=|"
])
for line in out3.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    ep = parts[3].strip() if len(parts) > 3 else ""
    dl = parts[4].strip() if len(parts) > 4 else "0"
    if ep == "0x80" and dl == "90":
        print(f"  Response: #{parts[0].strip()} t={parts[1].strip()}s")
