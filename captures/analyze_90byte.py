#!/usr/bin/env python3
"""Check the 11 packets with data_len=90 (GET_REPORT responses)."""
import subprocess

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Projects\razer-macos\captures\razer-naga-12btns-change-button-2.pcapng"

def run(args, timeout=600):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

# Try to find those 90-byte packets
out = run([
    "-Y", "usb.bus_id==2 && usb.device_address==3 && usb.transfer_type==0x02",
    "-T", "fields",
    "-e", "frame.number", "-e", "frame.time_relative",
    "-e", "usb.src", "-e", "usb.dst",
    "-e", "usb.data_len",
    "-e", "usb.data_fragment",
    "-E", "separator=|"
])

for line in out.split("\n"):
    if not line.strip():
        continue
    parts = line.split("|")
    if len(parts) < 6:
        continue
    frame = parts[0].strip()
    time = parts[1].strip()
    src = parts[2].strip()
    dst = parts[3].strip()
    data_len = parts[4].strip()
    data_frag = parts[5].strip() if len(parts) > 5 else ""

    d = data_frag.replace(":", "")

    # Show non-98-byte control transfers
    if data_len != "98" and data_len != "0":
        direction = "OUT" if "host" in src else "IN"
        # Parse if Razer-sized
        if len(d) >= 180:
            cmd_class = int(d[12:14], 16)
            cmd_id = int(d[14:16], 16)
            data_size = int(d[10:12], 16)
            status = int(d[0:2], 16)
            payload = d[16:176]
            b = [int(payload[j:j+2], 16) for j in range(0, min(data_size*2, 20), 2)]
            payload_hex = " ".join(f"{x:02x}" for x in b)
            status_names = {0: "NEW", 2: "BUSY", 3: "OK", 4: "FAIL", 5: "TIMEOUT"}
            sn = status_names.get(status, f"0x{status:02x}")
            print(f"  #{frame:>7s} t={time:>14s}s [{direction}] len={data_len:>3s} "
                  f"0x{cmd_class:02x}:0x{cmd_id:02x} status={sn:<7s} size={data_size}  [{payload_hex}]")
        else:
            print(f"  #{frame:>7s} t={time:>14s}s [{direction}] len={data_len:>3s} data={data_frag[:60]}")
