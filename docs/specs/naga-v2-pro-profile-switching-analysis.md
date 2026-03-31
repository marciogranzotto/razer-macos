# Razer Naga V2 Pro -- Profile Switching USB Capture Analysis (Capture 2)

**Date:** 2026-03-31
**Capture:** `captures/razer-naga-profile-switches-2.pcapng`
**Device:** Razer Naga V2 Pro wired (VID 0x1532, PID 0x00A7)
**Packets:** 103 Razer protocol packets (90 bytes each) over ~214 seconds (t=90s to t=304s)

This is a controlled capture where each user action is known precisely, replacing the earlier less-controlled first capture analysis.

## User Actions Performed

1. **Initial state:** `STEAMMACHINE-Default 1` off-board profile selected. No on-board profiles assigned.
2. **Assigned** 2nd on-board slot (red dot) to `Gaming` profile
3. **Assigned** 5th on-board slot (light blue dot) to `Blender` profile
4. **Assigned** 3rd on-board slot (green dot) to `STEAMMACHINE-Default 1` profile
5. **Switched** to `Gaming` profile (slot 2)
6. **Switched** to `Blender` profile (slot 5)
7. **Cleared** 2nd on-board profile (selected `None`)
8. **Cleared** 5th on-board profile (selected `None`)
9. **Cleared** 3rd on-board profile (selected `None`)

## Transaction IDs

Same as Capture 1: the wired Naga V2 Pro uses a rolling counter from `0x00` to `0x1e` (0-30), wrapping around. This differs from the wireless dongle's fixed `0x1f`.

---

## Timeline -- Packet Groups Mapped to User Actions

### Group 1 (t=90.5s) -- Initial State Read

| Time | Command | Details |
|------|---------|---------|
| 90.519 | `0x07:0x84` | Custom effect config read |
| 90.542 | `0x07:0x80` | Custom effect data read |

2 packets. Synapse reads current LED/effect state on connection.

---

### Group 2 (t=125.3-125.6s) -- Action 2: Assign Slot 2 = "Gaming"

Synapse writes the full profile configuration to on-board slot 2.

| Time | Command | Details |
|------|---------|---------|
| 125.289 | `0x05:0x02` data_size=1 | **GET_PROFILE** -- read current active profile (response: profile 2) |
| 125.315 | `0x15:0x80` | GET_BRIGHTNESS for profile 2 |
| 125.342 | `0x00:0x85` | GET_SERIAL -- read device serial |
| 125.369 | `0x05:0x08` data_size=0x45 | PROFILE_DATA write: profile 2, offset 0x00 (UUID + name "Gaming") |
| 125.396 | `0x05:0x08` data_size=0x45 | PROFILE_DATA write: profile 2, offset 0x40 (serial) |
| 125.424 | `0x05:0x08` data_size=0x45 | PROFILE_DATA write: profile 2, offset 0x80 (hash) |
| 125.451 | `0x05:0x08` data_size=0x3f | PROFILE_DATA write: profile 2, offset 0xC0 (zeros/padding) |
| 125.509 | `0x04:0x05` data_size=7 | SET_DPI: profile 2, X=3200, Y=3200 |
| 125.530 | `0x04:0x06` data_size=0x26 | DPI_STAGES: profile 2, 5 stages, active=4 |
| 125.552 | `0x0f:0x04` data_size=3 | LED_SET_COLOR: row=2 (profile indicator), brightness=0x54 |
| 125.575 | `0x06:0x8e` data_size=0x0e | MACRO_CLEAR |

**11 packets.** No button mapping writes -- the Gaming profile apparently uses default button bindings for the currently attached side panel.

---

### Group 3 (t=163.3-163.8s) -- Action 3: Assign Slot 5 = "Blender"

Same structure as Group 2, but with 12 button mapping writes because Blender has custom side-button bindings (numpad keys).

| Time | Command | Details |
|------|---------|---------|
| 163.264 | `0x05:0x02` data_size=1 | GET_PROFILE (response: profile 5) |
| 163.290 | `0x15:0x80` | GET_BRIGHTNESS for profile 5 |
| 163.318 | `0x00:0x85` | GET_SERIAL |
| 163.345 | `0x05:0x08` data_size=0x45 | PROFILE_DATA: profile 5, offset 0x00 ("Blender") |
| 163.371 | `0x15:0x00` | GET_DEVICE_MODE |
| 163.398 | `0x05:0x08` data_size=0x45 | PROFILE_DATA: profile 5, offset 0x40 (serial) |
| 163.425 | `0x05:0x08` data_size=0x45 | PROFILE_DATA: profile 5, offset 0x80 (hash) |
| 163.452 | `0x05:0x08` data_size=0x3f | PROFILE_DATA: profile 5, offset 0xC0 (zeros) |
| 163.512 | `0x04:0x05` data_size=7 | SET_DPI: profile 5, X=1600, Y=1600 |
| 163.533 | `0x04:0x06` data_size=0x26 | DPI_STAGES: profile 5, 5 stages, active=3 |
| 163.555 | `0x0f:0x04` data_size=3 | LED_SET_COLOR: row=5 |
| 163.577 | `0x02:0x0c` | BUTTON_WRITE: profile 5, btn 0x40 = Numpad 1 |
| 163.599 | `0x02:0x0c` | BUTTON_WRITE: profile 5, btn 0x41 = Numpad 2 |
| 163.622 | `0x02:0x0c` | BUTTON_WRITE: profile 5, btn 0x42 = Numpad 3 |
| 163.645 | `0x02:0x0c` | BUTTON_WRITE: profile 5, btn 0x43 = Numpad 4 |
| 163.667 | `0x02:0x0c` | BUTTON_WRITE: profile 5, btn 0x44 = Numpad 5 |
| 163.691 | `0x02:0x0c` | BUTTON_WRITE: profile 5, btn 0x45 = Numpad 6 |
| 163.714 | `0x02:0x0c` | BUTTON_WRITE: profile 5, btn 0x46 = Numpad 7 |
| 163.736 | `0x02:0x0c` | BUTTON_WRITE: profile 5, btn 0x47 = Numpad 8 |
| 163.760 | `0x02:0x0c` | BUTTON_WRITE: profile 5, btn 0x48 = Numpad 9 |
| 163.781 | `0x02:0x0c` | BUTTON_WRITE: profile 5, btn 0x49 = Numpad 0 |
| 163.803 | `0x02:0x0c` | BUTTON_WRITE: profile 5, btn 0x4a = Numpad . |
| 163.826 | `0x02:0x0c` | BUTTON_WRITE: profile 5, btn 0x4b = Numpad * |
| 163.848 | `0x06:0x8e` | MACRO_CLEAR |

**24 packets.** Note the slight ordering difference: GET_DEVICE_MODE appears between the first and second profile data chunks (unlike Group 2 where it was absent).

---

### Group 4 (t=199.7-200.1s) -- Action 4: Assign Slot 3 = "STEAMMACHINE-Default 1"

| Time | Command | Details |
|------|---------|---------|
| 199.716 | `0x05:0x02` data_size=1 | GET_PROFILE (profile 3) |
| 199.743 | `0x15:0x80` | GET_BRIGHTNESS for profile 3 |
| 199.769 | `0x00:0x85` | GET_SERIAL |
| 199.796 | `0x05:0x08` data_size=0x45 | PROFILE_DATA: profile 3, offset 0x00 ("STEAMMACHINE-Default 1") |
| 199.823 | `0x15:0x00` | GET_DEVICE_MODE |
| 199.850 | `0x05:0x08` data_size=0x45 | PROFILE_DATA: profile 3, offset 0x40 |
| 199.877 | `0x05:0x08` data_size=0x45 | PROFILE_DATA: profile 3, offset 0x80 |
| 199.903 | `0x05:0x08` data_size=0x3f | PROFILE_DATA: profile 3, offset 0xC0 |
| 199.960 | `0x04:0x05` data_size=7 | SET_DPI: profile 3, X=3200, Y=3200 |
| 199.982 | `0x04:0x06` data_size=0x26 | DPI_STAGES: profile 3, 5 stages, active=4 |
| 200.003 | `0x0f:0x04` data_size=3 | LED_SET_COLOR: row=3, brightness=0x7f |
| 200.025 | `0x02:0x0c` | BUTTON_WRITE: profile 3, btn 0x55 = GUI+Tab |
| 200.048 | `0x02:0x0c` | BUTTON_WRITE: profile 3, btn 0x50 = Mouse Back |
| 200.069 | `0x02:0x0c` | BUTTON_WRITE: profile 3, btn 0x53 = Ctrl+D |
| 200.091 | `0x02:0x0c` | BUTTON_WRITE: profile 3, btn 0x51 = Mouse Forward |
| 200.115 | `0x06:0x8e` | MACRO_CLEAR |

**16 packets.** This profile has custom bindings on the 6-button side panel (buttons 0x50-0x55) rather than the 12-button panel. Only 4 button writes were sent -- the remaining 2 buttons (0x52, 0x54) presumably use default bindings and were not written.

**Key observation:** LED brightness is 0x7f (127) for profile 3 vs 0x54 (84) for profiles 2 and 5, showing per-profile brightness.

---

### Group 5 (t=233.2-240.5s) -- Action 5: Switch to "Gaming" (Slot 2)

This group reads device state -- it appears to be Synapse refreshing its UI when the user selects a different profile, rather than sending a profile switch command.

| Time | Command | Details |
|------|---------|---------|
| 233.178 | `0x0f:0x80` data_size=0x50 | LED_FX_READ (large read) |
| 233.200 | `0x15:0x80` | GET_BRIGHTNESS for profile 1 |
| 233.221 | `0x0f:0x84` data_size=3 | LED_FX_CONFIG read |
| 233.243 | `0x15:0x00` | GET_DEVICE_MODE |
| 233.266 | `0x0f:0x04` data_size=3 | LED_SET_COLOR: row=1 (profile 1 indicator) |
| 233.288 | `0x15:0x07` data_size=9 | LED_LIST |
| 233.309 | `0x0f:0x80` data_size=0x50 | LED_FX_READ |
| 233.331 | `0x02:0x16` data_size=2 | GET_POLL_RATE |
| 233.353 | `0x0f:0x84` data_size=3 | LED_FX_CONFIG |
| 233.377 | `0x15:0x88` data_size=1 | GET_SERIAL (alternate) |
| 240.510 | `0x07:0x84` data_size=2 | Custom effect config |
| 240.534 | `0x07:0x80` data_size=2 | Custom effect data |

**12 packets.** ~7 second gap between t=233.4 and t=240.5 (user pausing). This group contains only reads and LED state queries -- no SET_PROFILE command is visible. The actual profile switch for slot 2 happens later in Group 7.

---

### Group 6 (t=245.6-246.3s) -- Action 6: Switch to "Blender" (Slot 5) + Interleaved Button Sync

This is the most complex group. Synapse appears to be performing a profile switch while simultaneously syncing button mappings across profiles 1 and 5.

| Time | Command | Profile | Details |
|------|---------|---------|---------|
| 245.638 | `0x04:0x06` DPI_STAGES | 1 | 5 stages, active=3 |
| 245.661 | `0x02:0x0c` BUTTON_WRITE | **5** | btn 0x40 = Numpad 1 |
| 245.683 | `0x15:0x80` GET_BRIGHTNESS | 1 | |
| 245.705 | `0x04:0x86` GET_DPI | 1 | |
| 245.727 | `0x02:0x0c` BUTTON_WRITE | **1** | btn 0x40 = Numpad 1 |
| 245.749 | `0x15:0x00` GET_DEVICE_MODE | 1 | |
| 245.771 | `0x04:0x86` GET_DPI | **5** | |
| 245.794 | `0x02:0x0c` BUTTON_WRITE | **5** | btn 0x41 = Numpad 2 |
| 245.818 | `0x15:0x07` LED_LIST | | |
| 245.839 | `0x02:0x0c` BUTTON_WRITE | **1** | btn 0x41 = Numpad 2 |
| 245.862 | `0x02:0x16` GET_POLL_RATE | | |
| 245.885 | `0x02:0x0c` BUTTON_WRITE | **5** | btn 0x42 = Numpad 3 |
| 245.907 | `0x15:0x88` GET_SERIAL | | |
| 245.928 | `0x02:0x0c` BUTTON_WRITE | **1** | btn 0x42 = Numpad 3 |
| 245.953 | `0x02:0x0c` BUTTON_WRITE | **5** | btn 0x43 = Numpad 4 |
| 245.975 | `0x02:0x0c` BUTTON_WRITE | **1** | btn 0x43 = Numpad 4 |
| 245.999 | `0x02:0x0c` BUTTON_WRITE | **5** | btn 0x44 = Numpad 5 |
| 246.021 | `0x02:0x0c` BUTTON_WRITE | **1** | btn 0x44 = Numpad 5 |
| 246.045 | `0x02:0x0c` BUTTON_WRITE | **5** | btn 0x45 = Numpad 6 |
| 246.067 | `0x02:0x0c` BUTTON_WRITE | **1** | btn 0x45 = Numpad 6 |
| 246.091 | `0x02:0x0c` BUTTON_WRITE | **5** | btn 0x46 = Numpad 7 |
| 246.114 | `0x02:0x0c` BUTTON_WRITE | **1** | btn 0x46 = Numpad 7 |
| 246.137 | `0x02:0x0c` BUTTON_WRITE | **5** | btn 0x47 = Numpad 8 |
| 246.160 | `0x02:0x0c` BUTTON_WRITE | **1** | btn 0x47 = Numpad 8 |
| 246.184 | `0x02:0x0c` BUTTON_WRITE | **5** | btn 0x48 = Numpad 9 |
| 246.206 | `0x02:0x0c` BUTTON_WRITE | **1** | btn 0x48 = Numpad 9 |
| 246.230 | `0x02:0x0c` BUTTON_WRITE | **5** | btn 0x49 = Numpad 0 |
| 246.254 | `0x02:0x0c` BUTTON_WRITE | **1** | btn 0x49 = Numpad 0 |
| 246.277 | `0x02:0x0c` BUTTON_WRITE | **5** | btn 0x4a = Numpad . |
| 246.299 | `0x02:0x0c` BUTTON_WRITE | **1** | btn 0x4a = Numpad . |
| 246.322 | `0x02:0x0c` BUTTON_WRITE | **5** | btn 0x4b = Numpad * |
| 246.346 | `0x02:0x0c` BUTTON_WRITE | **1** | btn 0x4b = Numpad * |

**32 packets.** The button writes for all 12 side buttons are written to BOTH profile 5 AND profile 1 in an alternating pattern: profile 5 first, then profile 1, for each button sequentially (0x40 through 0x4b). All bindings are identical (numpad keys). The state reads (brightness, DPI, device mode, poll rate, serial, LED list) are interleaved in the first half.

**Interpretation:** When switching to a profile that has custom button bindings, Synapse writes those bindings to both the target profile AND profile 1 (which may serve as the "active" or "off-board" profile). This ensures the device's current button state matches the newly active profile regardless of which on-board slot the firmware considers active.

---

### Group 7 (t=262.3s) -- Action 7: Clear Slot 2 (set to "None")

| Time | Command | Details |
|------|---------|---------|
| 262.270 | `0x05:0x03` data_size=1 | **SET_PROFILE = 2** |
| 262.293 | `0x06:0x8e` data_size=0x0e | MACRO_CLEAR |

**2 packets.** Clearing an on-board profile slot uses SET_PROFILE followed by MACRO_CLEAR.

**Hex verification** of the SET_PROFILE packet:
```
00 1c 00 00 00 01 05 03 02 00 00 00 ...
                     ^^ ^^ ^^
                     |  |  |
                     |  |  +-- arg[0] = 0x02 (profile number)
                     |  +----- cmd_id = 0x03 (SET)
                     +-------- cmd_class = 0x05 (Profile)
```

This is definitively `0x05:0x03` (SET_PROFILE), **not** `0x05:0x02` (GET_PROFILE). The data_size is `0x01` and the argument is the profile number to clear.

---

### Group 8 (t=286.7s) -- Action 8: Clear Slot 5 (set to "None")

| Time | Command | Details |
|------|---------|---------|
| 286.708 | `0x05:0x03` data_size=1 | **SET_PROFILE = 5** |
| 286.731 | `0x06:0x8e` | MACRO_CLEAR |

**2 packets.** Same pattern as Group 7.

Hex: `00 1e 00 00 00 01 05 03 05 ...` -- cmd_class=0x05, cmd_id=0x03, arg=0x05.

---

### Group 9 (t=304.0s) -- Action 9: Clear Slot 3 (set to "None")

| Time | Command | Details |
|------|---------|---------|
| 304.013 | `0x05:0x03` data_size=1 | **SET_PROFILE = 3** |
| 304.035 | `0x06:0x8e` | MACRO_CLEAR |

**2 packets.** Same pattern.

Hex: `00 01 00 00 00 01 05 03 03 ...` -- cmd_class=0x05, cmd_id=0x03, arg=0x03.

---

## Protocol Analysis

### 1. Profile Assignment Protocol

When Synapse assigns a Synapse profile to an on-board slot, it sends a full configuration sequence. The canonical order is:

```
1.  GET_PROFILE        (0x05:0x02)  -- read which slot is being configured
2.  GET_BRIGHTNESS     (0x15:0x80)  -- read current brightness for the slot
3.  GET_SERIAL         (0x00:0x85)  -- read device serial number
4.  PROFILE_DATA x4    (0x05:0x08)  -- write profile metadata (4 chunks at offsets 0x00/0x40/0x80/0xC0)
5.  [GET_DEVICE_MODE]  (0x15:0x00)  -- optional, not always present
6.  SET_DPI            (0x04:0x05)  -- set DPI for this profile
7.  DPI_STAGES         (0x04:0x06)  -- configure all DPI stages for this profile
8.  LED_SET_COLOR      (0x0f:0x04)  -- set profile indicator LED color/brightness
9.  BUTTON_WRITE x N   (0x02:0x0c)  -- write custom button bindings (0 if defaults, up to 12 for 12-btn panel)
10. MACRO_CLEAR        (0x06:0x8e)  -- clear macro buffer
```

**Observations:**
- GET_DEVICE_MODE (`0x15:0x00`) appeared in Groups 3 and 4 (between profile data chunks) but not in Group 2. Its position is not fixed.
- Button writes are only sent for buttons with non-default bindings. Gaming (Group 2) had 0 button writes. Blender had 12. STEAMMACHINE-Default 1 had 4 (on the 6-button panel).
- The sequence always ends with MACRO_CLEAR.

### 2. Profile Switching Protocol

When the user switches to a different already-assigned profile, the protocol is more complex than expected. Rather than a simple SET_PROFILE command, Synapse:

1. Reads device state (brightness, DPI, LED config, poll rate, serial) for profile 1 and the target profile
2. Writes button mappings to **both** the target profile and profile 1, interleaved

No explicit SET_PROFILE command was observed during profile switching in Groups 5-6. The firmware may automatically switch when the profile's settings are written, or the switch may happen through a mechanism not captured (e.g., the button writes themselves signal the active profile).

**This contrasts with Capture 1**, where simple SET_PROFILE + MACRO_CLEAR pairs were observed for quick profile switches. The difference may be that Capture 1 switched between already-loaded profiles, while here Synapse was also syncing button bindings.

### 3. Profile Clearing Protocol

Clearing an on-board profile slot ("None") uses a minimal 2-packet sequence:

```
1. SET_PROFILE  (0x05:0x03)  -- send the slot number to clear
2. MACRO_CLEAR  (0x06:0x8e)  -- clear macro buffer
```

This is the same SET_PROFILE command used for switching. The context determines the meaning:
- When profiles are assigned and you send SET_PROFILE(N), it **switches** to slot N.
- When Synapse's UI sets a slot to "None," it sends SET_PROFILE(N) + MACRO_CLEAR, presumably instructing the firmware to clear that slot.

The semantics of SET_PROFILE in a "clear" context remain ambiguous. It may be that:
- The firmware interprets SET_PROFILE as "activate this slot," and clearing happens through the Synapse-side state (Synapse no longer writes profile data to that slot).
- Or, Synapse sends SET_PROFILE to temporarily activate the slot, then the absence of profile data writes combined with MACRO_CLEAR effectively resets it.

Regardless, for our implementation, clearing an on-board slot is simply `SET_PROFILE(slot) + MACRO_CLEAR`.

### 4. Button Mapping Interleaving Discovery

At t=245-246s, when switching to the "Blender" profile (slot 5), Synapse writes button mappings in an **alternating pattern** between profile 5 and profile 1:

```
Profile 5: btn 0x40 = Numpad 1
Profile 1: btn 0x40 = Numpad 1
Profile 5: btn 0x41 = Numpad 2
Profile 1: btn 0x41 = Numpad 2
Profile 5: btn 0x42 = Numpad 3
Profile 1: btn 0x42 = Numpad 3
  ... (continues for all 12 buttons)
Profile 5: btn 0x4b = Numpad *
Profile 1: btn 0x4b = Numpad *
```

**Key observations:**
- Every button binding written to profile 5 is immediately duplicated to profile 1
- The bindings are identical -- both profiles receive the same numpad key assignments
- Profile 1 appears to serve as the "live" or "active device" profile, while profile 5 is the on-board storage slot
- This pattern was interleaved with device state reads (DPI, brightness, poll rate, etc.) in the first few iterations, then settled into pure alternating writes

**Implication:** When syncing profile bindings, Synapse writes to both the on-board slot AND profile 1. Profile 1 may be the "hardware-active" profile that the firmware uses for actual button dispatch, while on-board slots 2-5 are storage that the firmware can switch to independently.

---

## Command Reference

### 0x05:0x03 -- Set Active Profile / Clear Profile Slot

```
Offset  Size  Field
0       1     Profile number (1-5)
```

- `data_size` = `0x01`
- Dual purpose: switches to a profile when profiles are configured, or used as part of slot clearing when followed only by MACRO_CLEAR.
- Confirmed at t=262.3, t=286.7, t=304.0 (clearing slots 2, 5, 3).

### 0x05:0x02 -- Get Active Profile

```
Offset  Size  Field
0       1     Profile number (1-5, in response)
```

- `data_size` = `0x01`
- Read-only query. Seen at the start of each profile assignment sequence (Groups 2, 3, 4).
- The argument byte in the request may contain the slot being queried, or it may be the response echoing back the active profile. In all observed cases, the value matched the profile being configured.

### 0x05:0x08 -- Profile Data (Read/Write)

```
Offset  Size  Field
0       1     Profile number (1-5)
1       2     Offset (big-endian): 0x0000, 0x0040, 0x0080, 0x00C0
3       1     Reserved (always 0x00)
4       1     Marker byte (always 0xFA)
5       60/56 Data payload
```

- `data_size` = `0x45` (69) for offsets 0x00, 0x40, 0x80; `0x3f` (63) for offset 0xC0
- Profile data is written in 4 chunks totaling 256 bytes (64+64+64+64)
- The actual payload per chunk is 60 bytes (for 0x45) or 56 bytes (for 0x3f) after the 5-byte sub-header

**Chunk contents:**

| Offset | Content |
|--------|---------|
| 0x0000 | UUID (16 bytes, binary) + Profile name (ASCII, null-terminated, up to ~44 bytes) |
| 0x0040 | Device serial number (ASCII, null-terminated) |
| 0x0080 | Hash/checksum (hex-encoded ASCII string, ~50 chars) |
| 0x00C0 | Zeros (padding/reserved) |

### Profile Data Decoded from This Capture

**Slot 2 -- "Gaming":**
- UUID: `bee754e4-...` (matches Capture 1)
- Name: `Gaming` (6 chars + null)
- Serial: `6c605380538`
- Hash: `94de7f13304a44703029eadbdd8699c32f5792cf1a61a28c04a5`

**Slot 5 -- "Blender":**
- UUID: `b07475eb-d8b3-7047-8c4b-48f826cd2e1f` (matches Capture 1)
- Name: `Blender` (7 chars + null)
- Serial: `6c6053805387`
- Hash: `94d...` (same prefix as Gaming, likely device-specific)

**Slot 3 -- "STEAMMACHINE-Default 1":**
- UUID: `11ac9136-066c-f648-b077-c7e5623263bc`
- Name: `STEAMMACHINE-Default 1` (22 chars + null)
- Serial: `6c6053805387`
- Hash: `94d...` (same prefix)

Note: The serial number is the device serial, not profile-specific. The hash appears to be the same across profiles for the same device.

### 0x04:0x05 -- Set DPI (Per-Profile)

```
Offset  Size  Field
0       1     Profile number (1-5)
1       2     X DPI (big-endian)
3       2     Y DPI (big-endian)
5       2     Reserved (0x0000)
```

- `data_size` = `0x07`
- Sets the current DPI for the specified profile

DPI values observed:

| Profile | X DPI | Y DPI |
|---------|-------|-------|
| 2 (Gaming) | 3200 | 3200 |
| 5 (Blender) | 1600 | 1600 |
| 3 (STEAMMACHINE) | 3200 | 3200 |

### 0x04:0x06 -- DPI Stages (Per-Profile)

```
Offset  Size  Field
0       1     Profile number (1-5)
1       1     Active stage index (1-indexed)
2       1     Number of stages (1-5)
3+      7*N   Stage entries: [stage_num:1][x_dpi:2][y_dpi:2][reserved:2]
```

- `data_size` = `0x26` (38) -- enough for 5 stages of 7 bytes each + 3-byte header

**Correction from Capture 1 analysis:** Byte offsets 1 and 2 were previously documented as `[num_stages][active_stage]`. Based on careful cross-profile analysis in this capture, the order appears to be `[active_stage][num_stages]`. All profiles had 5 stages defined (`num_stages`=5), but different active stage indices.

DPI stage configurations observed:

| Profile | Active Stage | Stages | DPI Values |
|---------|-------------|--------|------------|
| 1 | 3 | 5 | 400, 800, 1600, 3200, 6400 |
| 2 (Gaming) | 4 | 5 | 400, 800, 1600, 3200, 6400 |
| 3 (STEAMMACHINE) | 4 | 5 | 400, 800, 1600, 3200, 6400 |
| 5 (Blender) | 3 | 5 | 400, 800, 1600, 3200, 6400 |

All profiles share the same 5 DPI stage values; only the active stage differs.

### 0x04:0x86 -- Get DPI (Read)

```
Offset  Size  Field
0       1     Profile number (in response)
```

- `data_size` = `0x50` (80) -- large read, likely returns full DPI configuration
- Seen at t=245.7 (profile 1) and t=245.8 (profile 5) during the profile switch/sync

### 0x0f:0x04 -- LED Set Color (Per-Profile)

```
Offset  Size  Field
0       1     Row (= profile number, used as profile indicator LED)
1       1     Brightness value
2       1     Reserved (0x00)
```

- `data_size` = `0x03`
- The `row` byte matches the profile number, suggesting this controls the profile indicator LED on the mouse

Brightness values observed:
- Profile 2: `0x54` (84)
- Profile 3: `0x7f` (127)
- Profile 5: `0x54` (84)
- Profile 1: `0x54` (84)

### 0x0f:0x80 -- LED Effect Read

```
Offset  Size  Field
0       80    LED effect data (device response)
```

- `data_size` = `0x50` (80)
- Reads the current LED effect/animation state from the device

### 0x0f:0x84 -- LED Effect Config

```
Offset  Size  Field
0       1     Row (profile/zone)
1       1     Config value
2       1     Reserved
```

- `data_size` = `0x03`
- Reads/writes LED effect configuration

### 0x15:0x80 -- Get Brightness (Per-Profile)

```
Offset  Size  Field
0       1     Profile number
1       1     Brightness value (in response)
```

- `data_size` = `0x02`

### 0x15:0x00 -- Get Device Mode

```
Offset  Size  Field
0       1     Profile number
1       1     Mode value (in response)
```

- `data_size` = `0x02`

### 0x15:0x07 -- LED List

```
Offset  Size  Field
0       1     Unknown (0x01 or 0x03)
1       1     Unknown (0x04 or 0x03)
2       1     Count/type (0x05)
3-7     5     LED IDs: 0x81, 0x82, 0x83, 0x84, 0x85
```

- `data_size` = `0x09`
- Lists available LED zones on the device. The 5 LED IDs likely correspond to the 5 profile indicator LEDs.

### 0x15:0x88 -- Get Serial (Alternate)

- `data_size` = `0x01`
- Alternative serial read command seen during profile switch state queries

### 0x02:0x16 -- Get Poll Rate

- `data_size` = `0x02`
- Reads the device polling rate

### 0x06:0x8e -- Macro Clear

```
(No arguments -- all 80 arg bytes are zero)
```

- `data_size` = `0x0e` (14)
- Clears the macro buffer. Always the final command in a profile assignment or clearing sequence.

### 0x07:0x84 / 0x07:0x80 -- Custom Effect Config / Data

- `data_size` = `0x02`
- Read custom LED effect configuration and data. Seen at initial state read and between profile operations.

---

## Full Command Reference Table

| Command | Class:ID | Direction | Data Size | Per-Profile | Description |
|---------|----------|-----------|-----------|-------------|-------------|
| Get Active Profile | `0x05:0x02` | Read | 1 | -- | Read active profile number |
| Set Active Profile | `0x05:0x03` | Write | 1 | -- | Set active profile / clear slot |
| Profile Data | `0x05:0x08` | Write | 69/63 | Yes | Write profile metadata (4 chunks) |
| Set DPI | `0x04:0x05` | Write | 7 | Yes | Set DPI X/Y for profile |
| Get DPI | `0x04:0x86` | Read | 80 | Yes | Read DPI configuration |
| DPI Stages | `0x04:0x06` | Write | 38 | Yes | Configure DPI stages for profile |
| LED Set Color | `0x0f:0x04` | Write | 3 | Yes | Set profile indicator LED |
| LED Effect Read | `0x0f:0x80` | Read | 80 | -- | Read LED effect state |
| LED Effect Config | `0x0f:0x84` | Read | 3 | -- | Read LED effect configuration |
| Get Brightness | `0x15:0x80` | Read | 2 | Yes | Read brightness for profile |
| Get Device Mode | `0x15:0x00` | Read | 2 | Yes | Read device mode |
| LED List | `0x15:0x07` | Read | 9 | -- | List available LED zones |
| Get Serial | `0x00:0x85` | Read | 1 | -- | Read device serial |
| Get Serial (alt) | `0x15:0x88` | Read | 1 | -- | Alternative serial read |
| Get Poll Rate | `0x02:0x16` | Read | 2 | -- | Read polling rate |
| Button Write | `0x02:0x0c` | Write | 10 | Yes | Write button mapping |
| Button Read | `0x02:0x8c` | Read | 10 | Yes | Read button mapping |
| Macro Clear | `0x06:0x8e` | Write | 14 | -- | Clear macro buffer |
| Custom FX Config | `0x07:0x84` | Read | 2 | -- | Custom effect config |
| Custom FX Data | `0x07:0x80` | Read | 2 | -- | Custom effect data |

---

## Impact on Our Implementation

### What This Confirms

1. **Profile number is the slot number (1-5):** The profile byte in all per-profile commands directly corresponds to the on-board slot position in the Synapse "On-Board Memory" UI (slot 1 = top/default, slot 2 = red dot, slot 3 = green dot, slot 4 = blue dot, slot 5 = light blue dot). Our current hardcoded `profile=0x01` targets slot 1.

2. **Button mappings are per-profile:** The same button can have different bindings in different profile slots. When we read/write button mappings, the profile byte determines which on-board slot is affected.

3. **SET_PROFILE is simple:** `0x05:0x03` with a 1-byte profile number. No complex handshaking required.

4. **MACRO_CLEAR should follow profile operations:** Every profile assignment, switch, and clearing sequence ends with `0x06:0x8e`.

### What We Can Safely Ignore (For Now)

1. **Profile metadata (0x05:0x08):** We do not need to write profile names, UUIDs, or hashes. These are Synapse-specific metadata for its UI. The device operates on slot numbers.

2. **Interleaved button writes to profile 1:** Synapse's behavior of writing to both the target slot and profile 1 appears to be a Synapse-specific sync strategy. For our app, writing to the target profile slot should be sufficient -- the device firmware will use the active profile's bindings.

3. **DPI stage management:** We already support DPI but not per-profile DPI stages. Adding profile support would require passing the profile number to DPI commands.

### Recommended Implementation Order

1. **Phase 1 (current):** Keep `profile=0x01` hardcoded. All button/DPI operations target slot 1. Works for single-profile use.

2. **Phase 2 (profile switching):**
   - Add `getActiveProfile()` -> `0x05:0x02`
   - Add `setActiveProfile(slot)` -> `0x05:0x03` + `0x06:0x8e`
   - Pass profile number through button read/write APIs

3. **Phase 3 (full profile management):**
   - Profile data read/write (`0x05:0x08`)
   - Per-profile DPI stages (`0x04:0x06`)
   - Per-profile LED settings (`0x0f:0x04`)
   - Per-profile brightness

### Open Questions

- **Why are profiles 1, 2, 3, 4, 5 used as on-board slots?** Profile 1 appears special -- Synapse writes button bindings to it during every profile switch, suggesting it is the "live" profile the firmware dispatches from.
- **Is SET_PROFILE truly dual-purpose (switch vs clear)?** Or does the firmware distinguish based on whether the slot has profile data written to it? Further testing needed.
- **What happens if we send SET_PROFILE without prior profile data write?** Does the firmware switch to an empty slot, or does it ignore the command?
- **Is the interleaved write pattern required?** Can we write all buttons to one profile, then all buttons to another, rather than alternating? Likely yes -- the interleaving is probably just Synapse's internal async I/O, not a protocol requirement.

---

## Packet Count Summary

| Group | Action | Packets |
|-------|--------|---------|
| 1 | Initial state read | 2 |
| 2 | Assign slot 2 = Gaming | 11 |
| 3 | Assign slot 5 = Blender | 24 |
| 4 | Assign slot 3 = STEAMMACHINE | 16 |
| 5 | Switch to Gaming (state reads) | 12 |
| 6 | Switch to Blender (interleaved sync) | 32 |
| 7 | Clear slot 2 | 2 |
| 8 | Clear slot 5 | 2 |
| 9 | Clear slot 3 | 2 |
| **Total** | | **103** |
