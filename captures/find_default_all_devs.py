#!/usr/bin/env python3
"""
Check ALL 3 devices on Bus 2 for the "Default" command.
The Naga V2 Pro dongle registers as 3 USB devices.
"""
import subprocess

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

for dev in [1, 2, 3]:
    print("=" * 80)
    print(f"  BUS 2, DEVICE {dev}")
    print("=" * 80)

    out = run([
        "-Y", f"usb.bus_id==2 && usb.device_address=={dev}",
        "-T", "fields",
        "-e", "frame.number", "-e", "frame.time_relative",
        "-e", "usb.src", "-e", "usb.dst",
        "-e", "usb.data_len",
        "-e", "usb.data_fragment",
        "-E", "separator=|"
    ])

    lines = [l for l in out.split("\n") if l.strip()]
    total = len(lines)
    with_data = 0
    razer_frames = 0

    non_led = []
    for line in lines:
        parts = line.split("|")
        if len(parts) < 6:
            continue
        frame = parts[0].strip()
        time = parts[1].strip()
        src = parts[2].strip()
        data_len = parts[4].strip()
        data_frag = parts[5].strip() if len(parts) > 5 else ""

        if data_frag:
            with_data += 1

        d = data_frag.replace(":", "")
        direction = "OUT" if "host" in src else "IN"

        if len(d) >= 180:
            razer_frames += 1
            p = parse_razer(data_frag)
            if p:
                # Skip LED
                if p["cmd_class"] == 0x0f and p["cmd_id"] in (0x03, 0x83):
                    continue
                ds = p["data_size"]
                b = [int(p["payload"][j:j+2], 16) for j in range(0, min(ds*2, 20), 2)]
                ph = " ".join(f"{x:02x}" for x in b)
                non_led.append((float(time), frame, direction, data_len,
                    f"RAZER 0x{p['cmd_class']:02x}:0x{p['cmd_id']:02x} size={ds} [{ph}]"))
        elif len(d) > 0:
            # Non-Razer data
            non_led.append((float(time), frame, direction, data_len,
                f"RAW ({len(d)//2}B): {d[:80]}"))

    print(f"  Total packets: {total}")
    print(f"  With data: {with_data}")
    print(f"  Razer-sized frames: {razer_frames}")
    print(f"  Non-LED entries: {len(non_led)}")

    if non_led:
        print(f"\n  Non-LED commands (chronological):")
        for t, frame, direction, data_len, desc in sorted(non_led):
            print(f"    #{frame:>7s} t={t:>10.3f}s [{direction}] len={data_len:>3s} {desc}")
    print()

# Also: raw hex dump of the first few frames for each device to identify them
print("=" * 80)
print("  DEVICE IDENTIFICATION (first packets)")
print("=" * 80)

for dev in [1, 2, 3]:
    print(f"\n  --- Device {dev} ---")
    out = run([
        "-Y", f"usb.bus_id==2 && usb.device_address=={dev}",
        "-c", "5", "-V"
    ])
    # Extract key info from verbose output
    for line in out.split("\n"):
        line_stripped = line.strip()
        if any(kw in line_stripped.lower() for kw in ["idvendor", "idproduct", "device address",
                "endpoint", "interface", "binterfaceclass", "binterfacesubclass",
                "binterfaceprotocol", "iproduct", "imanufacturer"]):
            print(f"    {line_stripped}")
