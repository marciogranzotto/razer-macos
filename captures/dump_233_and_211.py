#!/usr/bin/env python3
"""
Dump ALL 10 data packets from 2.3.3 (keyboard endpoint 3) and
check 2.1.1 (dev 1) for any non-mouse-movement data during Default windows.
"""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-3.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

# Get all 10 data frames from endpoint 2.3.3
print("=" * 80)
print("  ENDPOINT 2.3.3 (Keyboard HID ep3) - ALL 10 DATA PACKETS")
print("  Disabled writes at t=17.8, 26.0, 34.8")
print("  Default expected at ~t=21, ~t=30, ~t=38")
print("=" * 80)

out = run([
    "-Y", "usb.device_address==3 && usb.endpoint_address==0x83 && usb.data_len>0",
    "-T", "fields",
    "-e", "frame.number",
    "-E", "separator=|"
])

frames_233 = [l.strip() for l in out.split("\n") if l.strip()]
print(f"Frames: {frames_233}")

for fnum in frames_233:
    hexdump = run(["-Y", f"frame.number=={fnum}", "-x"])
    # Parse time from verbose output
    time_out = run([
        "-Y", f"frame.number=={fnum}",
        "-T", "fields", "-e", "frame.time_relative",
    ])
    print(f"\n  Frame #{fnum} t={time_out.strip()}s")
    # USBPcap header is 27 bytes (0x1b), then HID data
    for hl in hexdump.split("\n"):
        print(f"    {hl}")
    # Extract just the HID data bytes (after 27-byte header)
    raw = ""
    for hl in hexdump.split("\n"):
        if hl and hl[0:4].strip() and not hl.startswith("Frame"):
            # hex dump line: offset  hex bytes  ascii
            hex_part = hl[6:53].strip()  # hex bytes
            raw += hex_part.replace(" ", "")
    if len(raw) >= 54 + 16:  # 27 header bytes * 2 + 8 data bytes * 2
        hid_data = raw[54:54+16]
        b = [int(hid_data[i:i+2], 16) for i in range(0, len(hid_data), 2)]
        print(f"    HID data: {' '.join(f'{x:02x}' for x in b)}")
        # Interpret as keyboard HID report
        if len(b) >= 8:
            modifiers = b[0]
            keys = b[2:]
            key_names = {
                0x04: 'a', 0x05: 'b', 0x06: 'c', 0x07: 'd', 0x08: 'e',
                0x1e: '1', 0x1f: '2', 0x20: '3', 0x21: '4', 0x22: '5',
                0x23: '6', 0x24: '7', 0x25: '8', 0x26: '9', 0x27: '0',
                0x2d: '-', 0x2e: '=', 0x28: 'Enter', 0x29: 'Esc',
                0x59: 'KP1', 0x5a: 'KP2', 0x5b: 'KP3', 0x5c: 'KP4',
                0x5d: 'KP5', 0x5e: 'KP6', 0x5f: 'KP7', 0x60: 'KP8',
                0x61: 'KP9', 0x62: 'KP0', 0x63: 'KP.', 0x54: 'KP/',
                0x55: 'KP*', 0x56: 'KP-', 0x57: 'KP+', 0x58: 'KPEnter',
            }
            active = [key_names.get(k, f'0x{k:02x}') for k in keys if k != 0]
            mod_flags = []
            if modifiers & 0x01: mod_flags.append("LCtrl")
            if modifiers & 0x02: mod_flags.append("LShift")
            if modifiers & 0x04: mod_flags.append("LAlt")
            if modifiers & 0x08: mod_flags.append("LGui")
            if modifiers & 0x10: mod_flags.append("RCtrl")
            if modifiers & 0x20: mod_flags.append("RShift")
            if modifiers & 0x40: mod_flags.append("RAlt")
            if modifiers & 0x80: mod_flags.append("RGui")
            mods = "+".join(mod_flags) if mod_flags else "none"
            print(f"    Keyboard: mods={mods} keys={active if active else '(none = key release)'}")

print(f"\n\n{'=' * 80}")
print("  ENDPOINT 2.3.2 (Keyboard HID ep2) - check again carefully")
print("=" * 80)

# Maybe ep2 has a different endpoint address
out2 = run([
    "-Y", "usb.device_address==3 && usb.endpoint_address==0x82",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative", "-e", "usb.data_len",
    "-E", "separator=|"
])
lines2 = [l for l in out2.split("\n") if l.strip()]
print(f"  Total packets for ep 0x82: {len(lines2)}")
for l in lines2[:10]:
    print(f"    {l}")

# Also check ep2 as OUT (0x02)
out2b = run([
    "-Y", "usb.device_address==3 && usb.endpoint_address==0x02",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative", "-e", "usb.data_len",
    "-E", "separator=|"
])
lines2b = [l for l in out2b.split("\n") if l.strip()]
print(f"  Total packets for ep 0x02 (OUT): {len(lines2b)}")

# Check ep3 as OUT (0x03)
out3b = run([
    "-Y", "usb.device_address==3 && usb.endpoint_address==0x03",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative", "-e", "usb.data_len",
    "-E", "separator=|"
])
lines3b = [l for l in out3b.split("\n") if l.strip()]
print(f"  Total packets for ep 0x03 (OUT): {len(lines3b)}")

print(f"\n\n{'=' * 80}")
print("  DEVICE 2.1.1 - UNIQUE DATA PATTERNS IN DEFAULT WINDOWS")
print("=" * 80)

# 2.1.1 has 64-byte interrupt data. Check if data changes in the Default windows
# vs the Disabled windows
out3 = run([
    "-Y", "usb.device_address==1 && usb.endpoint_address==0x81 && usb.data_len==64",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-E", "separator=|"
])

frames_211 = []
for l in out3.split("\n"):
    if not l.strip():
        continue
    parts = l.split("|")
    t = float(parts[1].strip())
    frames_211.append((t, parts[0].strip()))

# Get hex dumps for a sample in each window
windows = [
    (14, 17, "Before Disabled #1"),
    (17, 19, "Disabled #1 window"),
    (19, 25, "Default #1 window"),
    (25, 27, "Disabled #2 window"),
    (27, 34, "Default #2 window"),
    (34, 36, "Disabled #3 window"),
    (36, 42, "Default #3 window"),
]

for wstart, wend, wlabel in windows:
    in_window = [(t, f) for t, f in frames_211 if wstart < t < wend]
    print(f"\n  {wlabel} (t={wstart}-{wend}s): {len(in_window)} packets")
    if in_window:
        # Dump first packet in window
        t, fnum = in_window[0]
        hexdump = run(["-Y", f"frame.number=={fnum}", "-x"])
        raw = ""
        for hl in hexdump.split("\n"):
            if hl and hl[0:4].strip() and not hl.startswith("Frame"):
                hex_part = hl[6:53].strip()
                raw += hex_part.replace(" ", "")
        if len(raw) >= 54:
            data = raw[54:]  # After 27-byte USBPcap header
            print(f"    Sample t={t:.3f}s: {data[:128]}")
