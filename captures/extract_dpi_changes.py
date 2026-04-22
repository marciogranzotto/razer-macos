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

import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capture_utils import load_raw_packets
from razer_report_decoder import parse_hex

PCAP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "razer-naga-pannel-swaps.pcapng")
TSHARK = shutil.which("tshark") or "tshark"

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
# Main: produce the DPI timeline.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Try tshark first; fall back to pre-extracted data if no DPI packets found.
    tshark_dpi = try_tshark()

    if tshark_dpi:
        # tshark yielded DPI packets — use them directly.
        source_label = "tshark (usb.capdata)"
        dpi_packets = tshark_dpi
        all_packets = []  # context view only available via the fallback path
    else:
        # tshark yielded no DPI packets; use pre-extracted data (all classes).
        source_label = "pre-extracted RAW_DATA (analyze_profile_switches.py)"
        all_packets = load_raw_packets()
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
    # Only available when we used the pre-extracted RAW_DATA path.
    # ---------------------------------------------------------------------------
    if all_packets:
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
