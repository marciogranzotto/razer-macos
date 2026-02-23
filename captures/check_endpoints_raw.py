#!/usr/bin/env python3
"""
Extract actual data from endpoints 2.3.1, 2.3.2, 2.3.3 and 2.1.1
using usb.capdata, HID data, and raw hex dumps since data_fragment is empty.
"""
import subprocess
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-3.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

# First: check ALL addresses again including 2.3.2
print("=" * 80)
print("  ALL USB ADDRESSES")
print("=" * 80)
out = run([
    "-T", "fields",
    "-e", "usb.src", "-e", "usb.dst",
    "-E", "separator=|"
])
addrs = Counter()
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    for p in parts:
        p = p.strip()
        if p and p != "host":
            addrs[p] += 1
for addr, count in sorted(addrs.items()):
    print(f"  {addr}: {count}")

# Now for each target, try multiple data extraction methods
for target in ["2.3.1", "2.3.2", "2.3.3", "2.1.1"]:
    print(f"\n{'=' * 80}")
    print(f"  ENDPOINT {target}")
    print(f"{'=' * 80}")

    # Try all possible data fields
    out2 = run([
        "-Y", f"usb.src=={target} || usb.dst=={target}",
        "-T", "fields",
        "-e", "frame.number", "-e", "frame.time_relative",
        "-e", "usb.src", "-e", "usb.dst",
        "-e", "usb.data_len",
        "-e", "usb.capdata",
        "-e", "usb.data_fragment",
        "-e", "usbhid.data",
        "-e", "usb.interrupt.data",
        "-E", "separator=|"
    ])

    lines = [l for l in out2.split("\n") if l.strip()]
    print(f"  Total packets: {len(lines)}")

    # Show first 30 non-empty-data packets
    shown = 0
    for line in lines:
        parts = line.split("|")
        frame = parts[0].strip() if len(parts) > 0 else ""
        time = parts[1].strip() if len(parts) > 1 else ""
        src = parts[2].strip() if len(parts) > 2 else ""
        dst = parts[3].strip() if len(parts) > 3 else ""
        data_len = parts[4].strip() if len(parts) > 4 else ""
        capdata = parts[5].strip() if len(parts) > 5 else ""
        data_frag = parts[6].strip() if len(parts) > 6 else ""
        hid_data = parts[7].strip() if len(parts) > 7 else ""
        intr_data = parts[8].strip() if len(parts) > 8 else ""

        direction = "OUT" if "host" in src else "IN"

        # Skip zero-length
        if data_len == "0":
            continue

        data_display = ""
        if capdata:
            data_display = f"capdata={capdata[:80]}"
        elif data_frag:
            data_display = f"frag={data_frag[:80]}"
        elif hid_data:
            data_display = f"hid={hid_data[:80]}"
        elif intr_data:
            data_display = f"intr={intr_data[:80]}"
        else:
            data_display = "(no field matched)"

        print(f"    #{frame:>7s} t={time:>14s}s [{direction}] len={data_len:>3s} {data_display}")
        shown += 1
        if shown >= 30:
            remaining = sum(1 for l in lines if l.strip()) - shown
            print(f"    ... ({remaining} more)")
            break

    if shown == 0:
        # Try raw hex dump of first few packets with data
        print(f"  No data in standard fields. Trying raw hex dump...")
        out3 = run([
            "-Y", f"(usb.src=={target} || usb.dst=={target}) && usb.data_len>0",
            "-T", "fields", "-c", "3",
            "-e", "frame.number",
            "-E", "separator=|"
        ])
        for line in out3.split("\n"):
            if not line.strip():
                continue
            fnum = line.split("|")[0].strip()
            print(f"\n    Raw hex of frame #{fnum}:")
            hexdump = run(["-Y", f"frame.number=={fnum}", "-x"])
            for hl in hexdump.split("\n"):
                print(f"      {hl}")
