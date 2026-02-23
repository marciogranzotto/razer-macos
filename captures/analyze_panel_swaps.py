#!/usr/bin/env python3
"""
Analyze panel swap capture: razer-naga-pannel-swaps.pcapng
Swaps: 2-btn -> 6-btn -> 12-btn -> 2-btn
Goal: Find panel detection/swap commands.
"""
import subprocess
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-pannel-swaps.pcapng"

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

# Discover devices
print("=" * 80)
print("  DEVICE DISCOVERY")
print("=" * 80)
out = run([
    "-T", "fields",
    "-e", "usb.bus_id", "-e", "usb.device_address",
    "-E", "separator=|"
])
addr_counter = Counter()
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    bus = parts[0].strip() if len(parts) > 0 else ""
    dev = parts[1].strip() if len(parts) > 1 else ""
    if bus and dev:
        addr_counter[(bus, dev)] += 1
for (bus, dev), count in sorted(addr_counter.items()):
    print(f"  Bus {bus} Dev {dev}: {count} packets")

# Try each device for Razer data
TARGET_BUS = None
TARGET_DEV = None
for (bus, dev), count in sorted(addr_counter.items()):
    out_test = run([
        "-Y", f"usb.bus_id=={bus} && usb.device_address=={dev}",
        "-T", "fields", "-c", "10",
        "-e", "usb.data_fragment",
        "-E", "separator=|"
    ])
    razer_count = 0
    for line in out_test.split("\n"):
        d = line.strip().replace(":", "")
        if len(d) >= 180:
            razer_count += 1
    if razer_count > 0:
        print(f"  -> Razer device at Bus {bus} Dev {dev}")
        TARGET_BUS = bus
        TARGET_DEV = dev
        break

if not TARGET_BUS:
    print("No Razer data_fragment found. Exiting.")
    exit(1)

# Get ALL Razer packets
out = run([
    "-Y", f"usb.bus_id=={TARGET_BUS} && usb.device_address=={TARGET_DEV}",
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

print(f"\nTotal Razer packets: {len(all_parsed)}")

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

# ALL non-LED commands with FULL payload
print("\n" + "=" * 80)
print("  ALL NON-LED COMMANDS (chronological, full payload)")
print("=" * 80)
interesting = sorted(
    [p for p in all_parsed
     if not (p["cmd_class"] == 0x0f and p["cmd_id"] in (0x03, 0x83))],
    key=lambda p: float(p["time"])
)

# Group by time gaps to identify swap events
prev_time = 0
swap_num = 0
swap_labels = {1: "=== SWAP 1: 2-btn -> 6-btn ===",
               2: "=== SWAP 2: 6-btn -> 12-btn ===",
               3: "=== SWAP 3: 12-btn -> 2-btn ==="}

for p in interesting:
    t = float(p["time"])
    if t - prev_time > 5 and prev_time > 0:
        swap_num += 1
        label = swap_labels.get(swap_num, f"=== GAP ({t - prev_time:.0f}s) ===")
        print(f"\n  {'=' * 60}")
        print(f"  {label}")
        print(f"  {'=' * 60}")
    prev_time = t

    cls_names = {0x00: "General", 0x02: "Macro/Btn", 0x03: "LED", 0x05: "Mouse",
                0x06: "Keypad", 0x07: "CustomFX", 0x09: "DPI", 0x0f: "HyperProf"}
    cls_name = cls_names.get(p["cmd_class"], f"0x{p['cmd_class']:02x}")
    ds = p["data_size"]
    # Show more payload bytes for these commands
    max_bytes = min(ds, 40)
    b = [int(p["payload"][j:j+2], 16) for j in range(0, max_bytes*2, 2)]
    payload_hex = " ".join(f"{x:02x}" for x in b)
    if ds > max_bytes:
        payload_hex += " ..."

    status_names = {0: "NEW", 2: "BUSY", 3: "OK", 4: "FAIL", 5: "TIMEOUT"}
    sn = status_names.get(p["status"], f"0x{p['status']:02x}")

    marker = ""
    if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c:
        marker = " ** BTN_WRITE **"
    elif p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c:
        marker = " (btn_read)"
    elif p["cmd_class"] == 0x00 and p["cmd_id"] == 0xbf:
        marker = " ** UNKNOWN 0xBF **"

    print(f"  #{p['frame']:>7s} t={t:>10.3f}s [{p['direction']}] status={sn:<5s} "
          f"{cls_name:10s} 0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} "
          f"size={ds:>2d}  [{payload_hex}]{marker}")

# Specifically look at 0x00:0xbf commands
print("\n" + "=" * 80)
print("  DETAIL: 0x00:0xbf COMMANDS")
print("=" * 80)
bf_cmds = [p for p in all_parsed if p["cmd_class"] == 0x00 and p["cmd_id"] == 0xbf]
for p in sorted(bf_cmds, key=lambda x: float(x["time"])):
    ds = p["data_size"]
    full_payload = [int(p["payload"][j:j+2], 16) for j in range(0, min(ds*2, 160), 2)]
    payload_hex = " ".join(f"{x:02x}" for x in full_payload)
    non_zero = [(i, v) for i, v in enumerate(full_payload) if v != 0]
    print(f"  #{p['frame']:>7s} t={float(p['time']):>10.3f}s [{p['direction']}] "
          f"status=0x{p['status']:02x} size={ds}")
    print(f"    Full: [{payload_hex}]")
    if non_zero:
        print(f"    Non-zero bytes: {non_zero}")
    else:
        print(f"    (all zeros)")

# Also check for any button reads (0x02:0x8c) — Synapse may re-read bindings after swap
print("\n" + "=" * 80)
print("  BUTTON READS (0x02:0x8c)")
print("=" * 80)
reads = [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c]
print(f"  Total button reads: {len(reads)}")
if reads:
    for p in sorted(reads, key=lambda x: float(x["time"]))[:20]:
        ds = p["data_size"]
        b = [int(p["payload"][j:j+2], 16) for j in range(0, min(ds*2, 20), 2)]
        payload_hex = " ".join(f"{x:02x}" for x in b)
        print(f"    #{p['frame']:>7s} t={float(p['time']):>10.3f}s [{p['direction']}] [{payload_hex}]")
    if len(reads) > 20:
        print(f"    ... ({len(reads) - 20} more)")
