#!/usr/bin/env python3
"""
Find the "Default" command by looking at ALL USB data, not just 90-byte Razer frames.
The default command might use a different packet size, different field, or different format.
"""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-3.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

# Step 1: Get ALL control transfers (type 0x02) with every possible data field
print("=" * 80)
print("  ALL CONTROL TRANSFERS (not just Razer-sized)")
print("=" * 80)

out = run([
    "-Y", "usb.bus_id==2 && usb.device_address==3 && usb.transfer_type==0x02",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.dst",
    "-e", "usb.data_len",
    "-e", "usb.data_fragment",
    "-e", "usb.control.data",
    "-e", "usb.capdata",
    "-e", "usb.setup.bRequest",
    "-e", "usb.setup.bmRequestType",
    "-e", "usb.setup.wValue",
    "-e", "usb.setup.wIndex",
    "-e", "usb.setup.wLength",
    "-E", "separator=|"
])

all_ctrl = []
for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    p = {
        "frame": parts[0].strip() if len(parts) > 0 else "",
        "time": parts[1].strip() if len(parts) > 1 else "",
        "src": parts[2].strip() if len(parts) > 2 else "",
        "dst": parts[3].strip() if len(parts) > 3 else "",
        "data_len": parts[4].strip() if len(parts) > 4 else "",
        "data_fragment": parts[5].strip() if len(parts) > 5 else "",
        "control_data": parts[6].strip() if len(parts) > 6 else "",
        "capdata": parts[7].strip() if len(parts) > 7 else "",
        "bRequest": parts[8].strip() if len(parts) > 8 else "",
        "bmRequestType": parts[9].strip() if len(parts) > 9 else "",
        "wValue": parts[10].strip() if len(parts) > 10 else "",
        "wIndex": parts[11].strip() if len(parts) > 11 else "",
        "wLength": parts[12].strip() if len(parts) > 12 else "",
    }
    p["direction"] = "OUT" if "host" in p["src"] else "IN"
    all_ctrl.append(p)

print(f"Total control transfers: {len(all_ctrl)}")

# Filter out LED data (0x0f:0x03) - check in data_fragment
non_led = []
for p in all_ctrl:
    d = p["data_fragment"].replace(":", "")
    # Check if this is LED color data (90-byte Razer frame with cmd 0x0f:0x03)
    is_led = False
    if len(d) >= 180:
        cmd_class = int(d[12:14], 16)
        cmd_id = int(d[14:16], 16)
        if cmd_class == 0x0f and cmd_id == 0x03:
            is_led = True
    if not is_led:
        non_led.append(p)

print(f"Non-LED control transfers: {len(non_led)}")

print("\nAll non-LED control transfers:")
for p in sorted(non_led, key=lambda x: float(x["time"]) if x["time"] else 0):
    # Show ALL data fields
    data_display = ""
    if p["data_fragment"]:
        raw = p["data_fragment"].replace(":", "")
        data_display = f"frag={raw[:40]}"
        if len(raw) >= 180:
            cmd_class = int(raw[12:14], 16)
            cmd_id = int(raw[14:16], 16)
            data_size = int(raw[10:12], 16)
            payload = raw[16:176]
            b = [int(payload[j:j+2], 16) for j in range(0, min(data_size*2, 20), 2)]
            payload_hex = " ".join(f"{x:02x}" for x in b)
            data_display = f"RAZER 0x{cmd_class:02x}:0x{cmd_id:02x} size={data_size} [{payload_hex}]"
    elif p["control_data"]:
        data_display = f"ctrl_data={p['control_data'][:60]}"
    elif p["capdata"]:
        data_display = f"capdata={p['capdata'][:60]}"

    setup_info = ""
    if p["bRequest"]:
        setup_info = f" bReq={p['bRequest']} bmReq={p['bmRequestType']} wVal={p['wValue']} wIdx={p['wIndex']} wLen={p['wLength']}"

    print(f"  #{p['frame']:>7s} t={p['time']:>14s}s [{p['direction']}] "
          f"len={p['data_len']:>3s}{setup_info}  {data_display}")

# Step 2: Also check raw hex of frames around the time gaps where "Default" should be
# The 3 "Disabled" writes are at known times. "Default" should be between them.
print("\n" + "=" * 80)
print("  RAW HEX DUMPS around expected 'Default' actions")
print("=" * 80)

# Get timestamps of the 3 Disabled writes
disabled_times = []
for p in non_led:
    d = p["data_fragment"].replace(":", "")
    if len(d) >= 180:
        cmd_class = int(d[12:14], 16)
        cmd_id = int(d[14:16], 16)
        if cmd_class == 0x02 and cmd_id == 0x0c:
            disabled_times.append(float(p["time"]))
            print(f"  Disabled write at t={p['time']}s (frame #{p['frame']})")

if len(disabled_times) >= 2:
    for i in range(len(disabled_times) - 1):
        t_start = disabled_times[i]
        t_end = disabled_times[i + 1]
        print(f"\n  Between Disabled #{i+1} (t={t_start:.1f}s) and Disabled #{i+2} (t={t_end:.1f}s):")
        print(f"  Gap = {t_end - t_start:.1f}s - 'Default' should be in here")

        # Find ALL packets in this time window (not just control)
        gap_packets = []
        out2 = run([
            "-Y", f"usb.bus_id==2 && usb.device_address==3 && frame.time_relative>{t_start+0.5} && frame.time_relative<{t_end-0.5}",
            "-T", "fields",
            "-e", "frame.number", "-e", "frame.time_relative",
            "-e", "usb.src", "-e", "usb.dst",
            "-e", "usb.transfer_type", "-e", "usb.data_len",
            "-e", "usb.data_fragment",
            "-E", "separator=|"
        ])
        for line2 in out2.split("\n"):
            if not line2.strip():
                continue
            parts2 = line2.split("|")
            data_len = parts2[5].strip() if len(parts2) > 5 else "0"
            xfer_type = parts2[4].strip() if len(parts2) > 4 else ""
            data_frag = parts2[6].strip() if len(parts2) > 6 else ""
            d2 = data_frag.replace(":", "")

            # Skip LED data
            if len(d2) >= 180:
                cc = int(d2[12:14], 16)
                ci = int(d2[14:16], 16)
                if cc == 0x0f and ci == 0x03:
                    continue

            # Show anything with data
            if int(data_len) > 0:
                direction = "OUT" if "host" in parts2[2] else "IN"
                types = {"0x02": "CTRL", "0x01": "ISOC", "0x03": "INTR", "0x00": "BULK"}
                tname = types.get(xfer_type, xfer_type)
                print(f"    #{parts2[0].strip():>7s} t={parts2[1].strip():>14s}s [{direction}] "
                      f"{tname} len={data_len:>3s} data={d2[:60]}")
