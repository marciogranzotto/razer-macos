#!/usr/bin/env python3
"""Find ALL packets that reference button 0x4b in the 12-button capture."""
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

# Use tshark contains filter to find packets with 0x4b in the data
# The byte 0x4b at position 1 of the Razer payload (byte 9 of usb.data_fragment)
# In the 90-byte Razer frame: [status][trans_id][remaining:2][proto_type][data_size][cmd_class][cmd_id][payload...]
# So byte[1] of payload = byte[9] of the Razer frame = byte[17] of usb.data_fragment (for 98-byte packets with 8 setup bytes)

# Just get ALL Razer-sized packets and filter in Python
out = run([
    "-Y", "usb.bus_id==2 && usb.device_address==3",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.dst",
    "-e", "usb.data_fragment",
    "-E", "separator=|"
])

found = []
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    if len(parts) < 5 or not parts[4]:
        continue
    p = parse_razer(parts[4])
    if not p:
        continue

    # Check if payload byte[1] == 0x4b (button ID position)
    if p["data_size"] >= 2:
        btn_id = int(p["payload"][2:4], 16)
        if btn_id == 0x4b:
            direction = "OUT" if "host" in parts[2] else "IN"
            b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 20), 2)]
            payload_hex = " ".join(f"{x:02x}" for x in b)
            found.append({
                "frame": parts[0].strip(),
                "time": parts[1].strip(),
                "direction": direction,
                "cmd_class": p["cmd_class"],
                "cmd_id": p["cmd_id"],
                "data_size": p["data_size"],
                "payload_hex": payload_hex,
                "status": p["status"],
            })

print(f"Packets referencing button 0x4b: {len(found)}")
print()
for f in found:
    status_names = {0: "NEW", 2: "BUSY", 3: "OK", 4: "FAIL", 5: "TIMEOUT"}
    status = status_names.get(f["status"], f"0x{f['status']:02x}")
    print(f"  #{f['frame']:>7s} t={f['time']:>14s}s [{f['direction']}] "
          f"0x{f['cmd_class']:02x}:0x{f['cmd_id']:02x} status={status:<7s} "
          f"size={f['data_size']:>2d}  [{f['payload_hex']}]")
