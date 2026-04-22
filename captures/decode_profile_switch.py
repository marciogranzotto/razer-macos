#!/usr/bin/env python3
"""Decode the profile-switch traffic extracted in analyze_profile_switches.py.

Produces a human-readable timeline of every Razer report in the switch flow.
"""

import sys
import os
import contextlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from razer_report_decoder import parse_hex

# Import the raw data block from the existing script
import importlib.util
spec = importlib.util.spec_from_file_location(
    "_aps", os.path.join(os.path.dirname(__file__), "analyze_profile_switches.py")
)
_aps = importlib.util.module_from_spec(spec)
with open(os.devnull, "w") as devnull, contextlib.redirect_stdout(devnull):
    spec.loader.exec_module(_aps)

RAW = _aps.RAW_DATA.strip().splitlines()

print(f"{'time(s)':>10}  {'summary'}")
print("-" * 100)
for line in RAW:
    parts = line.strip().split(None, 1)
    if len(parts) != 2:
        continue
    ts_ns, hex_pkt = parts
    try:
        ts = float(ts_ns) if "." in ts_ns else int(ts_ns) / 1e9
    except ValueError:
        continue
    rpt = parse_hex(hex_pkt)
    if rpt is None:
        continue
    print(f"{ts:>10.3f}  {rpt.summary()}")
