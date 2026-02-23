#!/usr/bin/env python3
"""
Razer Naga V2 Pro USB Capture Analyzer
Analyzes razer-naga-6btns-change-button-1.pcapng for Razer device traffic.
"""

import subprocess
import json
import sys
import os
from collections import Counter, defaultdict

TSHARK = r"C:\Program Files\Wireshark\tshark.exe"
PCAP = r"C:\Users\marci\OneDrive\Documentos\razer-naga-6btns-change-button-1.pcapng"

# Razer USB Vendor ID
RAZER_VID = "0x1532"
RAZER_PID = "0x00a8"

def run_tshark(args, timeout=120):
    """Run tshark with given arguments and return stdout."""
    cmd = [TSHARK, "-r", PCAP] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[TIMEOUT]"
    except Exception as e:
        return f"[ERROR: {e}]"

def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

def subsection(title):
    print(f"\n--- {title} ---")


def analyze_capture_overview():
    """General capture file statistics."""
    section("1. CAPTURE FILE OVERVIEW")

    # Total packets
    out = run_tshark(["-q", "-z", "io,stat,0"])
    for line in out.split("\n"):
        if "frames" in line.lower() or "duration" in line.lower() or "|" in line:
            print(f"  {line.strip()}")

    # Protocol hierarchy
    subsection("Protocol Hierarchy")
    out = run_tshark(["-q", "-z", "io,phs"])
    for line in out.split("\n"):
        if "frames:" in line:
            print(f"  {line.strip()}")


def analyze_all_usb_devices():
    """List all USB devices found in the capture."""
    section("2. ALL USB DEVICES IN CAPTURE")

    out = run_tshark([
        "-Y", "usb.idVendor",
        "-T", "fields",
        "-e", "usb.idVendor", "-e", "usb.idProduct",
        "-e", "usb.src",
        "-E", "separator=|"
    ])

    devices = {}
    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) >= 3:
            vid, pid = parts[0], parts[1]
            src = parts[2]
            key = f"{vid}:{pid}"
            if key not in devices:
                devices[key] = {"vid": vid, "pid": pid, "sources": set()}
            devices[key]["sources"].add(src)

    # Known vendor names
    vendor_names = {
        "0x1532": "Razer Inc.",
        "0x05e3": "Genesys Logic",
        "0x2109": "VIA Labs (USB Hub)",
        "0x0bc2": "Seagate",
        "0x1e71": "NZXT",
        "0x0e8d": "MediaTek",
        "0x26ce": "Unknown (LED Controller?)",
        "0x1a86": "QinHeng Electronics (CH340)",
        "0x0cf2": "ENE Technology",
        "0x10c4": "Silicon Labs (CP210x)",
        "0x1a40": "Terminus Technology (USB Hub)",
        "0x2e1a": "Unknown",
        "0x3434": "Unknown (USB Hub?)",
    }

    print(f"  {'VID:PID':<16} {'Vendor':<35} {'Bus Addresses'}")
    print(f"  {'-'*16} {'-'*35} {'-'*20}")
    for key, info in sorted(devices.items()):
        vid = info['vid']
        vendor = vendor_names.get(vid, "Unknown")
        marker = " <== RAZER NAGA" if vid == RAZER_VID else ""
        sources = ", ".join(sorted(info['sources']))
        print(f"  {key:<16} {vendor:<35} {sources}{marker}")


def analyze_razer_device_descriptor():
    """Detailed analysis of the Razer device descriptor."""
    section("3. RAZER NAGA V2 PRO - DEVICE DESCRIPTOR")

    # Get the device descriptor frame
    out = run_tshark([
        "-Y", f"usb.idVendor == {RAZER_VID}",
        "-T", "fields",
        "-e", "frame.number",
        "-e", "usb.src",
        "-e", "usb.idVendor",
        "-e", "usb.idProduct",
        "-e", "usb.bcdUSB",
        "-e", "usb.bcdDevice",
        "-e", "usb.bDeviceClass",
        "-e", "usb.bDeviceSubClass",
        "-e", "usb.bDeviceProtocol",
        "-e", "usb.bNumConfigurations",
        "-E", "separator=|"
    ])

    print(f"  Device: Razer Naga V2 Pro (Wireless Dongle)")
    print(f"  Vendor ID:  {RAZER_VID} (Razer Inc.)")
    print(f"  Product ID: {RAZER_PID}")
    print()

    for line in out.split("\n"):
        if not line.strip():
            continue
        parts = line.split("|")
        if len(parts) >= 6:
            frame, src, vid, pid, bcdusb, bcddev = parts[:6]
            print(f"  Frame #{frame}: Source={src}")
            print(f"    USB Version: {bcdusb}")
            print(f"    Device Version: {bcddev}")
            if len(parts) > 6:
                print(f"    Device Class: {parts[6]}")
            if len(parts) > 9:
                print(f"    Num Configurations: {parts[9]}")

    # Configuration descriptor
    subsection("Interface Configuration")
    # Frame 126 has the config descriptor
    frames_with_desc = []
    for line in out.split("\n"):
        if line.strip():
            frames_with_desc.append(line.split("|")[0])

    if frames_with_desc:
        first_frame = int(frames_with_desc[0])
        # The config descriptor is usually 2 frames after device descriptor
        config_out = run_tshark([
            "-Y", f"frame.number >= {first_frame} and frame.number <= {first_frame + 5}",
            "-T", "pdml"
        ])

        interfaces = []
        current_iface = {}
        for line in config_out.split("\n"):
            if "bInterfaceNumber" in line and "showname" in line:
                if current_iface:
                    interfaces.append(current_iface)
                current_iface = {}
                # Extract value
                start = line.find('show="') + 6
                end = line.find('"', start)
                current_iface["number"] = line[start:end]
            elif "bInterfaceClass" in line and "showname" in line:
                start = line.find('showname="') + 10
                end = line.find('"', start)
                current_iface["class"] = line[start:end]
            elif "bInterfaceSubClass" in line and "showname" in line:
                start = line.find('showname="') + 10
                end = line.find('"', start)
                current_iface["subclass"] = line[start:end]
            elif "bInterfaceProtocol" in line and "showname" in line:
                start = line.find('showname="') + 10
                end = line.find('"', start)
                current_iface["protocol"] = line[start:end]
            elif "bNumEndpoints" in line and "showname" in line:
                start = line.find('showname="') + 10
                end = line.find('"', start)
                current_iface["endpoints"] = line[start:end]
        if current_iface:
            interfaces.append(current_iface)

        # Remove duplicates
        seen = set()
        unique_ifaces = []
        for iface in interfaces:
            key = iface.get("number", "")
            if key not in seen:
                seen.add(key)
                unique_ifaces.append(iface)

        for iface in unique_ifaces:
            print(f"\n  Interface {iface.get('number', '?')}:")
            print(f"    Class:    {iface.get('class', 'N/A')}")
            print(f"    SubClass: {iface.get('subclass', 'N/A')}")
            print(f"    Protocol: {iface.get('protocol', 'N/A')}")
            print(f"    Endpoints: {iface.get('endpoints', 'N/A')}")


def analyze_razer_traffic_volume():
    """Analyze traffic volume and timing for Razer device."""
    section("4. RAZER DEVICE TRAFFIC ANALYSIS")

    for bus_id, dev_addr, label in [(3, 5, "First enumeration"), (2, 3, "Second enumeration")]:
        subsection(f"Bus {bus_id}, Device {dev_addr} ({label})")

        # Total packets
        out = run_tshark([
            "-Y", f"usb.bus_id == {bus_id} && usb.device_address == {dev_addr}",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "frame.time_relative",
            "-e", "usb.endpoint_address",
            "-e", "usb.transfer_type",
            "-e", "usb.data_len",
            "-E", "separator=|"
        ], timeout=180)

        lines = [l for l in out.split("\n") if l.strip()]
        total = len(lines)
        print(f"  Total packets: {total}")

        if total == 0:
            continue

        # Time range
        times = []
        endpoints = Counter()
        transfer_types = Counter()
        data_lens = []

        for line in lines:
            parts = line.split("|")
            if len(parts) >= 5:
                try:
                    times.append(float(parts[1]))
                except:
                    pass
                endpoints[parts[2]] += 1
                transfer_types[parts[3]] += 1
                try:
                    data_lens.append(int(parts[4]))
                except:
                    pass

        if times:
            print(f"  Time range: {min(times):.3f}s - {max(times):.3f}s (duration: {max(times)-min(times):.3f}s)")

        print(f"\n  Transfer Types:")
        type_names = {"0x00": "Isochronous", "0x01": "Interrupt", "0x02": "Control", "0x03": "Bulk"}
        for tt, count in transfer_types.most_common():
            name = type_names.get(tt, tt)
            print(f"    {name}: {count} packets")

        print(f"\n  Endpoints (top 10):")
        for ep, count in endpoints.most_common(10):
            print(f"    Endpoint {ep}: {count} packets")

        if data_lens:
            total_bytes = sum(data_lens)
            print(f"\n  Data volume: {total_bytes:,} bytes ({total_bytes/1024:.1f} KB)")


def analyze_razer_hid_reports():
    """Analyze HID reports from the Razer device (mouse/keyboard data)."""
    section("5. RAZER HID REPORT ANALYSIS")

    # Look for HID data on both Razer bus addresses
    for bus_id, dev_addr, label in [(3, 5, "First"), (2, 3, "Second")]:
        subsection(f"HID Reports - Bus {bus_id} Dev {dev_addr} ({label})")

        # Get interrupt IN transfers (HID reports from device to host)
        out = run_tshark([
            "-Y", f"usb.bus_id == {bus_id} && usb.device_address == {dev_addr} && usb.transfer_type == 0x01",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "frame.time_relative",
            "-e", "usb.endpoint_address",
            "-e", "usb.data_len",
            "-e", "usb.capdata",
            "-E", "separator=|",
            "-c", "500"
        ], timeout=120)

        lines = [l for l in out.split("\n") if l.strip()]
        print(f"  Interrupt transfer packets (first 500): {len(lines)}")

        if not lines:
            # Try URB interrupt
            out = run_tshark([
                "-Y", f"usb.bus_id == {bus_id} && usb.device_address == {dev_addr} && usb.endpoint_address == 0x81",
                "-T", "fields",
                "-e", "frame.number",
                "-e", "frame.time_relative",
                "-e", "usb.endpoint_address",
                "-e", "usb.data_len",
                "-e", "usb.capdata",
                "-E", "separator=|",
                "-c", "200"
            ], timeout=120)
            lines = [l for l in out.split("\n") if l.strip()]
            print(f"  Endpoint 0x81 packets (first 200): {len(lines)}")

        # Analyze data patterns
        if lines:
            data_patterns = Counter()
            for line in lines[:200]:
                parts = line.split("|")
                if len(parts) >= 5 and parts[4]:
                    data = parts[4]
                    # First few bytes often indicate report type
                    prefix = data[:11]  # first 4 bytes as hex
                    data_patterns[prefix] += 1

            if data_patterns:
                print(f"\n  Data prefix patterns (first 4 bytes):")
                for pattern, count in data_patterns.most_common(15):
                    print(f"    {pattern}: {count} occurrences")


def analyze_razer_control_transfers():
    """Analyze control transfers (configuration commands) to the Razer device."""
    section("6. RAZER CONTROL TRANSFER ANALYSIS (Configuration Commands)")

    for bus_id, dev_addr, label in [(3, 5, "First"), (2, 3, "Second")]:
        subsection(f"Control Transfers - Bus {bus_id} Dev {dev_addr} ({label})")

        out = run_tshark([
            "-Y", f"usb.bus_id == {bus_id} && usb.device_address == {dev_addr} && usb.transfer_type == 0x02",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "frame.time_relative",
            "-e", "usb.src",
            "-e", "usb.dst",
            "-e", "usb.endpoint_address",
            "-e", "usb.data_len",
            "-e", "usb.setup.bRequest",
            "-e", "usb.setup.wValue",
            "-e", "usb.setup.wIndex",
            "-e", "usb.capdata",
            "-E", "separator=|",
            "-c", "300"
        ], timeout=120)

        lines = [l for l in out.split("\n") if l.strip()]
        print(f"  Control transfer packets: {len(lines)}")

        if not lines:
            continue

        # Categorize by direction and request type
        host_to_dev = 0
        dev_to_host = 0
        requests = Counter()

        for line in lines:
            parts = line.split("|")
            if len(parts) >= 4:
                if parts[2] == "host":
                    host_to_dev += 1
                else:
                    dev_to_host += 1
            if len(parts) >= 7 and parts[6]:
                requests[parts[6]] += 1

        print(f"  Host -> Device: {host_to_dev}")
        print(f"  Device -> Host: {dev_to_host}")

        request_names = {
            "0x01": "CLEAR_FEATURE",
            "0x05": "SET_ADDRESS",
            "0x06": "GET_DESCRIPTOR",
            "0x09": "SET_CONFIGURATION",
            "0x0a": "SET_INTERFACE",
            "0x01": "SET_REPORT (HID)",
        }

        if requests:
            print(f"\n  Request types:")
            for req, count in requests.most_common():
                name = request_names.get(req, "")
                print(f"    bRequest={req} {name}: {count}")


def analyze_razer_protocol_data():
    """Deep analysis of Razer proprietary protocol data (98-byte control transfers)."""
    section("7. RAZER PROPRIETARY PROTOCOL ANALYSIS")
    print("  Razer devices use 90-byte feature reports for configuration.")
    print("  These are sent via SET_REPORT / GET_REPORT HID requests.")

    for bus_id, dev_addr, label in [(3, 5, "First"), (2, 3, "Second")]:
        subsection(f"Razer Protocol Data - Bus {bus_id} Dev {dev_addr} ({label})")

        # Razer control packets typically have specific data lengths (90 bytes payload)
        # They go to interface 0x02 (the third HID interface)
        out = run_tshark([
            "-Y", f"usb.bus_id == {bus_id} && usb.device_address == {dev_addr} && usb.data_len == 90",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "frame.time_relative",
            "-e", "usb.src",
            "-e", "usb.dst",
            "-e", "usb.endpoint_address",
            "-e", "usb.data_len",
            "-e", "usb.capdata",
            "-E", "separator=|",
            "-c", "200"
        ], timeout=120)

        lines = [l for l in out.split("\n") if l.strip()]

        if not lines:
            # Try other common Razer payload sizes
            for data_len in [91, 92, 98]:
                out = run_tshark([
                    "-Y", f"usb.bus_id == {bus_id} && usb.device_address == {dev_addr} && usb.data_len == {data_len}",
                    "-T", "fields",
                    "-e", "frame.number",
                    "-e", "frame.time_relative",
                    "-e", "usb.src",
                    "-e", "usb.dst",
                    "-e", "usb.data_len",
                    "-e", "usb.capdata",
                    "-E", "separator=|",
                    "-c", "100"
                ], timeout=120)
                lines = [l for l in out.split("\n") if l.strip()]
                if lines:
                    print(f"  Found {len(lines)} packets with data_len={data_len}")
                    break

        if not lines:
            print("  No Razer protocol packets found at this address.")
            continue

        print(f"  Found {len(lines)} Razer protocol packets")

        # Parse Razer protocol structure
        # Razer protocol: [status] [transaction_id] [remaining_packets] [protocol_type]
        #                  [data_size] [command_class] [command_id] [data...] [crc] [reserved]
        print(f"\n  Sample Razer protocol packets (showing command class & ID):")

        command_pairs = Counter()
        for i, line in enumerate(lines[:100]):
            parts = line.split("|")
            if len(parts) < 7 or not parts[6]:
                continue

            data_hex = parts[6].replace(":", "")
            frame = parts[0]
            time_rel = parts[1]
            direction = "OUT" if parts[2] == "host" else "IN"

            if len(data_hex) >= 18:
                status = data_hex[0:2]
                trans_id = data_hex[2:4]
                remaining = data_hex[4:8]
                proto_type = data_hex[8:10]
                data_size = data_hex[10:12]
                cmd_class = data_hex[12:14]
                cmd_id = data_hex[14:16]
                payload_start = data_hex[16:48]

                command_pairs[(cmd_class, cmd_id, direction)] += 1

                if i < 20:
                    print(f"    Frame {frame:>6s} [{direction:>3s}] status=0x{status} "
                          f"trans=0x{trans_id} type=0x{proto_type} "
                          f"size=0x{data_size} cmd=0x{cmd_class}:0x{cmd_id} "
                          f"data={payload_start}...")

        if command_pairs:
            print(f"\n  Command frequency summary:")
            # Known Razer command classes
            cmd_class_names = {
                "00": "Device Info",
                "01": "Device Mode",
                "02": "Macro",
                "03": "LED/Lighting",
                "04": "Keyboard",
                "05": "Mouse",
                "06": "Keypad",
                "07": "Custom",
                "0d": "Buttons/Keybinds",
                "0f": "Profile",
            }
            for (cls, cmd, direction), count in sorted(command_pairs.items()):
                cls_name = cmd_class_names.get(cls, "Unknown")
                print(f"    [{direction:>3s}] Class=0x{cls} ({cls_name}), Cmd=0x{cmd}: {count} packets")


def analyze_button_events():
    """Analyze button press/release events from the Razer mouse."""
    section("8. BUTTON EVENT ANALYSIS")
    print("  Looking for mouse button and side-button events...")

    for bus_id, dev_addr, label in [(3, 5, "First"), (2, 3, "Second")]:
        subsection(f"Button Events - Bus {bus_id} Dev {dev_addr} ({label})")

        # Mouse HID reports come as interrupt IN transfers on endpoint 0x81 (interface 0)
        # Standard mouse report: [buttons] [x_movement] [y_movement] [wheel]
        out = run_tshark([
            "-Y", f"usb.bus_id == {bus_id} && usb.device_address == {dev_addr} && usb.transfer_type == 0x01 && usb.endpoint_address == 0x81",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "frame.time_relative",
            "-e", "usb.data_len",
            "-e", "usbhid.data",
            "-e", "usb.capdata",
            "-E", "separator=|"
        ], timeout=180)

        lines = [l for l in out.split("\n") if l.strip()]
        print(f"  Endpoint 0x81 (Mouse) interrupt packets: {len(lines)}")

        if lines:
            # Analyze button byte patterns
            button_states = Counter()
            for line in lines:
                parts = line.split("|")
                data = ""
                if len(parts) >= 5 and parts[4]:
                    data = parts[4].replace(":", "")
                elif len(parts) >= 4 and parts[3]:
                    data = parts[3].replace(":", "")

                if data and len(data) >= 2:
                    button_byte = data[0:2]
                    button_states[button_byte] += 1

            if button_states:
                print(f"\n  Button byte values (first byte of HID report):")
                for btn, count in button_states.most_common(20):
                    btn_int = int(btn, 16)
                    pressed = []
                    if btn_int & 0x01: pressed.append("Left")
                    if btn_int & 0x02: pressed.append("Right")
                    if btn_int & 0x04: pressed.append("Middle")
                    if btn_int & 0x08: pressed.append("Back/Side4")
                    if btn_int & 0x10: pressed.append("Forward/Side5")
                    if btn_int & 0x20: pressed.append("Button6")
                    if btn_int & 0x40: pressed.append("Button7")
                    if btn_int & 0x80: pressed.append("Button8")
                    btn_desc = ", ".join(pressed) if pressed else "None (movement only)"
                    print(f"    0x{btn} ({btn_int:08b}): {count} packets  [{btn_desc}]")

        # Also check endpoint 0x82 and 0x83 (keyboard interfaces for side buttons)
        for ep_addr, ep_name in [("0x82", "Keyboard/Side-Buttons IF1"), ("0x83", "Keyboard/Side-Buttons IF2")]:
            out = run_tshark([
                "-Y", f"usb.bus_id == {bus_id} && usb.device_address == {dev_addr} && usb.transfer_type == 0x01 && usb.endpoint_address == {ep_addr}",
                "-T", "fields",
                "-e", "frame.number",
                "-e", "frame.time_relative",
                "-e", "usb.data_len",
                "-e", "usbhid.data",
                "-e", "usb.capdata",
                "-E", "separator=|"
            ], timeout=120)

            lines = [l for l in out.split("\n") if l.strip()]
            print(f"\n  Endpoint {ep_addr} ({ep_name}) interrupt packets: {len(lines)}")

            if lines:
                data_patterns = Counter()
                for line in lines[:500]:
                    parts = line.split("|")
                    data = ""
                    if len(parts) >= 5 and parts[4]:
                        data = parts[4].replace(":", "")
                    elif len(parts) >= 4 and parts[3]:
                        data = parts[3].replace(":", "")

                    if data:
                        data_patterns[data] += 1

                print(f"  Unique data patterns (top 20):")
                for pattern, count in data_patterns.most_common(20):
                    # For keyboard HID reports: [modifier] [reserved] [key1] [key2] ...
                    desc = ""
                    if len(pattern) >= 6:
                        modifier = int(pattern[0:2], 16)
                        keys = []
                        for k in range(4, len(pattern), 2):
                            key_code = int(pattern[k:k+2], 16)
                            if key_code > 0:
                                keys.append(f"0x{pattern[k:k+2]}")
                        if keys:
                            desc = f" keys={','.join(keys)}"
                        elif modifier:
                            desc = f" modifier=0x{pattern[0:2]}"
                        else:
                            desc = " (release/idle)"
                    print(f"    {pattern}: {count}{desc}")


def analyze_timing_patterns():
    """Analyze timing patterns to identify button change events."""
    section("9. TIMING & EVENT PATTERN ANALYSIS")
    print("  Looking for clusters of configuration activity (button remapping)...")

    for bus_id, dev_addr, label in [(3, 5, "First"), (2, 3, "Second")]:
        subsection(f"Timing - Bus {bus_id} Dev {dev_addr} ({label})")

        # Get control transfers with timing
        out = run_tshark([
            "-Y", f"usb.bus_id == {bus_id} && usb.device_address == {dev_addr} && usb.transfer_type == 0x02 && usb.data_len > 8",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "frame.time_relative",
            "-e", "usb.src",
            "-e", "usb.data_len",
            "-E", "separator=|"
        ], timeout=120)

        lines = [l for l in out.split("\n") if l.strip()]
        if not lines:
            print("  No significant control transfers found.")
            continue

        print(f"  Control transfers with data > 8 bytes: {len(lines)}")

        # Group by time clusters (bursts of activity)
        times = []
        for line in lines:
            parts = line.split("|")
            if len(parts) >= 2:
                try:
                    times.append((float(parts[1]), parts[0]))
                except:
                    pass

        if times:
            # Find bursts (gaps > 0.5s indicate separate events)
            bursts = []
            current_burst = [times[0]]
            for i in range(1, len(times)):
                if times[i][0] - times[i-1][0] > 0.5:
                    bursts.append(current_burst)
                    current_burst = [times[i]]
                else:
                    current_burst.append(times[i])
            bursts.append(current_burst)

            print(f"  Activity bursts (gap > 0.5s): {len(bursts)}")
            for i, burst in enumerate(bursts[:20]):
                start_time = burst[0][0]
                end_time = burst[-1][0]
                duration = end_time - start_time
                frames = [b[1] for b in burst]
                print(f"    Burst {i+1}: t={start_time:.3f}s, {len(burst)} packets, "
                      f"duration={duration:.3f}s, frames {frames[0]}-{frames[-1]}")


def analyze_razer_button_config():
    """Specifically look for Razer button configuration commands."""
    section("10. RAZER BUTTON CONFIGURATION COMMANDS")
    print("  Searching for SET_REPORT commands that configure button mappings...")
    print("  Razer command class 0x05 = Mouse, 0x0d = Button Bindings")

    for bus_id, dev_addr, label in [(3, 5, "First"), (2, 3, "Second")]:
        subsection(f"Button Config - Bus {bus_id} Dev {dev_addr} ({label})")

        # GET/SET feature reports sent to the device
        out = run_tshark([
            "-Y", f"usb.bus_id == {bus_id} && usb.device_address == {dev_addr} && usb.transfer_type == 0x02 && usb.data_len >= 90 && usb.dst != \"host\"",
            "-T", "fields",
            "-e", "frame.number",
            "-e", "frame.time_relative",
            "-e", "usb.data_len",
            "-e", "usb.capdata",
            "-E", "separator=|"
        ], timeout=120)

        lines = [l for l in out.split("\n") if l.strip()]
        print(f"  Outgoing config packets (>= 90 bytes): {len(lines)}")

        if not lines:
            continue

        for i, line in enumerate(lines):
            parts = line.split("|")
            if len(parts) < 4 or not parts[3]:
                continue

            frame = parts[0]
            time_rel = parts[1]
            data = parts[3].replace(":", "")

            if len(data) >= 16:
                status = data[0:2]
                trans_id = data[2:4]
                remaining = data[4:8]
                proto_type = data[8:10]
                data_size = data[10:12]
                cmd_class = data[12:14]
                cmd_id = data[14:16]
                payload = data[16:]

                print(f"\n  Frame {frame} (t={time_rel}s):")
                print(f"    Status=0x{status} TransID=0x{trans_id} Type=0x{proto_type}")
                print(f"    DataSize=0x{data_size} ({int(data_size, 16)}) CmdClass=0x{cmd_class} CmdID=0x{cmd_id}")
                print(f"    Payload: {payload[:64]}{'...' if len(payload) > 64 else ''}")
                print(f"    Full hex: {data}")

            if i >= 50:
                print(f"\n  ... (showing first 50 of {len(lines)} packets)")
                break


def main():
    print("*" * 70)
    print("  RAZER NAGA V2 PRO - USB CAPTURE ANALYSIS")
    print(f"  File: {os.path.basename(PCAP)}")
    print("*" * 70)

    analyze_capture_overview()
    analyze_all_usb_devices()
    analyze_razer_device_descriptor()
    analyze_razer_traffic_volume()
    analyze_razer_hid_reports()
    analyze_razer_control_transfers()
    analyze_razer_protocol_data()
    analyze_button_events()
    analyze_timing_patterns()
    analyze_razer_button_config()

    section("ANALYSIS COMPLETE")
    print("  Total sections analyzed: 10")
    print("  Razer device: VID=0x1532 PID=0x00a8")
    print("  This appears to be a Razer Naga V2 Pro wireless dongle.")
    print()

if __name__ == "__main__":
    main()
