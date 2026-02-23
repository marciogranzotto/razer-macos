#!/usr/bin/env python3
"""
Dump raw hex for ALL non-isochronous packets between the Disabled writes.
Look at raw bytes since tshark fields may not extract all data.
"""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-3.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

# Disabled writes are at t=17.8, 26.0, 34.8
# Default actions should be between: ~20-25s and ~28-33s
# Let's look at raw hex of ALL packets in those windows

for t_start, t_end, label in [(19, 25, "Between Disabled#1 and Disabled#2"),
                                (27, 34, "Between Disabled#2 and Disabled#3")]:
    print("=" * 80)
    print(f"  {label} (t={t_start}-{t_end}s)")
    print("=" * 80)

    # Get frame numbers in this window
    out = run([
        "-Y", f"usb.bus_id==2 && usb.device_address==3 && frame.time_relative>{t_start} && frame.time_relative<{t_end}",
        "-T", "fields",
        "-e", "frame.number", "-e", "frame.time_relative",
        "-e", "usb.src", "-e", "usb.dst",
        "-e", "usb.data_len",
        "-E", "separator=|"
    ])

    # Group by data_len to understand what's there
    from collections import Counter
    len_counts = Counter()
    frames_by_len = {}
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        dl = parts[4].strip() if len(parts) > 4 else "?"
        len_counts[dl] += 1
        if dl not in frames_by_len:
            frames_by_len[dl] = []
        frames_by_len[dl].append(parts[0].strip())

    print(f"  Packet data_len distribution:")
    for dl, count in sorted(len_counts.items(), key=lambda x: -x[1]):
        frames_sample = frames_by_len[dl][:3]
        print(f"    len={dl:>3s}: {count} packets (e.g. frames {', '.join(frames_sample)})")

    # Dump raw hex of non-LED 98-byte packets (if any non-0x0f:0x03)
    out2 = run([
        "-Y", f"usb.bus_id==2 && usb.device_address==3 && frame.time_relative>{t_start} && frame.time_relative<{t_end}",
        "-T", "fields",
        "-e", "frame.number", "-e", "frame.time_relative",
        "-e", "usb.src", "-e", "usb.dst",
        "-e", "usb.data_fragment",
        "-E", "separator=|"
    ])

    for line in out2.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) < 5 or not parts[4]:
            continue
        d = parts[4].replace(":", "")
        if len(d) >= 180:
            cc = int(d[12:14], 16)
            ci = int(d[14:16], 16)
            if cc == 0x0f and ci == 0x03:
                continue
            direction = "OUT" if "host" in parts[2] else "IN"
            print(f"  NON-LED RAZER: #{parts[0].strip()} [{direction}] 0x{cc:02x}:0x{ci:02x} data={d[:40]}...")

    # Now check: are there 8-byte packets (setup-only control transfers)?
    # These could be GET_REPORT requests where the response goes elsewhere
    if "8" in frames_by_len:
        print(f"\n  8-byte setup packets (potential GET_REPORT requests):")
        for frame_num in frames_by_len["8"][:10]:
            hexdump = run(["-Y", f"frame.number=={frame_num}", "-x"])
            # Extract just the setup bytes
            hex_lines = hexdump.split("\n")
            raw = ""
            for hl in hex_lines:
                if hl.startswith("0"):
                    # Parse hex dump line
                    parts_hex = hl.split("  ")
                    if len(parts_hex) >= 2:
                        hex_part = parts_hex[0][6:]  # Skip offset
                        raw += hex_part.replace(" ", "")
            if raw:
                # USBPcap header is 27 bytes, then 8 bytes of setup data
                setup_start = 27 * 2  # 54 hex chars
                setup = raw[setup_start:setup_start+16]
                print(f"    Frame #{frame_num}: setup={setup}")

    # Check for 90-byte packets (GET_REPORT responses)
    if "90" in frames_by_len:
        print(f"\n  90-byte response packets:")
        for frame_num in frames_by_len["90"][:10]:
            hexdump = run(["-Y", f"frame.number=={frame_num}", "-x"])
            hex_lines = hexdump.split("\n")
            raw = ""
            for hl in hex_lines:
                if hl.startswith("0"):
                    parts_hex = hl.split("  ")
                    if len(parts_hex) >= 2:
                        hex_part = parts_hex[0][6:]
                        raw += hex_part.replace(" ", "")
            if raw:
                # USBPcap header is 27 bytes for responses, then 90 bytes of data
                data_start = 27 * 2
                razer_data = raw[data_start:data_start+180]
                if len(razer_data) >= 16:
                    status = razer_data[0:2]
                    cc = razer_data[12:14]
                    ci = razer_data[14:16]
                    ds_hex = razer_data[10:12]
                    payload = razer_data[16:56]  # first 20 bytes of payload
                    print(f"    Frame #{frame_num}: status=0x{status} cmd=0x{cc}:0x{ci} size=0x{ds_hex} payload={payload}")
    print()
