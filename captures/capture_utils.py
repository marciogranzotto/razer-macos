#!/usr/bin/env python3
"""Shared helpers for capture-analysis scripts."""

import contextlib
import importlib.util
import io
import os
import sys
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from razer_report_decoder import parse_hex, RazerReport


def load_raw_packets() -> List[Tuple[float, RazerReport]]:
    """Load pre-extracted Razer HID reports from analyze_profile_switches.py RAW_DATA.

    Parses each line as "<timestamp> <hex_packet>" and returns a list of
    (seconds, RazerReport) tuples. Timestamps are floats (seconds); supports
    both dotted float and raw nanosecond integer formats. Malformed or
    un-parseable lines are silently skipped.
    """
    spec = importlib.util.spec_from_file_location(
        "_aps",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "analyze_profile_switches.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(mod)

    results: List[Tuple[float, RazerReport]] = []
    for line in mod.RAW_DATA.strip().splitlines():
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
