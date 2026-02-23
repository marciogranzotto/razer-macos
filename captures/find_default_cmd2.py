#!/usr/bin/env python3
"""
Find the Default command - dump ALL packets with any data, no type filter.
"""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-3.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

# First: what are the Disabled write timestamps?
out = run([
    "-Y", "usb.bus_id==2 && usb.device_address==3",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.dst",
    "-e", "usb.data_fragment",
    "-E", "separator=|"
])

disabled_times = []
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    if len(parts) < 5 or not parts[4]:
        continue
    d = parts[4].replace(":", "")
    if len(d) >= 180:
        cc = int(d[12:14], 16)
        ci = int(d[14:16], 16)
        if cc == 0x02 and ci == 0x0c:
            t = float(parts[1].strip())
            disabled_times.append((t, parts[0].strip()))
            print(f"Disabled write: t={t:.3f}s frame #{parts[0].strip()}")

print(f"\nTotal Disabled writes: {len(disabled_times)}")

# Now get ALL packets in the capture for bus 2 dev 3, with ALL data fields
# Between each pair of Disabled writes, look for anything unusual
print("\n" + "=" * 80)
print("  ALL NON-LED PACKETS WITH DATA (any size)")
print("=" * 80)

all_lines = out.split("\n")
non_led_with_data = []
for line in all_lines:
    if not line.strip():
        continue
    parts = line.split("|")
    if len(parts) < 5 or not parts[4]:
        continue
    d = parts[4].replace(":", "")
    frame = parts[0].strip()
    time = float(parts[1].strip())
    direction = "OUT" if "host" in parts[2] else "IN"

    # Parse as Razer if possible
    if len(d) >= 180:
        cc = int(d[12:14], 16)
        ci = int(d[14:16], 16)
        ds = int(d[10:12], 16)
        # Skip LED
        if cc == 0x0f and ci == 0x03:
            continue
        payload = d[16:176]
        b = [int(payload[j:j+2], 16) for j in range(0, min(ds*2, 20), 2)]
        ph = " ".join(f"{x:02x}" for x in b)
        non_led_with_data.append((time, frame, direction, f"RAZER 0x{cc:02x}:0x{ci:02x} size={ds} [{ph}]", len(d)//2))
    else:
        # Non-Razer data - show raw
        non_led_with_data.append((time, frame, direction, f"RAW ({len(d)//2} bytes): {d[:60]}", len(d)//2))

for t, frame, direction, desc, size in sorted(non_led_with_data):
    print(f"  #{frame:>7s} t={t:>10.3f}s [{direction}] {desc}")

# Step 2: Check if there are packets on DIFFERENT device addresses
# Maybe "Default" goes to a different USB endpoint
print("\n" + "=" * 80)
print("  CHECK OTHER DEVICE ADDRESSES ON BUS 2")
print("=" * 80)

out2 = run([
    "-Y", "usb.bus_id==2 && usb.device_address!=3",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.device_address",
    "-e", "usb.src", "-e", "usb.dst",
    "-e", "usb.data_fragment",
    "-E", "separator=|"
])

other_devs = set()
other_with_data = []
for line in out2.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    dev_addr = parts[2].strip() if len(parts) > 2 else ""
    other_devs.add(dev_addr)
    if len(parts) > 5 and parts[5].strip():
        d = parts[5].replace(":", "")
        t = float(parts[1].strip()) if parts[1].strip() else 0
        # Only show if in the time window of our test
        if t > 10 and t < 50 and len(d) >= 20:
            direction = "OUT" if "host" in parts[3] else "IN"
            other_with_data.append((t, parts[0].strip(), dev_addr, direction, d[:80]))

print(f"Other device addresses on bus 2: {other_devs}")
if other_with_data:
    print(f"Packets with data from other devices (t=10-50s):")
    for t, frame, dev, direction, data in sorted(other_with_data)[:20]:
        print(f"  #{frame:>7s} t={t:>10.3f}s dev={dev} [{direction}] {data}")

# Step 3: Check ALL buses
print("\n" + "=" * 80)
print("  CHECK ALL BUSES")
print("=" * 80)

out3 = run([
    "-c", "100",
    "-T", "fields",
    "-e", "frame.number",
    "-e", "usb.bus_id", "-e", "usb.device_address",
    "-e", "usb.src", "-e", "usb.dst",
    "-E", "separator=|"
])
buses = set()
for line in out3.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    bus = parts[1].strip() if len(parts) > 1 else ""
    dev = parts[2].strip() if len(parts) > 2 else ""
    buses.add((bus, dev))

print(f"Bus/Device pairs seen: {sorted(buses)}")
