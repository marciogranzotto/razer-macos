#!/usr/bin/env python3
"""
Analyze the default button bindings from capture #1 (read responses).
Capture #1 has the full init sequence with all 80 button reads.
"""
import subprocess
from collections import Counter

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

HID_KEYCODES = {
    0x00: "None", 0x04: "a", 0x05: "b", 0x06: "c", 0x07: "d", 0x08: "e",
    0x1e: "1", 0x1f: "2", 0x20: "3", 0x21: "4", 0x22: "5", 0x23: "6",
    0x24: "7", 0x25: "8", 0x26: "9", 0x27: "0",
    0x59: "KP1", 0x5a: "KP2", 0x5b: "KP3", 0x5c: "KP4",
    0x5d: "KP5", 0x5e: "KP6", 0x5f: "KP7", 0x60: "KP8",
    0x61: "KP9", 0x62: "KP0",
}

MOUSE_BUTTONS = {
    0x01: "Left", 0x02: "Right", 0x03: "Middle",
    0x04: "Back", 0x05: "Forward",
}

def decode_action(b):
    if len(b) < 4:
        return "?"
    action_type = b[3]
    if action_type == 0x00:
        return "Disabled"
    elif action_type == 0x01:
        sub = b[4] if len(b) > 4 else 0
        btn = b[5] if len(b) > 5 else 0
        return f"Mouse:{MOUSE_BUTTONS.get(btn, f'0x{btn:02x}')} (sub=0x{sub:02x})"
    elif action_type == 0x02:
        sub = b[4] if len(b) > 4 else 0
        mod = b[5] if len(b) > 5 else 0
        key = b[6] if len(b) > 6 else 0
        key_name = HID_KEYCODES.get(key, f"0x{key:02x}")
        return f"Kbd:{key_name} (sub=0x{sub:02x} mod=0x{mod:02x})"
    elif action_type == 0x05:
        sub = b[4] if len(b) > 4 else 0
        param = b[5] if len(b) > 5 else 0
        return f"Default (sub=0x{sub:02x} param=0x{param:02x})"
    elif action_type == 0x0a:
        page = b[4] if len(b) > 4 else 0
        code_hi = b[5] if len(b) > 5 else 0
        code_lo = b[6] if len(b) > 6 else 0
        return f"Multimedia:0x{code_hi:02x}{code_lo:02x} (page=0x{page:02x})"
    else:
        return f"Unknown:0x{action_type:02x}"

def main():
    print("=" * 80)
    print("  DEFAULT BUTTON BINDINGS FROM CAPTURE #1")
    print("  (0x02:0x8c GET_REPORT responses)")
    print("=" * 80)

    # Capture 1 had two phases - Bus 3 Dev 5 and Bus 2 Dev 3
    all_responses = []
    for bus, dev, label in [(3, 5, "Phase1"), (2, 3, "Phase2")]:
        out = run([
            "-Y", f"usb.bus_id=={bus} && usb.device_address=={dev} && usb.data_len>=90 && usb.data_len<=98 && usb.src!= host",
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
            parsed["label"] = label
            all_responses.append(parsed)

    # Filter for 0x02:0x8c responses with status OK (0x02)
    btn_responses = [p for p in all_responses
                     if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c
                     and p["status"] == 0x02]  # RESPONSE_OK or RESPONSE_BUSY

    # Also try status 0x03 (RESPONSE_OK)
    btn_responses_ok = [p for p in all_responses
                        if p["cmd_class"] == 0x02 and p["cmd_id"] == 0x8c]

    print(f"\n  Total 0x02:0x8c responses: {len(btn_responses_ok)}")
    print(f"  Status distribution: {Counter(p['status'] for p in btn_responses_ok)}")

    # Show all button bindings
    print("\n  Button bindings:")
    for p in sorted(btn_responses_ok, key=lambda x: float(x["time"])):
        b = [int(p["payload"][j:j+2], 16) for j in range(0, p["data_size"]*2, 2)]
        if len(b) < 4:
            continue
        profile = b[0]
        button_id = b[1]
        hypershift = b[2]
        action_desc = decode_action(b)
        hs_str = "HS" if hypershift == 1 else "NL"
        status_names = {0: "NEW", 2: "BUSY", 3: "OK", 4: "FAIL", 5: "TIMEOUT"}
        status = status_names.get(p["status"], f"0x{p['status']:02x}")
        payload_hex = " ".join(f"{x:02x}" for x in b)
        print(f"    [{p['label']}] Btn=0x{button_id:02x} {hs_str} status={status} -> {action_desc}")
        print(f"           [{payload_hex}]")


if __name__ == "__main__":
    main()
