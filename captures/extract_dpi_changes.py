#!/usr/bin/env python3
"""Extract DPI-related packets from the Naga V2 Pro capture.

Filters for class=0x04 (DPI family) reports in both directions.
Prints timeline with decoded summaries.

NOTE on pcapng extraction: This capture was recorded with USBPcap on Windows.
On macOS tshark, the Razer HID SET_REPORT packets (class 0x04/0x05/0x06) are stored
in the USB Control transfer setup stage and are NOT accessible via usb.capdata or
usb.data_fragment on the macOS tshark build (the data_fragment field only yields the
LED/HyperProf commands on interface 1, device 1).  The Razer control-command payloads
were therefore pre-extracted on Windows and stored verbatim in analyze_profile_switches.py.

This script reads that pre-extracted data directly, filtering for DPI family commands.
The broader context (classes 0x04 and 0x05) is produced by the inline block below.
"""

import subprocess
import sys
import os
import contextlib
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from razer_report_decoder import parse_hex

PCAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "razer-naga-pannel-swaps.pcapng")
TSHARK = "/opt/homebrew/bin/tshark"

# ---------------------------------------------------------------------------
# Step 1: Attempt tshark extraction (usb.capdata — works for LED/misc frames).
#         Razer HID control commands (0x04/0x05/0x06) are NOT present in
#         usb.capdata for this capture; they live in the USB Control setup
#         data stage.  We therefore fall back to the pre-extracted data.
# ---------------------------------------------------------------------------

def try_tshark():
    """Return list of (ts_float, RazerReport) via tshark usb.capdata, class 0x04 only."""
    try:
        cmd = [
            TSHARK, "-r", PCAP, "-T", "fields",
            "-e", "frame.time_relative",
            "-e", "usb.capdata",
            "-Y", "usb.capdata",
        ]
        proc = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return []

    results = []
    for line in proc.stdout.splitlines():
        parts = line.strip().split("\t")
        if len(parts) != 2:
            continue
        ts, hex_pkt = parts
        hex_pkt = hex_pkt.replace(":", "").replace(",", "").strip()
        rpt = parse_hex(hex_pkt)
        if rpt is None or rpt.command_class != 0x04:
            continue
        try:
            ts_f = float(ts)
        except ValueError:
            continue
        results.append((ts_f, rpt))
    return results


# ---------------------------------------------------------------------------
# Step 2: Load pre-extracted raw data from analyze_profile_switches.py.
#         This is the authoritative source for Razer control commands.
# ---------------------------------------------------------------------------

def load_raw_data():
    """Load pre-extracted packets from analyze_profile_switches.py RAW_DATA."""
    spec = importlib.util.spec_from_file_location(
        "_aps",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyze_profile_switches.py"),
    )
    _aps = importlib.util.module_from_spec(spec)
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(_aps)

    results = []
    for line in _aps.RAW_DATA.strip().splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2:
            continue
        ts_str, hex_pkt = parts
        try:
            ts_f = float(ts_str) if "." in ts_str else int(ts_str) / 1e9
        except ValueError:
            continue
        rpt = parse_hex(hex_pkt)
        if rpt is None:
            continue
        results.append((ts_f, rpt))
    return results


# ---------------------------------------------------------------------------
# Main: produce the DPI timeline.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Try tshark first; supplement with pre-extracted data if no DPI packets found.
    tshark_dpi = try_tshark()
    all_packets = load_raw_data()

    if tshark_dpi:
        # tshark yielded DPI packets — use them directly.
        source_label = "tshark (usb.capdata)"
        dpi_packets = tshark_dpi
    else:
        # tshark yielded no DPI packets; use pre-extracted data (all classes).
        source_label = "pre-extracted RAW_DATA (analyze_profile_switches.py)"
        dpi_packets = [(ts, rpt) for ts, rpt in all_packets if rpt.command_class == 0x04]

    print(f"Source: {source_label}")
    print(f"DPI (class=0x04) packets found: {len(dpi_packets)}")
    print()
    print(f"{'time(s)':>10}  {'summary'}")
    print("-" * 100)
    for ts_f, rpt in sorted(dpi_packets, key=lambda x: x[0]):
        print(f"{ts_f:>10.3f}  {rpt.summary()}")

    # ---------------------------------------------------------------------------
    # Context view: show DPI + profile commands together (classes 0x04 and 0x05).
    # ---------------------------------------------------------------------------
    print()
    print("=" * 100)
    print("CONTEXT: DPI (0x04) and Profile (0x05) commands together")
    print("=" * 100)
    print(f"{'time(s)':>10}  {'summary'}")
    print("-" * 100)
    ctx_packets = [
        (ts, rpt) for ts, rpt in all_packets
        if rpt.command_class in (0x04, 0x05)
    ]
    for ts_f, rpt in sorted(ctx_packets, key=lambda x: x[0]):
        print(f"{ts_f:>10.3f}  {rpt.summary()}")
