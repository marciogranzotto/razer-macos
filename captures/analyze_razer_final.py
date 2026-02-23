#!/usr/bin/env python3
"""
Razer Naga V2 Pro - Final Comprehensive Analysis
Analyzes razer-naga-6btns-change-button-1.pcapng
"""

import subprocess
import os
from collections import Counter, defaultdict

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Documentos\razer-naga-6btns-change-button-1.pcapng"

CMD_CLASS_NAMES = {
    0x00: "General", 0x01: "Device Mode", 0x02: "Macro",
    0x03: "Lighting/LED", 0x04: "Keyboard Layout", 0x05: "Mouse Config",
    0x06: "Keypad", 0x07: "Custom Effects", 0x08: "Profile",
    0x09: "DPI", 0x0b: "Wireless/Dongle", 0x0d: "Button Mapping",
    0x0f: "Hypershift/Profile", 0x15: "Extended Config",
}

def run(args, timeout=300):
    cmd = [TSHARK, "-r", PCAP] + args
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, errors='replace')
    return r.stdout.strip()

def section(t):
    print(f"\n{'='*75}\n  {t}\n{'='*75}")

def sub(t):
    print(f"\n--- {t} ---")

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

def main():
    print("*" * 75)
    print("  RAZER NAGA V2 PRO - COMPREHENSIVE USB CAPTURE ANALYSIS")
    print(f"  File: {os.path.basename(PCAP)}")
    print("*" * 75)

    # =========================================================================
    section("1. CAPTURE OVERVIEW")
    # =========================================================================
    out = run(["-q", "-z", "io,stat,0"])
    for line in out.split("\n"):
        if "|" in line or "Duration" in line:
            print(f"  {line.strip()}")

    print(f"\n  Total USB devices detected:")
    out = run(["-Y", "usb.idVendor", "-T", "fields",
               "-e", "usb.idVendor", "-e", "usb.idProduct", "-e", "usb.src",
               "-E", "separator=|"])

    vendors = {
        "0x1532": "Razer Inc.", "0x05e3": "Genesys Logic",
        "0x2109": "VIA Labs (Hub)", "0x0bc2": "Seagate",
        "0x1e71": "NZXT", "0x0e8d": "MediaTek",
        "0x26ce": "LED Controller", "0x1a86": "QinHeng (CH340)",
        "0x0cf2": "ENE Technology", "0x10c4": "Silicon Labs",
        "0x1a40": "Terminus (Hub)", "0x2e1a": "Unknown",
        "0x3434": "Unknown (Hub)",
    }

    devices = {}
    for line in out.split("\n"):
        if not line.strip(): continue
        parts = line.split("|")
        if len(parts) >= 3:
            k = f"{parts[0]}:{parts[1]}"
            if k not in devices:
                devices[k] = {"vid": parts[0], "pid": parts[1], "addrs": set()}
            devices[k]["addrs"].add(parts[2])

    for k, d in sorted(devices.items()):
        v = vendors.get(d["vid"], "Unknown")
        marker = " <<<< RAZER NAGA V2 PRO" if d["vid"] == "0x1532" else ""
        print(f"  {k:<16} {v:<25} {', '.join(sorted(d['addrs']))}{marker}")

    # =========================================================================
    section("2. RAZER DEVICE IDENTIFICATION")
    # =========================================================================
    print("  Vendor ID:   0x1532 (Razer Inc.)")
    print("  Product ID:  0x00a8 (Razer Naga V2 Pro - Wireless Dongle)")
    print("  USB Version: 2.0")
    print("  Device Version: 1.0")
    print()
    print("  Bus Addresses:")
    print("    Phase 1: Bus 3, Device 5 (address 3.5.x) - Frames 124 to ~126000")
    print("    Phase 2: Bus 2, Device 3 (address 2.3.x) - Frames 126454 to ~221000")
    print("    (Device was re-enumerated mid-capture)")
    print()
    print("  Interface Configuration (3 HID interfaces):")
    print("    IF0: HID Boot Mouse     (ep 0x81) - Standard mouse reports")
    print("    IF1: HID Boot Keyboard  (ep 0x82) - Side button reports")
    print("    IF2: HID Boot Keyboard  (ep 0x83) - Additional button reports")

    # =========================================================================
    section("3. TRAFFIC VOLUME")
    # =========================================================================
    for bus, dev, label, trange in [
        (3, 5, "Phase 1", "2.6s - 145.1s"),
        (2, 3, "Phase 2", "161.1s - 241.7s")
    ]:
        sub(f"Bus {bus} Dev {dev} ({label}) [{trange}]")
        out = run(["-Y", f"usb.bus_id=={bus} && usb.device_address=={dev}",
                   "-T", "fields", "-e", "usb.endpoint_address", "-e", "usb.transfer_type",
                   "-E", "separator=|"])
        lines = [l for l in out.split("\n") if l.strip()]
        print(f"  Total packets: {len(lines)}")

        ep_counts = Counter()
        tt_counts = Counter()
        for l in lines:
            p = l.split("|")
            if len(p) >= 2:
                ep_counts[p[0]] += 1
                tt_counts[p[1]] += 1

        type_names = {"0x00": "Isochronous", "0x01": "Interrupt", "0x02": "Control", "0x03": "Bulk"}
        print("  Transfer types:")
        for t, c in tt_counts.most_common():
            print(f"    {type_names.get(t, t)}: {c}")
        print("  Endpoints:")
        for e, c in ep_counts.most_common(6):
            print(f"    {e}: {c}")

    # =========================================================================
    section("4. RAZER PROTOCOL ANALYSIS (90-byte Feature Reports)")
    # =========================================================================
    print("  Razer protocol: 90-byte HID Feature Reports sent via SET_REPORT/GET_REPORT")
    print("  Structure: [status:1][trans_id:1][remaining:2][proto_type:1]")
    print("             [data_size:1][cmd_class:1][cmd_id:1][params:80][crc:1][end:1]")

    all_parsed = []

    for bus, dev, label in [(3, 5, "Phase 1"), (2, 3, "Phase 2")]:
        sub(f"Razer Commands - {label} (bus {bus} dev {dev})")
        out = run([
            "-Y", f"usb.bus_id=={bus} && usb.device_address=={dev} && usb.data_len>=90 && usb.data_len<=98",
            "-T", "fields",
            "-e", "frame.number", "-e", "frame.time_relative",
            "-e", "usb.src", "-e", "usb.dst",
            "-e", "usb.data_fragment",
            "-E", "separator=|"
        ])

        lines = [l for l in out.split("\n") if l.strip()]
        print(f"  Total protocol packets: {len(lines)}")

        out_cmds = Counter()
        in_cmds = Counter()

        for line in lines:
            parts = line.split("|")
            if len(parts) < 5 or not parts[4]:
                continue
            frame, time_rel, src, dst = parts[0], parts[1], parts[2], parts[3]
            direction = "OUT" if src == "host" else "IN"
            parsed = parse_razer(parts[4])
            if not parsed:
                continue
            parsed["frame"] = frame
            parsed["time"] = time_rel
            parsed["direction"] = direction
            parsed["label"] = label

            if direction == "OUT":
                out_cmds[(parsed["cmd_class"], parsed["cmd_id"])] += 1
            else:
                in_cmds[(parsed["cmd_class"], parsed["cmd_id"])] += 1
            all_parsed.append(parsed)

        print(f"\n  HOST -> DEVICE Commands:")
        print(f"  {'Class':>6s} {'CmdID':>6s} {'Count':>7s}  {'Class Name':<22s}")
        print(f"  {'-'*6} {'-'*6} {'-'*7}  {'-'*22}")
        for (cls, cmd), count in sorted(out_cmds.items()):
            cn = CMD_CLASS_NAMES.get(cls, f"0x{cls:02x}")
            print(f"  0x{cls:02x}   0x{cmd:02x}   {count:>7d}  {cn}")

        if in_cmds:
            print(f"\n  DEVICE -> HOST Responses:")
            for (cls, cmd), count in sorted(in_cmds.items()):
                cn = CMD_CLASS_NAMES.get(cls, f"0x{cls:02x}")
                print(f"  0x{cls:02x}   0x{cmd:02x}   {count:>7d}  {cn}")

    # =========================================================================
    section("5. BUTTON MAPPING COMMANDS (cmd_class=0x0f, cmd_id=0x03)")
    # =========================================================================
    btn_map = [p for p in all_parsed if p["cmd_class"] == 0x0f and p["cmd_id"] == 0x03]
    print(f"  Total Hypershift/Button Mapping packets: {len(btn_map)}")
    print(f"  These are the primary commands for configuring button mappings.")
    print()

    # Show distinct payload patterns
    payload_patterns = Counter()
    for p in btn_map:
        if p["direction"] == "OUT":
            meaningful = p["payload"][:p["data_size"] * 2]
            payload_patterns[meaningful] += 1

    print(f"  Unique button mapping payloads: {len(payload_patterns)}")
    print(f"\n  Top 30 most common payloads (first {btn_map[0]['data_size'] if btn_map else 0} bytes):")
    for pat, count in payload_patterns.most_common(30):
        spaced = " ".join(pat[i:i+2] for i in range(0, len(pat), 2))
        print(f"    {spaced}  (x{count})")

    # Show first 20 and last 20 unique payloads chronologically
    print(f"\n  First 10 button config packets:")
    for p in btn_map[:10]:
        payload_hex = " ".join(p["payload"][i:i+2] for i in range(0, p["data_size"]*2, 2))
        print(f"    #{p['frame']:>6s} t={p['time']:>12s}s [{p['direction']}] {payload_hex}")

    print(f"\n  Last 10 button config packets:")
    for p in btn_map[-10:]:
        payload_hex = " ".join(p["payload"][i:i+2] for i in range(0, p["data_size"]*2, 2))
        print(f"    #{p['frame']:>6s} t={p['time']:>12s}s [{p['direction']}] {payload_hex}")

    # =========================================================================
    section("6. CONFIGURATION ACTIVITY TIMELINE")
    # =========================================================================
    set_ops = [p for p in all_parsed if p["direction"] == "OUT"]
    bursts = []
    if set_ops:
        current = [set_ops[0]]
        for i in range(1, len(set_ops)):
            try:
                if float(set_ops[i]["time"]) - float(set_ops[i-1]["time"]) > 1.0:
                    bursts.append(current)
                    current = [set_ops[i]]
                else:
                    current.append(set_ops[i])
            except:
                current.append(set_ops[i])
        bursts.append(current)

    print(f"  Total SET operations: {len(set_ops)}")
    print(f"  Configuration bursts (gap > 1s): {len(bursts)}")

    for i, burst in enumerate(bursts):
        t_start = burst[0]["time"]
        t_end = burst[-1]["time"]
        burst_cmds = Counter()
        for p in burst:
            cn = CMD_CLASS_NAMES.get(p["cmd_class"], f"0x{p['cmd_class']:02x}")
            burst_cmds[cn] += 1

        print(f"\n  Burst {i+1}: t={t_start}s - {t_end}s ({len(burst)} pkts)")
        for name, count in burst_cmds.most_common(5):
            print(f"    {name}: {count}x")

    # =========================================================================
    section("7. MOUSE HID REPORTS (Endpoint 0x81)")
    # =========================================================================
    print("  Format: [buttons:1][pad:1][pad:1][pan:1][wheel:1][X:2][Y:2] = 8 bytes")

    for src_addr, label in [("3.5.1", "Phase 1"), ("2.3.1", "Phase 2")]:
        sub(f"Mouse Reports - {label} ({src_addr})")
        out = run([
            "-Y", f'usb.src == "{src_addr}"',
            "-T", "fields",
            "-e", "frame.number", "-e", "frame.time_relative",
            "-e", "usb.data_len", "-e", "usbhid.data",
            "-E", "separator=|"
        ])
        lines = [l for l in out.split("\n") if l.strip()]
        print(f"  Total mouse reports: {len(lines)}")

        button_changes = []
        prev_btn = None
        btn_counts = Counter()

        for line in lines:
            parts = line.split("|")
            if len(parts) < 4 or not parts[3]:
                continue
            data = parts[3].replace(":", "")
            if len(data) < 2:
                continue
            btn_byte = int(data[0:2], 16)
            btn_counts[btn_byte] += 1

            if btn_byte != prev_btn:
                pressed = []
                if btn_byte & 0x01: pressed.append("Left")
                if btn_byte & 0x02: pressed.append("Right")
                if btn_byte & 0x04: pressed.append("Middle")
                if btn_byte & 0x08: pressed.append("Back(4)")
                if btn_byte & 0x10: pressed.append("Forward(5)")
                for b in range(5, 8):
                    if btn_byte & (1 << b):
                        pressed.append(f"Btn{b+1}")
                button_changes.append({
                    "frame": parts[0], "time": parts[1],
                    "btn": btn_byte, "pressed": pressed
                })
                prev_btn = btn_byte

        if btn_counts:
            print(f"\n  Button byte value distribution:")
            for btn, count in btn_counts.most_common(10):
                label_str = "None(movement)" if btn == 0 else ""
                if btn & 0x01: label_str = "Left"
                print(f"    0x{btn:02x} ({btn:08b}): {count:>6d} reports  {label_str}")

        if button_changes:
            print(f"\n  Button state changes: {len(button_changes)}")
            print(f"  Button press/release events:")
            for evt in button_changes[:30]:
                btns = ", ".join(evt["pressed"]) if evt["pressed"] else "RELEASE"
                print(f"    #{evt['frame']:>6s} t={evt['time']:>12s}s "
                      f"0x{evt['btn']:02x} [{btns}]")
            if len(button_changes) > 30:
                print(f"    ... ({len(button_changes) - 30} more state changes)")

    # =========================================================================
    section("8. KEYBOARD/SIDE-BUTTON HID REPORTS")
    # =========================================================================
    print("  Side buttons on the Razer Naga are reported as keyboard HID events")
    print("  on IF1 (ep 0x82) and IF2 (ep 0x83)")

    for src_addr, label in [
        ("3.5.2", "Phase 1 IF1"), ("3.5.3", "Phase 1 IF2"),
        ("2.3.2", "Phase 2 IF1"), ("2.3.3", "Phase 2 IF2"),
    ]:
        sub(f"Keyboard Reports - {label} ({src_addr})")
        out = run([
            "-Y", f'usb.src == "{src_addr}" && usb.data_len > 0',
            "-T", "fields",
            "-e", "frame.number", "-e", "frame.time_relative",
            "-e", "usb.data_len", "-e", "usbhid.data",
            "-E", "separator=|"
        ])
        lines = [l for l in out.split("\n") if l.strip()]
        print(f"  Reports: {len(lines)}")

        for line in lines[:30]:
            parts = line.split("|")
            data = parts[3].replace(":", "") if len(parts) > 3 else ""
            frame = parts[0] if parts else "?"
            t = parts[1] if len(parts) > 1 else "?"
            if data:
                spaced = " ".join(data[i:i+2] for i in range(0, len(data), 2))
                # Parse keyboard report: [report_id][modifier][reserved][key1][key2]...
                desc = ""
                if len(data) >= 6:
                    report_id = int(data[0:2], 16)
                    modifier_or_key = int(data[2:4], 16)
                    desc = f" (report_id=0x{report_id:02x})"
                print(f"    #{frame:>6s} t={t:>12s}s  {spaced}{desc}")
            else:
                print(f"    #{frame:>6s} t={t:>12s}s  (no data)")

    # =========================================================================
    section("9. NON-BUTTON-MAPPING COMMANDS (Phase 2 initialization)")
    # =========================================================================
    print("  Phase 2 contains device initialization commands beyond button mapping.")
    phase2_init = [p for p in all_parsed
                   if p["label"] == "Phase 2" and p["direction"] == "OUT"
                   and not (p["cmd_class"] == 0x0f and p["cmd_id"] == 0x03)]

    cmd_summary = Counter()
    for p in phase2_init:
        cn = CMD_CLASS_NAMES.get(p["cmd_class"], f"0x{p['cmd_class']:02x}")
        cmd_summary[(cn, f"0x{p['cmd_class']:02x}", f"0x{p['cmd_id']:02x}")] += 1

    print(f"  Non-button-mapping commands in Phase 2: {len(phase2_init)}")
    print(f"\n  {'Class Name':<22s} {'Class':>6s} {'CmdID':>6s} {'Count':>7s}")
    print(f"  {'-'*22} {'-'*6} {'-'*6} {'-'*7}")
    for (cn, cls, cmd), count in sorted(cmd_summary.items()):
        print(f"  {cn:<22s} {cls:>6s} {cmd:>6s} {count:>7d}")

    # Show details of key initialization commands
    print(f"\n  Sample initialization commands:")
    for p in phase2_init[:20]:
        cn = CMD_CLASS_NAMES.get(p["cmd_class"], f"0x{p['cmd_class']:02x}")
        payload_hex = " ".join(p["payload"][i:i+2] for i in range(0, min(p["data_size"]*2, 40), 2))
        print(f"    #{p['frame']:>6s} {cn:<18s} cls=0x{p['cmd_class']:02x} cmd=0x{p['cmd_id']:02x} "
              f"size={p['data_size']:>2d} data={payload_hex}")

    # =========================================================================
    section("10. SUMMARY")
    # =========================================================================
    total_razer = len(all_parsed)
    btn_map_count = len(btn_map)
    other_count = total_razer - btn_map_count

    print(f"  Device:           Razer Naga V2 Pro (Wireless Dongle)")
    print(f"  VID:PID:          0x1532:0x00a8")
    print(f"  Capture Duration: ~241.7 seconds")
    print(f"  Total Packets:    221,920")
    print(f"")
    print(f"  Razer Protocol Packets:  {total_razer}")
    print(f"    Button Mapping (0x0f:0x03): {btn_map_count} ({btn_map_count*100//max(total_razer,1)}%)")
    print(f"    Other Commands:             {other_count}")
    print(f"")
    print(f"  Configuration Bursts:    {len(bursts)}")
    print(f"  Two enumeration phases (device re-enumerated at ~t=161s)")
    print(f"")
    print(f"  The capture is dominated by Hypershift/Profile button mapping commands")
    print(f"  (cmd_class=0x0f, cmd_id=0x03) which are being continuously sent to")
    print(f"  configure/update the 6-button side panel mappings on the Razer Naga V2 Pro.")
    print(f"")
    print(f"  Phase 2 additionally includes device initialization commands:")
    print(f"    - General device setup (0x00)")
    print(f"    - Macro configuration (0x02)")
    print(f"    - Keyboard layout (0x04)")
    print(f"    - Mouse config (0x05)")
    print(f"    - Custom effects/lighting (0x07)")
    print(f"    - Profile management (0x0f)")
    print(f"    - Extended config (0x15)")

if __name__ == "__main__":
    main()
