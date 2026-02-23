#!/usr/bin/env python3
"""
Check USB addresses 2.1.1, 2.3.1, and 2.3.3 for the Default command.
These may be different interfaces of the Razer dongle.
"""
import subprocess
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-3.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

def parse_razer(hex_data):
    d = hex_data.replace(":", "")
    if len(d) < 180:
        return None
    return {
        "status": int(d[0:2], 16),
        "data_size": int(d[10:12], 16), "cmd_class": int(d[12:14], 16),
        "cmd_id": int(d[14:16], 16), "payload": d[16:176],
    }

# First: what USB addresses exist in this capture?
print("=" * 80)
print("  ALL USB ADDRESSES IN CAPTURE")
print("=" * 80)

out = run([
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.dst",
    "-e", "usb.data_len", "-e", "usb.data_fragment",
    "-E", "separator=|"
])

addr_counter = Counter()
addr_with_data = Counter()
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    src = parts[2].strip() if len(parts) > 2 else ""
    dst = parts[3].strip() if len(parts) > 3 else ""
    data_frag = parts[5].strip() if len(parts) > 5 else ""
    for addr in [src, dst]:
        if addr and addr != "host":
            addr_counter[addr] += 1
            if data_frag:
                addr_with_data[addr] += 1

print("Address usage (src or dst):")
for addr, count in sorted(addr_counter.items()):
    data_count = addr_with_data.get(addr, 0)
    print(f"  {addr:>10s}: {count:>6d} packets ({data_count} with data_fragment)")

# Now examine each target address
for target_addr in ["2.1.1", "2.3.1", "2.3.3"]:
    print(f"\n{'=' * 80}")
    print(f"  DEVICE {target_addr}")
    print(f"{'=' * 80}")

    # Get all packets to/from this address
    out2 = run([
        "-Y", f"usb.src=='{target_addr}' || usb.dst=='{target_addr}'",
        "-T", "fields",
        "-e", "frame.number", "-e", "frame.time_relative",
        "-e", "usb.src", "-e", "usb.dst",
        "-e", "usb.data_len", "-e", "usb.data_fragment",
        "-e", "usb.endpoint_address",
        "-E", "separator=|"
    ])

    lines = [l for l in out2.split("\n") if l.strip()]
    print(f"  Total packets: {len(lines)}")

    if not lines:
        # Try without quotes
        out2 = run([
            "-Y", f"usb.src=={target_addr} || usb.dst=={target_addr}",
            "-T", "fields",
            "-e", "frame.number", "-e", "frame.time_relative",
            "-e", "usb.src", "-e", "usb.dst",
            "-e", "usb.data_len", "-e", "usb.data_fragment",
            "-e", "usb.endpoint_address",
            "-E", "separator=|"
        ])
        lines = [l for l in out2.split("\n") if l.strip()]
        print(f"  Total packets (retry): {len(lines)}")

    # Show data_len distribution
    len_counts = Counter()
    all_entries = []
    for line in lines:
        parts = line.split("|")
        frame = parts[0].strip() if len(parts) > 0 else ""
        time = parts[1].strip() if len(parts) > 1 else ""
        src = parts[2].strip() if len(parts) > 2 else ""
        dst = parts[3].strip() if len(parts) > 3 else ""
        data_len = parts[4].strip() if len(parts) > 4 else ""
        data_frag = parts[5].strip() if len(parts) > 5 else ""
        endpoint = parts[6].strip() if len(parts) > 6 else ""
        len_counts[data_len] += 1

        direction = "OUT" if "host" in src else "IN"
        all_entries.append({
            "frame": frame, "time": time, "direction": direction,
            "data_len": data_len, "data_frag": data_frag, "endpoint": endpoint,
        })

    print(f"  Data length distribution:")
    for dl, count in sorted(len_counts.items(), key=lambda x: -x[1]):
        print(f"    data_len={dl:>3s}: {count}")

    # Show non-LED packets with data
    print(f"\n  Non-LED packets with data:")
    shown = 0
    for e in sorted(all_entries, key=lambda x: float(x["time"]) if x["time"] else 0):
        d = e["data_frag"].replace(":", "")
        if not d:
            continue
        # Try to parse as Razer
        p = parse_razer(e["data_frag"])
        if p:
            if p["cmd_class"] == 0x0f and p["cmd_id"] == 0x03:
                continue  # skip LED
            ds = p["data_size"]
            b = [int(p["payload"][j:j+2], 16) for j in range(0, min(ds*2, 20), 2)]
            ph = " ".join(f"{x:02x}" for x in b)
            print(f"    #{e['frame']:>7s} t={e['time']:>14s}s [{e['direction']}] ep={e['endpoint']} "
                  f"RAZER 0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} size={ds} [{ph}]")
            shown += 1
        else:
            # Raw data
            print(f"    #{e['frame']:>7s} t={e['time']:>14s}s [{e['direction']}] ep={e['endpoint']} "
                  f"len={e['data_len']} RAW({len(d)//2}B): {d[:80]}")
            shown += 1

        if shown > 50:
            print(f"    ... (truncated)")
            break

    if shown == 0:
        print(f"    (none)")
