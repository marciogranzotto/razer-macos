#!/usr/bin/env python3
"""
Look at ALL USB packets in capture 2, not just Razer-sized ones.
Check if "Default" uses a different packet size or format.
"""
import subprocess
from collections import Counter

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-2.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

# Get ALL packets for bus 2 dev 3, including those without data_fragment
out = run([
    "-Y", "usb.bus_id==2 && usb.device_address==3",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.dst",
    "-e", "usb.transfer_type", "-e", "usb.data_len",
    "-e", "usb.data_fragment", "-e", "usb.setup.bRequest",
    "-E", "separator=|"
])

lines = [l for l in out.split("\n") if l.strip()]
print(f"Total packets for bus 2 dev 3: {len(lines)}")

# Classify by data length
data_lens = Counter()
transfer_types = Counter()
non_led_non_razer = []

for line in lines:
    parts = line.split("|")
    frame = parts[0].strip() if len(parts) > 0 else ""
    time = parts[1].strip() if len(parts) > 1 else ""
    src = parts[2].strip() if len(parts) > 2 else ""
    dst = parts[3].strip() if len(parts) > 3 else ""
    xfer_type = parts[4].strip() if len(parts) > 4 else ""
    data_len = parts[5].strip() if len(parts) > 5 else ""
    data_frag = parts[6].strip() if len(parts) > 6 else ""
    b_request = parts[7].strip() if len(parts) > 7 else ""

    data_lens[data_len] += 1
    transfer_types[xfer_type] += 1

    # Check for non-LED packets with unexpected sizes
    d = data_frag.replace(":", "")
    is_razer_sized = len(d) in (180, 196)  # 90 bytes or 98 bytes

    if data_frag and not is_razer_sized:
        direction = "OUT" if "host" in src else "IN"
        non_led_non_razer.append({
            "frame": frame, "time": time, "direction": direction,
            "data_len": data_len, "data": data_frag[:80],
            "xfer_type": xfer_type, "b_request": b_request,
            "full_data": d,
        })

print("\nData length distribution:")
for dl, count in sorted(data_lens.items(), key=lambda x: -x[1]):
    print(f"  data_len={dl}: {count}")

print("\nTransfer type distribution:")
for tt, count in sorted(transfer_types.items(), key=lambda x: -x[1]):
    # 0x02=control, 0x01=isochronous, 0x03=interrupt
    names = {"0x02": "CONTROL", "0x01": "ISOCHRONOUS", "0x03": "INTERRUPT", "0x00": "BULK"}
    name = names.get(tt, tt)
    print(f"  {name} ({tt}): {count}")

print(f"\nNon-Razer-sized packets with data: {len(non_led_non_razer)}")
for p in non_led_non_razer[:50]:
    print(f"  #{p['frame']:>7s} t={p['time']:>14s}s [{p['direction']}] "
          f"type={p['xfer_type']} len={p['data_len']} bReq={p['b_request']} "
          f"data={p['data']}")

# Now let's look at timing more carefully
# How many user actions between what timestamps?
print("\n" + "=" * 80)
print("  TIMING OF ALL NON-LED RAZER COMMANDS")
print("=" * 80)

for line in lines:
    parts = line.split("|")
    frame = parts[0].strip() if len(parts) > 0 else ""
    time = parts[1].strip() if len(parts) > 1 else ""
    src = parts[2].strip() if len(parts) > 2 else ""
    data_frag = parts[6].strip() if len(parts) > 6 else ""

    d = data_frag.replace(":", "")
    if len(d) < 180:
        continue

    # Parse Razer frame
    cmd_class = int(d[12:14], 16)
    cmd_id = int(d[14:16], 16)

    # Skip LED color data
    if cmd_class == 0x0f and cmd_id == 0x03:
        continue

    data_size = int(d[10:12], 16)
    payload = d[16:176]
    b = [int(payload[j:j+2], 16) for j in range(0, min(data_size*2, 20), 2)]
    payload_hex = " ".join(f"{x:02x}" for x in b)
    direction = "OUT" if "host" in src else "IN"

    print(f"  #{frame:>7s} t={time:>14s}s [{direction}] "
          f"0x{cmd_class:02x}:0x{cmd_id:02x} size={data_size:>2d}  [{payload_hex}]")
