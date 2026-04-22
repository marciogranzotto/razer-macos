#!/usr/bin/env python3
"""Razer report decoder — parses 90-byte Razer HID reports into structured records.

Report layout (per openrazer):
  byte 0      status
  byte 1      transaction_id
  bytes 2-3   remaining_packets (big-endian u16)
  byte 4      protocol_type
  byte 5      data_size
  byte 6      command_class
  byte 7      command_id
  bytes 8-87  arguments (80 bytes)
  byte 88     crc
  byte 89     reserved
"""

from dataclasses import dataclass
from typing import Optional

# Command-name lookup keyed on (class, cmd). Populated from our C driver and
# razerchromacommon.c; extended as we decode unknowns. A None value means "observed
# in traffic but semantics not yet confirmed".
COMMAND_NAMES = {
    (0x00, 0x85): None,  # observed in captures, unknown
    (0x04, 0x05): "SET_DPI (class=04 cmd=05)",
    (0x04, 0x06): "SET_DPI_STAGES (class=04 cmd=06)",
    (0x04, 0x85): "GET_DPI (class=04 cmd=85)",
    (0x04, 0x86): "GET_DPI_STAGES_OR_PROFILE (class=04 cmd=86)",
    (0x05, 0x02): None,  # observed preceding per-slot writes, unknown
    (0x05, 0x03): "SET_ACTIVE_PROFILE (class=05 cmd=03)",
    (0x05, 0x08): None,  # observed as multi-packet, unknown (likely profile metadata)
    (0x05, 0x82): "GET_ACTIVE_PROFILE (class=05 cmd=82)",
    (0x06, 0x8e): "MACRO_CLEAR (class=06 cmd=8e)",
    (0x0f, 0x80): None,  # observed at startup, unknown
    (0x15, 0x80): None,  # observed in flows, unknown
}


@dataclass
class RazerReport:
    status: int
    transaction_id: int
    remaining_packets: int
    protocol_type: int
    data_size: int
    command_class: int
    command_id: int
    arguments: bytes  # 80 bytes
    crc: int
    reserved: int

    @property
    def name(self) -> str:
        key = (self.command_class, self.command_id)
        if key in COMMAND_NAMES:
            named = COMMAND_NAMES[key]
            if named is not None:
                return named
            return (
                f"OBSERVED (semantics unconfirmed) "
                f"class=0x{self.command_class:02x} cmd=0x{self.command_id:02x}"
            )
        return f"UNKNOWN class=0x{self.command_class:02x} cmd=0x{self.command_id:02x}"

    def args_hex(self, n: int = 8) -> str:
        return self.arguments[:n].hex()

    def summary(self) -> str:
        return (
            f"class=0x{self.command_class:02x} cmd=0x{self.command_id:02x} "
            f"size={self.data_size} args={self.args_hex(self.data_size)} "
            f"| {self.name}"
        )


def parse_hex(hex_str: str) -> Optional[RazerReport]:
    """Parse a 180-hex-char (90-byte) Razer report. Returns None if malformed."""
    hex_str = hex_str.strip().replace(" ", "")
    if len(hex_str) != 180:
        return None
    data = bytes.fromhex(hex_str)
    return RazerReport(
        status=data[0],
        transaction_id=data[1],
        remaining_packets=int.from_bytes(data[2:4], "big"),
        protocol_type=data[4],
        data_size=data[5],
        command_class=data[6],
        command_id=data[7],
        arguments=data[8:88],
        crc=data[88],
        reserved=data[89],
    )
