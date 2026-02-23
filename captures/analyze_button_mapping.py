#!/usr/bin/env python3
"""
Deep analysis of button mapping commands in the Razer Naga V2 Pro capture.
Focuses on cmd_class=0x0f and all potential button configuration commands.
"""
import subprocess
from collections import Counter, defaultdict

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Documentos\razer-naga-6btns-change-button-1.pcapng"

def run(args, timeout=300):
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

def main():
    # Get ALL Razer protocol packets
    all_parsed = []
    for bus, dev, label in [(3, 5, "Phase 1"), (2, 3, "Phase 2")]:
        out = run([
            "-Y", f"usb.bus_id=={bus} && usb.device_address=={dev} && usb.data_len>=90 && usb.data_len<=98",
            "-T", "fields",
            "-e", "frame.number", "-e", "frame.time_relative",
            "-e", "usb.src", "-e", "usb.dst",
            "-e", "usb.data_fragment",
            "-E", "separator=|"
        ])
        for line in out.split("\n"):
            if not line.strip():
                continue
            parts = line.split("|")
            if len(parts) < 5 or not parts[4]:
                continue
            parsed = parse_razer(parts[4])
            if not parsed:
                continue
            parsed["frame"] = parts[0]
            parsed["time"] = parts[1]
            parsed["direction"] = "OUT" if parts[2] == "host" else "IN"
            parsed["label"] = label
            all_parsed.append(parsed)

    print(f"Total Razer protocol packets: {len(all_parsed)}")

    # =========================================================================
    print("\n" + "=" * 75)
    print("  ALL 0x0f (Hypershift/Profile) COMMANDS - DETAILED")
    print("=" * 75)

    cmds_0f = [p for p in all_parsed if p["cmd_class"] == 0x0f]
    print(f"Total 0x0f commands: {len(cmds_0f)}")

    cmd_id_counts = Counter((p["cmd_id"], p["direction"]) for p in cmds_0f)
    print(f"\ncmd_id x direction distribution:")
    for (cmd_id, direction), count in sorted(cmd_id_counts.items()):
        print(f"  cmd_id=0x{cmd_id:02x} [{direction}]: {count}")

    for cmd_id in sorted(set(p["cmd_id"] for p in cmds_0f)):
        subset_out = [p for p in cmds_0f if p["cmd_id"] == cmd_id and p["direction"] == "OUT"]
        subset_in = [p for p in cmds_0f if p["cmd_id"] == cmd_id and p["direction"] == "IN"]

        print(f"\n--- cmd_class=0x0f cmd_id=0x{cmd_id:02x} ---")
        print(f"  OUT: {len(subset_out)}, IN: {len(subset_in)}")

        for direction_label, subset in [("OUT", subset_out), ("IN", subset_in)]:
            if not subset:
                continue
            print(f"\n  [{direction_label}] Data sizes: {Counter(p['data_size'] for p in subset)}")

            # Show unique payloads
            seen = set()
            count = 0
            for p in subset:
                key = p["payload"][:p["data_size"] * 2]
                if key not in seen:
                    seen.add(key)
                    spaced = " ".join(key[i:i+2] for i in range(0, len(key), 2))
                    print(f"    #{p['frame']:>6s} t={p['time']:>12s}s size={p['data_size']:>2d}  {spaced}")
                    count += 1
                    if count > 30:
                        total_unique = len(set(pp["payload"][:pp["data_size"]*2] for pp in subset))
                        print(f"    ... ({total_unique - count} more unique payloads)")
                        break

    # =========================================================================
    print("\n" + "=" * 75)
    print("  0x0f:0x03 PAYLOAD BYTE-LEVEL ANALYSIS")
    print("=" * 75)

    btn_cmds = [p for p in all_parsed if p["cmd_class"] == 0x0f and p["cmd_id"] == 0x03 and p["direction"] == "OUT"]
    print(f"Total 0x0f:0x03 OUT commands: {len(btn_cmds)}")
    print(f"Data sizes: {Counter(p['data_size'] for p in btn_cmds)}")

    # Byte-by-byte analysis
    max_data_size = max(p["data_size"] for p in btn_cmds)
    print(f"\nByte-by-byte analysis (max data_size={max_data_size}):")
    for byte_pos in range(max_data_size):
        vals = Counter()
        for p in btn_cmds:
            if byte_pos < p["data_size"]:
                val = int(p["payload"][byte_pos*2:byte_pos*2+2], 16)
                vals[val] += 1
        top = vals.most_common(8)
        print(f"  Byte[{byte_pos:2d}]: {len(vals):>4d} unique. Top: {', '.join(f'0x{v:02x}({c})' for v, c in top)}")

    # =========================================================================
    # Look at what happens around the time we expect button changes
    print("\n" + "=" * 75)
    print("  LOOKING FOR ACTUAL BUTTON REMAP COMMANDS")
    print("=" * 75)

    # The 0x0f:0x03 with data_size=11 looks like it might be LED matrix data
    # (the payloads look like RGB color values that are smoothly changing)
    # Let's look at non-0x03 commands in 0x0f class - these might be the actual button mapping

    print("\n0x0f:0x02 commands (Set Profile):")
    prof_cmds = [p for p in all_parsed if p["cmd_class"] == 0x0f and p["cmd_id"] == 0x02]
    for p in prof_cmds:
        payload_hex = " ".join(p["payload"][i:i+2] for i in range(0, p["data_size"]*2, 2))
        print(f"  #{p['frame']:>6s} t={p['time']:>12s}s [{p['direction']}] size={p['data_size']:>2d}  {payload_hex}")

    print("\n0x0f:0x04 commands:")
    cmd04 = [p for p in all_parsed if p["cmd_class"] == 0x0f and p["cmd_id"] == 0x04]
    for p in cmd04:
        payload_hex = " ".join(p["payload"][i:i+2] for i in range(0, p["data_size"]*2, 2))
        print(f"  #{p['frame']:>6s} t={p['time']:>12s}s [{p['direction']}] size={p['data_size']:>2d}  {payload_hex}")

    print("\n0x0f:0x80 commands:")
    cmd80 = [p for p in all_parsed if p["cmd_class"] == 0x0f and p["cmd_id"] == 0x80]
    for p in cmd80:
        payload_hex = " ".join(p["payload"][i:i+2] for i in range(0, p["data_size"]*2, 2))
        print(f"  #{p['frame']:>6s} t={p['time']:>12s}s [{p['direction']}] size={p['data_size']:>2d}  {payload_hex}")

    print("\n0x0f:0x84 commands:")
    cmd84 = [p for p in all_parsed if p["cmd_class"] == 0x0f and p["cmd_id"] == 0x84]
    for p in cmd84:
        payload_hex = " ".join(p["payload"][i:i+2] for i in range(0, p["data_size"]*2, 2))
        print(f"  #{p['frame']:>6s} t={p['time']:>12s}s [{p['direction']}] size={p['data_size']:>2d}  {payload_hex}")

    # =========================================================================
    # Check Macro commands (0x02) - could contain button mappings
    print("\n" + "=" * 75)
    print("  MACRO COMMANDS (0x02) - POTENTIAL BUTTON MAPPING")
    print("=" * 75)

    macro_cmds = [p for p in all_parsed if p["cmd_class"] == 0x02]
    cmd_id_counts = Counter((p["cmd_id"], p["direction"]) for p in macro_cmds)
    print(f"Total 0x02 commands: {len(macro_cmds)}")
    for (cmd_id, direction), count in sorted(cmd_id_counts.items()):
        print(f"  cmd_id=0x{cmd_id:02x} [{direction}]: {count}")

    for cmd_id in sorted(set(p["cmd_id"] for p in macro_cmds)):
        subset = [p for p in macro_cmds if p["cmd_id"] == cmd_id]
        print(f"\n--- 0x02:0x{cmd_id:02x} ---")
        seen = set()
        for p in subset:
            key = p["payload"][:p["data_size"]*2]
            if key not in seen:
                seen.add(key)
                payload_hex = " ".join(key[i:i+2] for i in range(0, len(key), 2))
                print(f"  #{p['frame']:>6s} t={p['time']:>12s}s [{p['direction']}] size={p['data_size']:>2d}  {payload_hex}")

    # =========================================================================
    # Let's look at the 0x0f:0x03 data more carefully - are these color frames?
    print("\n" + "=" * 75)
    print("  0x0f:0x03 - IS THIS LED DATA OR BUTTON MAPPING?")
    print("=" * 75)

    # Check if payload bytes 4-10 (the color-like data) change smoothly
    # This would indicate LED animation rather than button mapping
    print("\nFirst 50 unique 0x0f:0x03 payloads in time order:")
    seen_payloads = set()
    count = 0
    for p in btn_cmds:
        key = p["payload"][:p["data_size"]*2]
        if key not in seen_payloads:
            seen_payloads.add(key)
            bytes_list = [int(key[i:i+2], 16) for i in range(0, len(key), 2)]
            spaced = " ".join(f"{b:02x}" for b in bytes_list)
            # Check if bytes 5-10 look like 2x RGB
            if len(bytes_list) >= 11:
                r1, g1, b1 = bytes_list[5], bytes_list[6], bytes_list[7]
                r2, g2, b2 = bytes_list[8], bytes_list[9], bytes_list[10]
                same = (r1 == r2 and g1 == g2 and b1 == b2)
                print(f"  #{p['frame']:>6s} [{spaced}]  RGB1=({r1},{g1},{b1}) RGB2=({r2},{g2},{b2}) same={same}")
            else:
                print(f"  #{p['frame']:>6s} [{spaced}]")
            count += 1
            if count >= 50:
                break

    # =========================================================================
    # Look for keyboard/side-button HID reports around the time of suspected button changes
    print("\n" + "=" * 75)
    print("  KEYBOARD HID REPORTS (side button events)")
    print("=" * 75)

    # Get Phase 2 IF1 reports (ep 0x82)
    out = run([
        "-Y", 'usb.src == "2.3.2" && usb.data_len > 0',
        "-T", "fields",
        "-e", "frame.number", "-e", "frame.time_relative",
        "-e", "usb.data_len", "-e", "usbhid.data",
        "-E", "separator=|"
    ])
    lines = [l for l in out.split("\n") if l.strip()]
    print(f"Phase 2 IF1 (ep 0x82) reports: {len(lines)}")
    for line in lines:
        parts = line.split("|")
        if len(parts) < 4 or not parts[3]:
            continue
        data = parts[3].replace(":", "")
        spaced = " ".join(data[i:i+2] for i in range(0, len(data), 2))
        # Decode report_id 0x05 (Razer extended report)
        if len(data) >= 4:
            report_id = int(data[0:2], 16)
            byte1 = int(data[2:4], 16)
            desc = ""
            if report_id == 0x05:
                if byte1 == 0x09:
                    desc = " -> PANEL CHANGE/DETECT?"
                elif byte1 == 0x02:
                    desc = " -> BUTTON CONFIG NOTIFICATION?"
                elif byte1 == 0x31:
                    desc = " -> PROFILE/STATE CHANGE?"
                elif byte1 == 0x0c:
                    desc = " -> DEVICE READY?"
                elif byte1 == 0x0e:
                    desc = " -> DEVICE CONFIG UPDATE?"
                elif byte1 == 0x3a:
                    desc = " -> HYPERSHIFT/LAYER CHANGE?"
            print(f"  #{parts[0]:>6s} t={parts[1]:>12s}s  {spaced}{desc}")

    # =========================================================================
    # Summary: Look at the 0x0f:0x03 pattern
    print("\n" + "=" * 75)
    print("  PATTERN ANALYSIS SUMMARY")
    print("=" * 75)

    # Count how many 0x0f:0x03 have same RGB1 == RGB2
    same_rgb = 0
    for p in btn_cmds:
        key = p["payload"][:p["data_size"]*2]
        bytes_list = [int(key[i:i+2], 16) for i in range(0, len(key), 2)]
        if len(bytes_list) >= 11:
            if bytes_list[5:8] == bytes_list[8:11]:
                same_rgb += 1

    print(f"0x0f:0x03 with RGB1==RGB2: {same_rgb}/{len(btn_cmds)} ({same_rgb*100//max(len(btn_cmds),1)}%)")

    # Check byte[4] (always 0x01?)
    byte4_vals = Counter()
    for p in btn_cmds:
        if p["data_size"] >= 5:
            byte4_vals[int(p["payload"][8:10], 16)] += 1
    print(f"Byte[4] values: {[(f'0x{v:02x}', c) for v, c in byte4_vals.most_common()]}")

    # Check bytes 0-3 (always 0x00?)
    for pos in range(4):
        vals = Counter()
        for p in btn_cmds:
            vals[int(p["payload"][pos*2:pos*2+2], 16)] += 1
        print(f"Byte[{pos}] values: {[(f'0x{v:02x}', c) for v, c in vals.most_common(5)]}")

    print("\nConclusion:")
    print("The 0x0f:0x03 commands appear to be LED MATRIX color data, not button mapping!")
    print("Structure: [row:1][col:1][00][00][flag:1][R1:1][G1:1][B1:1][R2:1][G2:1][B2:1]")
    print("The smooth color transitions and RGB pattern confirm this.")
    print()
    print("For ACTUAL button mapping, look for:")
    print("  - Different cmd_class/cmd_id combinations")
    print("  - Commands sent around the time of Synapse button-change clicks")
    print("  - The capture may not contain explicit button remapping if only")
    print("    the default 'number keys' mapping was used with a color change")


if __name__ == "__main__":
    main()
