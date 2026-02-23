#!/usr/bin/env python3
"""
Check FW version responses and ep 0x82/0x83 activity during panel swaps.
"""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-pannel-swaps.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

def extract_hex(hexdump):
    raw = ""
    for hl in hexdump.split("\n"):
        if hl and len(hl) > 6 and hl[4:6] == "  ":
            raw += hl[6:53].strip().replace(" ", "")
    return raw

# Response frames at known times
resp_frames = ["3343", "9537", "11197", "12217", "13398", "13407", "13763", "14951"]

print("=" * 80)
print("  FW VERSION RESPONSES (raw hex)")
print("=" * 80)

for fnum in resp_frames:
    time_out = run(["-Y", f"frame.number=={fnum}", "-T", "fields", "-e", "frame.time_relative"])
    hexdump = run(["-Y", f"frame.number=={fnum}", "-x"])
    raw = extract_hex(hexdump)

    # Response: 27-byte USBPcap header + 90 bytes Razer
    # But let's just show the raw bytes and try to find the Razer frame
    print(f"\n  Frame #{fnum} t={time_out.strip()}s raw={len(raw)//2}B")

    # Try to find Razer frame by looking for known patterns
    # Razer response: status=02/03, trans_id varies, ...cmd_class, cmd_id...end=0x00
    # Look for the pattern where bytes end with 0x00
    for offset in [54, 56, 52, 58]:
        if len(raw) >= offset + 180:
            chunk = raw[offset:offset+180]
            status = int(chunk[0:2], 16)
            trans_id = int(chunk[2:4], 16)
            data_size = int(chunk[10:12], 16)
            cmd_class = int(chunk[12:14], 16)
            cmd_id = int(chunk[14:16], 16)
            end = int(chunk[178:180], 16)

            if end == 0x00 and status in (0x02, 0x03) and cmd_class < 0x20:
                payload_bytes = [int(chunk[16+j*2:18+j*2], 16) for j in range(min(data_size, 10))]
                ph = " ".join(f"{x:02x}" for x in payload_bytes)
                status_name = {2: "BUSY", 3: "OK"}.get(status, f"0x{status:02x}")
                print(f"    @offset={offset//2}B: [{status_name}] 0x{cmd_class:02x}:0x{cmd_id:02x} "
                      f"size={data_size} [{ph}]")
                break

# Check keyboard endpoints for panel-related HID reports
print(f"\n{'=' * 80}")
print(f"  KEYBOARD ENDPOINT ACTIVITY (ep 0x82, 0x83)")
print(f"{'=' * 80}")

for ep_addr in [0x82, 0x83]:
    out = run([
        "-Y", f"usb.bus_id==4 && usb.device_address==1 && usb.endpoint_address==0x{ep_addr:02x}",
        "-T", "fields",
        "-e", "frame.number", "-e", "frame.time_relative",
        "-e", "usb.data_len",
        "-E", "separator=|"
    ])
    lines = [l for l in out.split("\n") if l.strip()]
    print(f"\n  Endpoint 0x{ep_addr:02x}: {len(lines)} packets")
    for line in lines:
        parts = line.split("|")
        fnum = parts[0].strip()
        time = parts[1].strip()
        dl = parts[2].strip() if len(parts) > 2 else "?"
        print(f"    #{fnum} t={time}s data_len={dl}")
        # Hex dump if data
        if int(dl) > 0:
            hexdump = run(["-Y", f"frame.number=={fnum}", "-x"])
            raw = extract_hex(hexdump)
            # HID data starts after 27-byte header
            hid = raw[54:54+32]
            b = [int(hid[i:i+2], 16) for i in range(0, len(hid), 2)]
            print(f"      HID: {' '.join(f'{x:02x}' for x in b)}")

# Also check dev 2 - it had lots of varied-size data
print(f"\n{'=' * 80}")
print(f"  DEVICE 2 (possible Bluetooth/wireless)")
print(f"{'=' * 80}")
out2 = run([
    "-Y", "usb.bus_id==4 && usb.device_address==2",
    "-T", "fields",
    "-e", "usb.endpoint_address", "-e", "usb.data_len",
    "-E", "separator=|"
])
from collections import Counter
ep_counts = Counter()
for line in out2.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    ep = parts[0].strip() if len(parts) > 0 else ""
    ep_counts[ep] += 1
print(f"  Endpoint distribution: {dict(sorted(ep_counts.items()))}")

# Check dev 2 ep 0x01 and 0x02 (OUT endpoints) for any Razer-like data
for ep in ["0x01", "0x02"]:
    out3 = run([
        "-Y", f"usb.bus_id==4 && usb.device_address==2 && usb.endpoint_address=={ep}",
        "-T", "fields", "-c", "3",
        "-e", "frame.number", "-e", "frame.time_relative", "-e", "usb.data_len",
        "-E", "separator=|"
    ])
    lines3 = [l for l in out3.split("\n") if l.strip()]
    if lines3:
        print(f"\n  Dev 2, ep {ep}: {len(lines3)} frames (showing first 3):")
        for line in lines3[:3]:
            parts = line.split("|")
            fnum = parts[0].strip()
            hexdump = run(["-Y", f"frame.number=={fnum}", "-x"])
            raw = extract_hex(hexdump)
            print(f"    #{fnum} t={parts[1].strip()} len={parts[2].strip()} raw_start={raw[54:120]}")
