#!/usr/bin/env python3
"""
Analyze: razer-naga-2btns-change-button-1.pcapng
2-button module. Actions:
  1st button -> Keyboard 'a'
  1st button -> Default (Mouse Button 5 / Forward)
  2nd button -> Keyboard 'F1'
  2nd button -> Default (Mouse Button 4 / Back)

Goals:
  1. Discover 2-button panel button IDs
  2. Confirm whether Default from non-disabled state sends a write
"""
import subprocess
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-2btns-change-button-1.pcapng"

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

# Find the Razer device - check all bus/dev combos
print("=" * 80)
print("  DEVICE DISCOVERY")
print("=" * 80)

out = run([
    "-T", "fields",
    "-e", "usb.bus_id", "-e", "usb.device_address",
    "-e", "usb.src", "-e", "usb.dst",
    "-E", "separator=|"
])

addr_counter = Counter()
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    bus = parts[0].strip() if len(parts) > 0 else ""
    dev = parts[1].strip() if len(parts) > 1 else ""
    if bus and dev:
        addr_counter[(bus, dev)] += 1

print("Bus/Device pairs:")
for (bus, dev), count in sorted(addr_counter.items()):
    print(f"  Bus {bus} Dev {dev}: {count} packets")

# Try known locations and all discovered pairs
all_pairs = sorted(addr_counter.keys())
for bus, dev in all_pairs:
    out_test = run([
        "-Y", f"usb.bus_id=={bus} && usb.device_address=={dev}",
        "-T", "fields", "-c", "5",
        "-e", "usb.data_fragment",
        "-E", "separator=|"
    ])
    razer_count = 0
    for line in out_test.split("\n"):
        d = line.strip().replace(":", "")
        if len(d) >= 180:
            razer_count += 1
    if razer_count > 0:
        print(f"\n  Razer device found at Bus {bus} Dev {dev}")
        TARGET_BUS = bus
        TARGET_DEV = dev
        break

# Get all packets
out = run([
    "-Y", f"usb.bus_id=={TARGET_BUS} && usb.device_address=={TARGET_DEV}",
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

print(f"\nTotal Razer packets: {len(all_parsed)}")

# Command distribution
print("\n" + "=" * 80)
print("  COMMAND DISTRIBUTION")
print("=" * 80)
cmd_counts = Counter((p["cmd_class"], p["cmd_id"], p["direction"]) for p in all_parsed)
for (cls, cid, direction), count in sorted(cmd_counts.items()):
    cls_names = {0x00: "General", 0x02: "Macro/Btn", 0x03: "LED", 0x05: "Mouse",
                0x06: "Keypad", 0x07: "CustomFX", 0x09: "DPI", 0x0f: "HyperProf"}
    cls_name = cls_names.get(cls, f"0x{cls:02x}")
    print(f"  {cls_name:12s} 0x{cls:02x}:0x{cid:02x} [{direction}]: {count}")

# ALL non-LED commands
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
    marker = ""
    if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c:
        marker = " ** BTN_WRITE **"
    print(f"  #{p['frame']:>7s} t={p['time']:>14s}s [{p['direction']}] "
          f"{cls_name:10s} 0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} "
          f"size={p['data_size']:>2d}  [{payload_hex}]{marker}")

# Button writes detail
print("\n" + "=" * 80)
print("  BUTTON MAPPING WRITES (0x02:0x0c) — DETAILED")
print("=" * 80)
writes = sorted(
    [p for p in all_parsed if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c and p["direction"] == "OUT"],
    key=lambda p: float(p["time"])
)
print(f"\nTotal writes: {len(writes)}")

action_names = {
    0x00: "Disabled", 0x01: "Mouse Button", 0x02: "Keyboard Key",
    0x03: "Macro Play Once", 0x06: "Sensitivity Clutch",
    0x0a: "Multimedia", 0x0c: "Hypershift", 0x12: "Scroll Wheel",
}
key_names = {
    0x04: 'a', 0x05: 'b', 0x06: 'c', 0x07: 'd', 0x08: 'e',
    0x1e: '1', 0x1f: '2', 0x20: '3', 0x21: '4', 0x22: '5',
    0x23: '6', 0x24: '7', 0x25: '8', 0x26: '9', 0x27: '0',
    0x2d: '-', 0x2e: '=', 0x28: 'Enter', 0x29: 'Esc',
    0x3a: 'F1', 0x3b: 'F2', 0x3c: 'F3', 0x3d: 'F4',
    0x3e: 'F5', 0x3f: 'F6', 0x40: 'F7', 0x41: 'F8',
    0x42: 'F9', 0x43: 'F10', 0x44: 'F11', 0x45: 'F12',
}
mouse_names = {0x01: "Left", 0x02: "Right", 0x03: "Middle", 0x04: "Back", 0x05: "Forward"}

for i, p in enumerate(writes):
    b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
    payload_hex = " ".join(f"{x:02x}" for x in b)
    action_type = b[3] if len(b) > 3 else 0
    action = action_names.get(action_type, f"Unknown 0x{action_type:02x}")

    detail = ""
    if action_type == 0x02 and len(b) > 6:
        detail = f" -> key '{key_names.get(b[6], f'0x{b[6]:02x}')}'"
        if b[5]: detail += f" mods=0x{b[5]:02x}"
    elif action_type == 0x01 and len(b) > 5:
        detail = f" -> {mouse_names.get(b[5], f'btn {b[5]}')}"

    print(f"\n  Write #{i+1}: #{p['frame']} t={p['time']}s")
    print(f"    Raw: [{payload_hex}]")
    print(f"    Profile={b[0]}  Button=0x{b[1]:02x}  Layer={'HS' if b[2] else 'Normal'}")
    print(f"    Action: {action}{detail}")

# Summary
print(f"\n{'=' * 80}")
print(f"  SUMMARY")
print(f"{'=' * 80}")
if len(writes) >= 2:
    btn_ids = set(int(p["payload"][2:4], 16) for p in writes)
    print(f"  Button IDs seen: {', '.join(f'0x{x:02x}' for x in sorted(btn_ids))}")
    print(f"  Total writes: {len(writes)}")
    if len(writes) == 4:
        print(f"  4 writes for 4 actions = Default DOES send a write from non-disabled state!")
    elif len(writes) == 2:
        print(f"  2 writes for 4 actions = Default sends NO write (even from non-disabled)")
