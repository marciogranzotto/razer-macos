#!/usr/bin/env python3
"""Extract button-mapping (class=0x02) traffic from the Naga V2 Pro capture.

Uses the pre-extracted RAW_DATA loader (capture_utils.load_raw_packets) because
macOS tshark cannot read Razer HID control commands from this USBPcap-format file
(the packets live in USB Control transfer setup stage, not usb.capdata). Also prints
class 0x05 (profile) for context — useful to see whether button-mapping writes
are preceded by SET_ACTIVE_PROFILE (0x05:0x03) or the hypothesized
SELECT_PROFILE_CONTEXT (0x05:0x02).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from capture_utils import load_raw_packets

# Classes relevant to button-mapping analysis and its context.
# 0x02 = button-mapping (SET = 0x0d in our driver, GET = unknown cmd)
# 0x05 = profile management (SET_ACTIVE = 0x03, possible SELECT_CONTEXT = 0x02)
# 0x06 = macro commands (MACRO_CLEAR = 0x8e) — observed near profile switches
RELEVANT_CLASSES = {0x02, 0x05, 0x06}

if __name__ == "__main__":
    packets = load_raw_packets()
    relevant = [(ts, rpt) for ts, rpt in packets if rpt.command_class in RELEVANT_CLASSES]

    print(f"Button-mapping context packets (classes 0x02, 0x05, 0x06): {len(relevant)}")
    print()
    print(f"{'time(s)':>10}  {'summary'}")
    print("-" * 100)
    for ts, rpt in sorted(relevant, key=lambda x: x[0]):
        print(f"{ts:>10.3f}  {rpt.summary()}")
