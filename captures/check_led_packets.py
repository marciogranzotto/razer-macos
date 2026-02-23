#!/usr/bin/env python3
"""
Check every single 98-byte packet in the time gaps.
Maybe one of them ISN'T LED data — maybe the Default write has cmd_class != 0x0f.
"""
import subprocess

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

out = run([
    "-Y", "usb.bus_id==2 && usb.device_address==3",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.data_fragment",
    "-E", "separator=|"
])

# Count ALL command classes across the entire capture
from collections import Counter
cmd_counter = Counter()
unique_cmds = set()

for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    if len(parts) < 4 or not parts[3]:
        continue
    p = parse_razer(parts[3])
    if not p:
        continue
    key = (p["cmd_class"], p["cmd_id"])
    cmd_counter[key] += 1
    unique_cmds.add(key)

print("ALL unique commands in capture #6:")
for (cc, ci), count in sorted(cmd_counter.items()):
    print(f"  0x{cc:02x}:0x{ci:02x} = {count}")

print(f"\nTotal unique command types: {len(unique_cmds)}")
print(f"Total Razer packets: {sum(cmd_counter.values())}")

# If there are ONLY 0x0f:0x03 and 0x02:0x0c, then there's really nothing else
non_led = {k: v for k, v in cmd_counter.items() if k != (0x0f, 0x03)}
print(f"\nNon-LED commands: {non_led}")
