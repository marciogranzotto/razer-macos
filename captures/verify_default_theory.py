#!/usr/bin/env python3
"""
Final verification: Look at capture #4 (12-btn, 10 action types).
When user set button 12 back to Default ("=" key), what was the LAST write?
If "Default" = Synapse writes the specific binding, the last write should be
keyboard key "=" (HID keycode 0x2e), NOT all zeros.

Also check capture #1 (6-btn) for the same pattern.
"""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"

def run(pcap, args, timeout=600):
    cmd = [TSHARK, "-r", pcap] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

def parse_razer(hex_data):
    d = hex_data.replace(":", "")
    if len(d) < 180:
        return None
    return {
        "status": int(d[0:2], 16),
        "data_size": int(d[10:12], 16), "cmd_class": int(d[12:14], 16),
        "cmd_id": int(d[14:16], 16), "payload": d[16:176],
    }

# Check capture #4 (12-btn panel, 10 action changes to button 12)
print("=" * 80)
print("  CAPTURE #4: Last few button writes to button 0x4b")
print("  User sequence ended with: Disable, then Default ('=' key)")
print("=" * 80)

PCAP4 = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-1.pcapng"
out = run(PCAP4, [
    "-Y", "usb.bus_id==2 && usb.device_address==3",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.data_fragment",
    "-E", "separator=|"
])

writes_4b = []
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    if len(parts) < 4 or not parts[3]:
        continue
    p = parse_razer(parts[3])
    if not p:
        continue
    if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x0c and "host" in parts[2]:
        ds = p["data_size"]
        b = [int(p["payload"][j:j+2], 16) for j in range(0, ds*2, 2)]
        if len(b) >= 2 and b[1] == 0x4b:
            payload_hex = " ".join(f"{x:02x}" for x in b)
            writes_4b.append({
                "frame": parts[0].strip(),
                "time": parts[1].strip(),
                "payload": b,
                "hex": payload_hex,
            })

print(f"\nAll {len(writes_4b)} writes to button 0x4b:")
for i, w in enumerate(writes_4b):
    action_type = w["payload"][3] if len(w["payload"]) > 3 else 0
    action_names = {
        0x00: "DISABLED/DEFAULT",
        0x01: "Mouse Button",
        0x02: "Keyboard Key",
        0x03: "Macro Play Once",
        0x06: "Sensitivity Clutch",
        0x0a: "Multimedia",
        0x0c: "Hypershift",
        0x12: "Scroll Wheel",
    }
    name = action_names.get(action_type, f"Unknown 0x{action_type:02x}")

    extra = ""
    if action_type == 0x02 and len(w["payload"]) > 6:
        keycode = w["payload"][6]
        keycodes = {0x04: "a", 0x1e: "1", 0x1f: "2", 0x20: "3", 0x21: "4",
                   0x22: "5", 0x23: "6", 0x24: "7", 0x25: "8", 0x26: "9",
                   0x27: "0", 0x2d: "-", 0x2e: "="}
        extra = f" key='{keycodes.get(keycode, f'0x{keycode:02x}')}'"

    print(f"  #{i+1:>2d} t={w['time']:>14s}s  type=0x{action_type:02x} {name:20s}{extra}  [{w['hex']}]")

print(f"\n  Last write: [{writes_4b[-1]['hex']}]")
if writes_4b[-1]["payload"][3] == 0x00 and all(b == 0 for b in writes_4b[-1]["payload"][3:]):
    print("  => Last write is all-zeros (Disabled)")
    print("  => This means 'Default' was the LAST action but produced NO write")
    print("  => OR 'Default' was already done when user stopped capture")
elif writes_4b[-1]["payload"][3] == 0x02:
    print("  => Last write is a keyboard key binding!")
    print("  => Synapse writes the specific default binding, not a special 'restore' command")
