#!/usr/bin/env python3
"""
Verify raw hex parsing for panel swap capture.
Check if offset is correct by looking at raw bytes.
"""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-pannel-swaps.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

# Get first few 98-byte frames
out = run([
    "-Y", "usb.bus_id==4 && usb.device_address==1 && usb.endpoint_address==0x00 && usb.data_len==98",
    "-T", "fields", "-c", "5",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src",
    "-E", "separator=|"
])

for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    fnum = parts[0].strip()
    time = parts[1].strip()
    src = parts[2].strip()
    direction = "OUT" if "host" in src else "IN"

    hexdump = run(["-Y", f"frame.number=={fnum}", "-x"])
    raw = ""
    for hl in hexdump.split("\n"):
        if hl and len(hl) > 6 and hl[4:6] == "  ":
            hex_part = hl[6:53].strip()
            raw += hex_part.replace(" ", "")

    print(f"\nFrame #{fnum} t={time}s [{direction}] raw_len={len(raw)//2}")
    print(f"  Full hex: {raw}")

    # Show different offset interpretations
    for offset_name, offset in [("27B (response)", 54), ("35B (SET_REPORT)", 70), ("28B", 56), ("36B", 72)]:
        if len(raw) >= offset + 16:
            chunk = raw[offset:offset+180]
            if len(chunk) >= 16:
                status = int(chunk[0:2], 16)
                trans_id = int(chunk[2:4], 16)
                data_size = int(chunk[10:12], 16) if len(chunk) > 12 else -1
                cmd_class = int(chunk[12:14], 16) if len(chunk) > 14 else -1
                cmd_id = int(chunk[14:16], 16) if len(chunk) > 16 else -1
                end_byte = int(chunk[178:180], 16) if len(chunk) >= 180 else -1
                print(f"  @{offset_name}: status=0x{status:02x} tid=0x{trans_id:02x} "
                      f"size={data_size} cmd=0x{cmd_class:02x}:0x{cmd_id:02x} "
                      f"end=0x{end_byte:02x}")

# Also check first 90-byte frame (response)
print("\n\n=== 90-BYTE FRAMES (responses) ===")
out2 = run([
    "-Y", "usb.bus_id==4 && usb.device_address==1 && usb.data_len==90",
    "-T", "fields", "-c", "3",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src",
    "-E", "separator=|"
])

for line in out2.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    fnum = parts[0].strip()
    hexdump = run(["-Y", f"frame.number=={fnum}", "-x"])
    raw = ""
    for hl in hexdump.split("\n"):
        if hl and len(hl) > 6 and hl[4:6] == "  ":
            hex_part = hl[6:53].strip()
            raw += hex_part.replace(" ", "")

    print(f"\nFrame #{fnum} raw_len={len(raw)//2}")
    print(f"  Full hex: {raw}")
    for offset_name, offset in [("27B", 54), ("28B", 56)]:
        if len(raw) >= offset + 16:
            chunk = raw[offset:offset+180]
            status = int(chunk[0:2], 16)
            trans_id = int(chunk[2:4], 16)
            data_size = int(chunk[10:12], 16) if len(chunk) > 12 else -1
            cmd_class = int(chunk[12:14], 16) if len(chunk) > 14 else -1
            cmd_id = int(chunk[14:16], 16) if len(chunk) > 16 else -1
            end_byte = int(chunk[178:180], 16) if len(chunk) >= 180 else -1
            print(f"  @{offset_name}: status=0x{status:02x} tid=0x{trans_id:02x} "
                  f"size={data_size} cmd=0x{cmd_class:02x}:0x{cmd_id:02x} "
                  f"end=0x{end_byte:02x}")

# Verbose decode to check USBPcap header size
print("\n\n=== VERBOSE FIRST FRAME ===")
out3 = run([
    "-Y", "usb.bus_id==4 && usb.device_address==1 && usb.data_len==98",
    "-c", "1", "-V"
])
for line in out3.split("\n"):
    ls = line.strip()
    if any(kw in ls.lower() for kw in ["header size", "data length", "setup",
            "brequest", "wvalue", "fragment", "capdata", "hid", "razer",
            "usbpcap", "irp", "endpoint", "function"]):
        print(f"  {ls}")
