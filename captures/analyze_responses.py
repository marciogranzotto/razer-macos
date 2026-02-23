#!/usr/bin/env python3
"""Check what field contains the 90-byte response data."""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-2.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

# Get the response frames with multiple potential data fields
# Frame 13700 should be the response to the first btn write at frame 13685
for frame_num in ["13700", "24378", "141244", "155414"]:
    print(f"\n=== Frame #{frame_num} ===")
    out = run([
        "-Y", f"frame.number=={frame_num}",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "usb.data_fragment",
        "-e", "usb.control.data",
        "-e", "usb.capdata",
        "-e", "usb.setup.bRequest",
        "-e", "usb.data_len",
        "-E", "separator=|"
    ])
    print(f"  data_fragment | control.data | capdata | bRequest | data_len")
    for line in out.split("\n"):
        if line.strip():
            parts = line.split("|")
            print(f"  frag={parts[1][:40] if len(parts)>1 else ''}")
            print(f"  ctrl={parts[2][:40] if len(parts)>2 else ''}")
            print(f"  cap ={parts[3][:40] if len(parts)>3 else ''}")
            print(f"  bReq={parts[4] if len(parts)>4 else ''}")
            print(f"  dLen={parts[5] if len(parts)>5 else ''}")

# Also try raw hex dump of one response
print("\n\n=== RAW HEX DUMP of frame 13700 ===")
out = run(["-Y", "frame.number==13700", "-x"])
print(out[:2000])

# And the corresponding request (8-byte setup)
print("\n\n=== RAW HEX DUMP of frame 13699 (setup packet) ===")
out = run(["-Y", "frame.number==13699", "-x"])
print(out[:2000])
