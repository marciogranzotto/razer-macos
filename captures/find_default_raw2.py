#!/usr/bin/env python3
"""
Raw hex dump of specific frames in the time gaps.
Focus on finding any control transfer that isn't LED data.
"""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-3.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

# Get all 98-byte packets between t=19 and t=25 (gap where Default #1 should be)
# and check if any are NOT LED data
out = run([
    "-Y", "usb.bus_id==2 && usb.device_address==3 && frame.time_relative>19 && frame.time_relative<25",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.dst",
    "-e", "usb.data_len",
    "-e", "usb.data_fragment",
    "-E", "separator=|"
])

print("Non-LED 98-byte packets in gap (t=19-25s):")
all_98byte = []
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    if len(parts) < 6:
        continue
    data_len = parts[4].strip()
    data_frag = parts[5].strip() if len(parts) > 5 else ""
    if data_len == "98" and data_frag:
        d = data_frag.replace(":", "")
        if len(d) >= 16:
            cc = int(d[12:14], 16)
            ci = int(d[14:16], 16)
            if cc != 0x0f or ci != 0x03:
                ds = int(d[10:12], 16)
                b_hex = d[16:16+ds*2]
                print(f"  #{parts[0].strip()} t={parts[1].strip()} 0x{cc:02x}:0x{ci:02x} size={ds} payload={b_hex}")
            all_98byte.append((cc, ci))

if not any(cc != 0x0f or ci != 0x03 for cc, ci in all_98byte):
    print("  (none — all 98-byte packets are LED data)")

# Maybe the "Default" command goes via a different USB interface on the same device?
# Check endpoint usage
print("\n" + "=" * 80)
print("  ENDPOINT USAGE (all packets in gap t=19-25s)")
print("=" * 80)

out2 = run([
    "-Y", "usb.bus_id==2 && usb.device_address==3 && frame.time_relative>19 && frame.time_relative<25",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.endpoint_address", "-e", "usb.data_len",
    "-E", "separator=|"
])

from collections import Counter
endpoint_counts = Counter()
for line in out2.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    ep = parts[2].strip() if len(parts) > 2 else "?"
    dl = parts[3].strip() if len(parts) > 3 else "?"
    endpoint_counts[(ep, dl)] += 1

print("  Endpoint x DataLen:")
for (ep, dl), count in sorted(endpoint_counts.items()):
    print(f"    endpoint={ep:>6s} data_len={dl:>3s}: {count}")

# Let's also check: does USBPcap capture ALL interfaces?
# The 8-byte packets with data_len=8 could be interrupt IN transfers from endpoints 0x81/0x82/0x83
# These would be the HID reports from the mouse/keyboard interfaces
print("\n" + "=" * 80)
print("  CHECK 8-BYTE PACKETS (HID interrupt transfers?)")
print("=" * 80)

# Dump a few 8-byte packets
out3 = run([
    "-Y", "usb.bus_id==2 && usb.device_address==3 && usb.data_len==8 && frame.time_relative>19 && frame.time_relative<25",
    "-T", "fields", "-c", "5",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.endpoint_address",
    "-e", "usb.src", "-e", "usb.dst",
    "-E", "separator=|"
])
print("First 5 eight-byte packets:")
for line in out3.split("\n"):
    if line.strip():
        print(f"  {line}")

# Raw hex of one
sample_frames = []
for line in out3.split("\n"):
    if line.strip():
        sample_frames.append(line.split("|")[0].strip())

if sample_frames:
    print(f"\n  Raw hex of frame #{sample_frames[0]}:")
    hexdump = run(["-Y", f"frame.number=={sample_frames[0]}", "-x"])
    print(hexdump[:500])

# Finally, let's try the bigger capture (capture #2) which had more actions
# and see if dev 1 or dev 2 had any interesting data during button changes
print("\n" + "=" * 80)
print("  CHECK CAPTURE #2 (more actions) - ALL DEVICES")
print("=" * 80)

PCAP2 = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-2.pcapng"

for dev in [1, 2]:
    out4 = subprocess.run(
        [TSHARK, "-r", PCAP2,
         "-Y", f"usb.bus_id==2 && usb.device_address=={dev}",
         "-T", "fields",
         "-e", "frame.number", "-e", "frame.time_relative",
         "-e", "usb.src", "-e", "usb.data_len",
         "-e", "usb.data_fragment",
         "-E", "separator=|"],
        capture_output=True, text=True, timeout=600, errors='replace'
    ).stdout.strip()

    total = len([l for l in out4.split("\n") if l.strip()])
    with_frag = 0
    for line in out4.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) > 4 and parts[4].strip():
            with_frag += 1
    print(f"  Dev {dev}: {total} packets, {with_frag} with data_fragment")
