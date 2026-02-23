#!/usr/bin/env python3
"""
Analyze 2-button capture. Bus 4, Devs 1/2/3.
Try all data fields since data_fragment may not work.
"""
import subprocess
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-2btns-change-button-1.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

# Check data_len distribution per device
for dev in [1, 2, 3]:
    out = run([
        "-Y", f"usb.bus_id==4 && usb.device_address=={dev}",
        "-T", "fields",
        "-e", "usb.data_len", "-e", "usb.endpoint_address",
        "-E", "separator=|"
    ])
    len_counts = Counter()
    ep_counts = Counter()
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        dl = parts[0].strip() if len(parts) > 0 else ""
        ep = parts[1].strip() if len(parts) > 1 else ""
        len_counts[dl] += 1
        ep_counts[ep] += 1
    print(f"Dev {dev}: data_lens={dict(sorted(len_counts.items()))} endpoints={dict(sorted(ep_counts.items()))}")

# Raw hex dump of first few packets with data_len=98 or data_len=90
print("\n" + "=" * 80)
print("  LOOKING FOR RAZER FRAMES (data_len=98 or 90)")
print("=" * 80)

for dev in [1, 2]:
    for target_len in [98, 90]:
        out = run([
            "-Y", f"usb.bus_id==4 && usb.device_address=={dev} && usb.data_len=={target_len}",
            "-T", "fields", "-c", "3",
            "-e", "frame.number", "-e", "frame.time_relative",
            "-e", "usb.src",
            "-E", "separator=|"
        ])
        frames = [l for l in out.split("\n") if l.strip()]
        if frames:
            print(f"\n  Dev {dev}, data_len={target_len}: {len(frames)} frames found")
            for line in frames[:3]:
                fnum = line.split("|")[0].strip()
                hexdump = run(["-Y", f"frame.number=={fnum}", "-x"])
                print(f"\n    Frame #{fnum}:")
                for hl in hexdump.split("\n"):
                    print(f"      {hl}")

# Also check using usb.capdata instead of data_fragment
print("\n" + "=" * 80)
print("  TRYING usb.capdata FIELD")
print("=" * 80)

for dev in [1, 2]:
    out = run([
        "-Y", f"usb.bus_id==4 && usb.device_address=={dev} && usb.data_len==98",
        "-T", "fields", "-c", "5",
        "-e", "frame.number", "-e", "frame.time_relative",
        "-e", "usb.capdata", "-e", "usb.data_fragment",
        "-e", "usb.control.data", "-e", "usbhid.data",
        "-E", "separator=|"
    ])
    if out.strip():
        print(f"\n  Dev {dev}:")
        for line in out.split("\n"):
            if line.strip():
                print(f"    {line}")

# Try verbose decode of a single 98-byte frame
print("\n" + "=" * 80)
print("  VERBOSE DECODE OF FIRST 98-BYTE FRAME")
print("=" * 80)

for dev in [1, 2]:
    out = run([
        "-Y", f"usb.bus_id==4 && usb.device_address=={dev} && usb.data_len==98",
        "-c", "1", "-V"
    ])
    if out.strip():
        print(f"\n  Dev {dev}:")
        for line in out.split("\n"):
            ls = line.strip()
            if any(kw in ls.lower() for kw in [
                "data fragment", "capdata", "control data", "hid",
                "setup data", "brequest", "bmrequest", "wvalue",
                "windex", "wlength", "report", "descriptor",
                "razer", "vendor", "idvendor", "idproduct",
                "endpoint", "interface"
            ]):
                print(f"      {ls}")
