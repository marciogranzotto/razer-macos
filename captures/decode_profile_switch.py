#!/usr/bin/env python3
"""Decode the profile-switch traffic extracted in analyze_profile_switches.py.

Produces a human-readable timeline of every Razer report in the switch flow.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capture_utils import load_raw_packets

packets = load_raw_packets()

print(f"{'time(s)':>10}  {'summary'}")
print("-" * 100)
for ts, rpt in packets:
    print(f"{ts:>10.3f}  {rpt.summary()}")
