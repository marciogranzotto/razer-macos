#!/usr/bin/env python3
"""Check which endpoint has the 98-byte data in panel swap capture."""
import subprocess
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-pannel-swaps.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

# Check all endpoints and data lens for dev 1
out = run([
    "-Y", "usb.bus_id==4 && usb.device_address==1",
    "-T", "fields",
    "-e", "usb.endpoint_address", "-e", "usb.data_len",
    "-E", "separator=|"
])

ep_dl = Counter()
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    ep = parts[0].strip() if len(parts) > 0 else "?"
    dl = parts[1].strip() if len(parts) > 1 else "?"
    ep_dl[(ep, dl)] += 1

print("Dev 1 - Endpoint x DataLen:")
for (ep, dl), count in sorted(ep_dl.items()):
    if dl in ("0", ""):
        continue
    print(f"  ep={ep:>6s} data_len={dl:>4s}: {count}")

# Get verbose decode of a 98-byte frame (whatever endpoint)
out2 = run([
    "-Y", "usb.bus_id==4 && usb.device_address==1 && usb.data_len==98",
    "-T", "fields", "-c", "1",
    "-e", "frame.number", "-e", "usb.endpoint_address",
    "-E", "separator=|"
])
if out2.strip():
    fnum = out2.split("|")[0].strip()
    ep = out2.split("|")[1].strip() if "|" in out2 else "?"
    print(f"\nFirst 98-byte frame: #{fnum} on endpoint {ep}")

    hexdump = run(["-Y", f"frame.number=={fnum}", "-x"])
    print(f"\nRaw hex:")
    for hl in hexdump.split("\n"):
        print(f"  {hl}")

    verbose = run(["-Y", f"frame.number=={fnum}", "-c", "1", "-V"])
    print(f"\nVerbose (key lines):")
    for line in verbose.split("\n"):
        ls = line.strip()
        if any(kw in ls.lower() for kw in ["header size", "data", "setup",
                "brequest", "wvalue", "fragment", "hid", "endpoint",
                "function", "irp", "transfer", "direction"]):
            print(f"  {ls}")

# Also check USB addresses in this capture
print("\n\nUSB addresses:")
out3 = run([
    "-T", "fields",
    "-e", "usb.src", "-e", "usb.dst",
    "-E", "separator=|"
])
addrs = Counter()
for line in out3.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    for p in parts:
        p = p.strip()
        if p and p != "host":
            addrs[p] += 1
for addr, count in sorted(addrs.items()):
    print(f"  {addr}: {count}")
