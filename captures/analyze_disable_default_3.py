#!/usr/bin/env python3
"""
Analyze capture: razer-naga-12btns-change-button-3.pcapng
3x Disabled, 3x Default on button 1 of 12-btn panel.
If we see only 3 writes, "Default" sends no USB command.
"""
import subprocess
from collections import Counter

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
        "status": int(d[0:2], 16), "trans_id": int(d[2:4], 16),
        "remaining": int(d[4:8], 16), "proto_type": int(d[8:10], 16),
        "data_size": int(d[10:12], 16), "cmd_class": int(d[12:14], 16),
        "cmd_id": int(d[14:16], 16), "payload": d[16:176],
        "crc": int(d[176:178], 16), "end": int(d[178:180], 16),
    }

out = run([
    "-Y", "usb.bus_id==2 && usb.device_address==3",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.dst",
    "-e", "usb.data_fragment",
    "-E", "separator=|"
])

all_parsed = []
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    if len(parts) < 5 or not parts[4]:
        continue
    parsed = parse_razer(parts[4])
    if not parsed:
        continue
    parsed["frame"] = parts[0].strip()
    parsed["time"] = parts[1].strip()
    parsed["direction"] = "OUT" if "host" in parts[2] else "IN"
    all_parsed.append(parsed)

print(f"Total Razer packets: {len(all_parsed)}")

# Command distribution
print("\nCommand distribution:")
cmd_counts = Counter((p["cmd_class"], p["cmd_id"], p["direction"]) for p in all_parsed)
for (cls, cid, direction), count in sorted(cmd_counts.items()):
    cls_names = {0x00: "General", 0x02: "Macro/Btn", 0x03: "LED", 0x05: "Mouse",
                0x06: "Keypad", 0x07: "CustomFX", 0x09: "DPI", 0x0f: "HyperProf"}
    cls_name = cls_names.get(cls, f"0x{cls:02x}")
    print(f"  {cls_name:12s} 0x{cls:02x}:0x{cid:02x} [{direction}]: {count}")

# ALL non-LED commands chronologically
print("\n" + "=" * 80)
print("  ALL NON-LED COMMANDS (chronological)")
print("=" * 80)
interesting = sorted(
    [p for p in all_parsed
     if not (p["cmd_class"] == 0x0f and p["cmd_id"] in (0x03, 0x83))],
    key=lambda p: float(p["time"])
)
for p in interesting:
    cls_names = {0x00: "General", 0x02: "Macro/Btn", 0x03: "LED", 0x05: "Mouse",
                0x06: "Keypad", 0x07: "CustomFX", 0x09: "DPI", 0x0f: "HyperProf"}
    cls_name = cls_names.get(p["cmd_class"], f"0x{p['cmd_class']:02x}")
    b = [int(p["payload"][j:j+2], 16) for j in range(0, min(p["data_size"]*2, 20), 2)]
    payload_hex = " ".join(f"{x:02x}" for x in b)
    status_names = {0: "NEW", 2: "BUSY", 3: "OK", 4: "FAIL", 5: "TIMEOUT"}
    status = status_names.get(p["status"], f"0x{p['status']:02x}")
    marker = ""
    if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c:
        marker = " ** BTN_WRITE **"
    print(f"  #{p['frame']:>7s} t={p['time']:>14s}s [{p['direction']}] status={status:<5s} "
          f"{cls_name:10s} 0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} "
          f"size={p['data_size']:>2d}  [{payload_hex}]{marker}")

# Button writes summary
writes = [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c and p["direction"] == "OUT"]
print(f"\n{'=' * 80}")
print(f"  RESULT: {len(writes)} button mapping writes found")
print(f"  User performed 6 actions (3x Disabled + 3x Default)")
if len(writes) == 3:
    print(f"  => CONFIRMED: 'Default' sends NO USB command!")
elif len(writes) == 6:
    print(f"  => Both Disabled and Default send writes - check payloads for differences")
else:
    print(f"  => Unexpected count, investigate further")
print(f"{'=' * 80}")
