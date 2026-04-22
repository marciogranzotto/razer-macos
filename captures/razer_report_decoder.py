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
    # class=0x00 — misc/common commands (razerchromacommon.c)
    # Confirmed: razer_chroma_misc_get_polling_rate uses get_razer_report(0x00, 0x85, 0x01).
    # Note: analyze_profile_switches.py mislabels this "GET SERIAL NUMBER" — our driver
    # is authoritative here. Serial is 0x00:0x82 (razer_chroma_standard_get_serial).
    (0x00, 0x85): "GET_POLLING_RATE (class=00 cmd=85)",

    # class=0x02 — button/poll-rate commands
    # Confirmed: razer_mouse_attr_write_button_mapping uses get_razer_report(0x02, 0x0c, 0x0a).
    # Capture verified: size=10, arg layout [profile, btn_id, layer, action_type, params×6].
    (0x02, 0x0c): "SET_BUTTON_MAPPING (class=02 cmd=0c)",
    # Confirmed: razer_mouse_attr_read_button_mapping uses get_razer_report(0x02, 0x8c, 0x0a).
    # Not seen in capture (no read traffic captured), but direct driver code match.
    (0x02, 0x8c): "GET_BUTTON_MAPPING (class=02 cmd=8c)",
    # Observed with size=2, args=0100 in 4 packets. analyze_profile_switches.py labels it
    # "GET POLL RATE" but the driver's poll-rate command is class=0x00 cmd=0x85. No driver
    # match for 0x02:0x16 — insufficient evidence to label confidently.
    (0x02, 0x16): None,

    # class=0x04 — DPI commands
    (0x04, 0x05): "SET_DPI (class=04 cmd=05)",
    (0x04, 0x06): "SET_DPI_STAGES (class=04 cmd=06)",
    (0x04, 0x85): "GET_DPI (class=04 cmd=85)",
    # Confirmed: razer_mouse_attr_read_dpi_profile uses get_razer_report(0x04, 0x86, 0x07).
    # Reads a single profile's DPI X/Y — not a stages table. Renamed from
    # GET_DPI_STAGES_OR_PROFILE.
    (0x04, 0x86): "GET_DPI_PROFILE (class=04 cmd=86)",

    # class=0x05 — profile management commands
    # Hypothesized: consistently precedes full-resync flows, arg[0]=profile_index.
    # analyze_profile_switches.py labels it "GET ACTIVE PROFILE". Our driver uses
    # 0x05:0x82 for the same semantic (read active profile); 0x02 vs 0x82 may indicate
    # the request packet vs. a different read variant.
    (0x05, 0x02): "GET_ACTIVE_PROFILE (class=05 cmd=02, hypothesized)",
    (0x05, 0x03): "SET_ACTIVE_PROFILE (class=05 cmd=03)",
    # Hypothesized: observed as multi-packet (data_size=0x45, 69 bytes) at offsets
    # 0x0000/0x0040/0x0080/0x00c0; chunk at 0x0000 contains profile UUID + ASCII name.
    (0x05, 0x08): "PROFILE_METADATA (class=05 cmd=08, hypothesized)",
    (0x05, 0x82): "GET_ACTIVE_PROFILE (class=05 cmd=82)",

    # class=0x06 — macro commands
    (0x06, 0x8e): "MACRO_CLEAR (class=06 cmd=8e)",

    # class=0x0f — LED effect commands (Naga V2 Pro Synapse protocol; no driver match)
    (0x0f, 0x04): None,  # observed: 3 bytes, args[0]=profile/row, args[2]=brightness/value
    (0x0f, 0x80): None,  # observed at startup: data_size=80, args all zeros
    (0x0f, 0x84): None,  # observed: 3 bytes, args pattern 01:04:00 / 02:04:00

    # class=0x15 — device-info / LED-list commands (Naga V2 Pro Synapse protocol; no driver match)
    (0x15, 0x00): None,  # observed: 2 bytes, args[0:2]=profile_id repeated (e.g. 0x01 0x01)
    (0x15, 0x07): None,  # observed: variable, args[0]=count followed by LED IDs
    # Hypothesized: consistently observed with arg[0]=profile_index in brightness-read flows.
    # analyze_profile_switches.py labels it "GET BRIGHTNESS". No driver match.
    (0x15, 0x80): "GET_BRIGHTNESS (class=15 cmd=80, hypothesized)",
    (0x15, 0x88): None,  # observed: 1 byte, args[0]=0x00; different from razer_chroma_standard_get_serial (0x00:0x82)
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
