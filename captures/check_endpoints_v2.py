#!/usr/bin/env python3
"""
Extract data from all endpoints using endpoint_address and device_address filters.
Razer dongle (dev 3) interfaces:
  0x00 = control (Razer protocol)
  0x81 = endpoint 1 IN (mouse HID) -> addr 2.3.1
  0x82 = endpoint 2 IN (keyboard HID) -> addr 2.3.2
  0x83 = endpoint 3 IN (keyboard HID) -> addr 2.3.3
Also check dev 1 endpoint 1 -> addr 2.1.1
"""
import subprocess
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-3.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

# Known disabled write times: t=17.8, 26.0, 34.8
# Default actions should be around t=21, t=30, t=38 (roughly)

targets = [
    (3, 0x81, "2.3.1 - Mouse HID (ep1)"),
    (3, 0x82, "2.3.2 - Keyboard HID (ep2)"),
    (3, 0x83, "2.3.3 - Keyboard HID (ep3)"),
    (1, 0x81, "2.1.1 - Dev1 ep1"),
    (1, 0x82, "2.1.2 - Dev1 ep2"),
]

for dev_addr, ep_addr, label in targets:
    print(f"\n{'=' * 80}")
    print(f"  {label}  (dev={dev_addr}, ep=0x{ep_addr:02x})")
    print(f"{'=' * 80}")

    # Filter by device and endpoint
    filt = f"usb.device_address=={dev_addr} && usb.endpoint_address==0x{ep_addr:02x}"
    out = run([
        "-Y", filt,
        "-T", "fields",
        "-e", "frame.number", "-e", "frame.time_relative",
        "-e", "usb.src", "-e", "usb.dst",
        "-e", "usb.data_len",
        "-E", "separator=|"
    ])

    lines = [l for l in out.split("\n") if l.strip()]
    print(f"  Total packets: {len(lines)}")

    if not lines:
        continue

    # data_len distribution
    len_counts = Counter()
    for line in lines:
        parts = line.split("|")
        dl = parts[4].strip() if len(parts) > 4 else "?"
        len_counts[dl] += 1
    print(f"  Data lengths: {dict(len_counts)}")

    # Raw hex dump of first few with data, and specifically ones in the "Default" time windows
    frames_with_data = []
    for line in lines:
        parts = line.split("|")
        dl = parts[4].strip() if len(parts) > 4 else "0"
        if int(dl) > 0:
            t = float(parts[1].strip()) if len(parts) > 1 and parts[1].strip() else 0
            frames_with_data.append((t, parts[0].strip(), dl))

    print(f"  Packets with data: {len(frames_with_data)}")

    # Show timestamps of all data packets to see timing correlation
    if len(frames_with_data) <= 40:
        print(f"\n  ALL data packets:")
        for t, fnum, dl in frames_with_data:
            # Mark if in a "Default" time window
            marker = ""
            if 19 < t < 25:
                marker = " <<< Default #1 window"
            elif 27 < t < 34:
                marker = " <<< Default #2 window"
            elif 35 < t < 42:
                marker = " <<< Default #3 window"
            print(f"    #{fnum:>7s} t={t:>10.3f}s len={dl}{marker}")
    else:
        # Show subset: ones in the Default windows
        print(f"\n  Data packets in Default time windows:")
        for t, fnum, dl in frames_with_data:
            if (19 < t < 25) or (27 < t < 34) or (35 < t < 42):
                print(f"    #{fnum:>7s} t={t:>10.3f}s len={dl}")

    # Raw hex dump of a few interesting ones
    sample_frames = []
    for t, fnum, dl in frames_with_data:
        if (19 < t < 25) or (27 < t < 34) or (35 < t < 42):
            sample_frames.append((t, fnum))
        if len(sample_frames) >= 6:
            break

    # Also grab first packet for identification
    if frames_with_data and not sample_frames:
        sample_frames = [(frames_with_data[0][0], frames_with_data[0][1])]

    if sample_frames:
        print(f"\n  Raw hex dumps of interesting frames:")
        for t, fnum in sample_frames[:6]:
            print(f"\n    --- Frame #{fnum} (t={t:.3f}s) ---")
            hexdump = run(["-Y", f"frame.number=={fnum}", "-x"])
            for hl in hexdump.split("\n"):
                print(f"    {hl}")
