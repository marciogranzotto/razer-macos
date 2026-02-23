#!/usr/bin/env python3
"""Find ALL Razer commands between t=331s and t=355s (between Volume Down and end)."""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-1.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

def parse_razer(hex_data):
    d = hex_data.replace(":", "")
    if len(d) < 180:
        return None
    return {
        "status": int(d[0:2], 16), "data_size": int(d[10:12], 16),
        "cmd_class": int(d[12:14], 16), "cmd_id": int(d[14:16], 16),
        "payload": d[16:176],
    }

out = run([
    "-Y", "usb.bus_id==2 && usb.device_address==3",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.dst",
    "-e", "usb.data_fragment",
    "-E", "separator=|"
])

print("All non-LED Razer commands between t=325s and t=360s:")
print()
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    if len(parts) < 5 or not parts[4]:
        continue
    try:
        t = float(parts[1].strip())
    except:
        continue
    if t < 325 or t > 360:
        continue
    p = parse_razer(parts[4])
    if not p:
        continue
    # Skip LED color data (0x0f:0x03)
    if p["cmd_class"] == 0x0f and p["cmd_id"] == 0x03:
        continue
    direction = "OUT" if "host" in parts[2] else "IN"
    b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 20), 2)]
    payload_hex = " ".join(f"{x:02x}" for x in b)
    print(f"  #{parts[0]:>7s} t={t:>10.3f}s [{direction}] "
          f"0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} "
          f"size={p['data_size']:>2d}  [{payload_hex}]")
