# Razer Naga V2 Pro — Button Mapping USB Protocol Specification

**Date:** 2026-02-22
**Status:** Draft (based on USB capture analysis)
**Device:** Razer Naga V2 Pro wireless dongle (VID 0x1532, PID 0x00A8)

## Transport

Button mapping uses HID Feature Reports (SET_REPORT / GET_REPORT) via USB control transfers. The Razer protocol frame is 90 bytes:

```
[status:1][trans_id:1][remaining:2][proto_type:1][data_size:1][cmd_class:1][cmd_id:1][params:80][crc:1][end:1]
```

With USBPcap, SET_REPORT appears as 98 bytes (8 setup + 90 payload) and GET_REPORT responses as 90 bytes.

### USB Device Structure

The wireless dongle (VID 0x1532, PID 0x00A8) enumerates as a single USB device
with 3 HID interfaces:

| Interface | Protocol | Endpoint | Function |
|-----------|----------|----------|----------|
| 0 | Mouse (0x02) | 0x81 IN | Mouse movement/clicks (8-byte HID reports) |
| 1 | Keyboard (0x01) | 0x82 IN | Keyboard output (side button keystrokes) |
| 2 | Keyboard (0x01) | 0x83 IN | Keyboard output (side button keystrokes) |

All Razer protocol commands (button mapping, LED, macros) go through endpoint
0x00 (control transfers / HID Feature Reports), not through the interrupt endpoints.

## Button Mapping Command

| Field | Write | Read |
|-------|-------|------|
| Command Class | `0x02` | `0x02` |
| Command ID | `0x0c` | `0x8c` (`0x80 \| 0x0c`) |
| Data Size | `0x0a` (10) | `0x0a` (10) |

### Payload Structure (10 bytes)

```
Byte[0]: Profile slot     (0x01 = profile 1)
Byte[1]: Button ID         (see Button ID table)
Byte[2]: Layer             (0x00 = Normal, 0x01 = Hypershift)
Byte[3]: Action type       (see Action Types)
Byte[4]: Action param 1    (sub_type or action-specific)
Byte[5]: Action param 2
Byte[6]: Action param 3
Byte[7]: Action param 4
Byte[8]: Action param 5
Byte[9]: Action param 6
```

## Action Types

### 0x00 — Disabled / Macro Queue

When all params are zero, the button is disabled.
When params contain a macro ID, it's a macro in queue/toggle mode.

**Note on "Default":** Razer Synapse's "Default" action sends NO USB command.
This was confirmed across three independent captures (#4, #5, #6) by exhaustive
analysis of all USB endpoints on the device:

| Endpoint | Interface | Checked? | Result |
|----------|-----------|----------|--------|
| 0x00 (2.3.0) | Control (Razer protocol) | Yes | Only LED data during Default windows |
| 0x81 (2.3.1) | HID Mouse (Interface 0) | Yes | Normal mouse movement only |
| 0x82 (2.3.2) | HID Keyboard (Interface 1) | Yes | 0 packets in entire capture |
| 0x83 (2.3.3) | HID Keyboard (Interface 2) | Yes | Only key output at startup, none during test |
| 0x81 (2.1.1) | Dev 1 ep1 (dongle telemetry) | Yes | Static 64-byte telemetry, no changes |

Capture #6 provided definitive proof: 3 Disabled + 3 Default = only 3 writes
(all Disabled). Zero commands of any kind sent for Default on any endpoint.

Factory default bindings are stored in device firmware and active on power-up
without configuration. Synapse likely only writes the specific default binding
(e.g., keyboard key "1") when transitioning from a non-disabled state to Default.
For the Disabled ↔ Default toggle test, no write is needed because the device
firmware already knows its defaults.

Capture #7 (2-btn panel) confirmed this also holds when transitioning from a
non-disabled state: setting button from "keyboard a" → "Default" produced no
write (2 keyboard writes for 4 total actions).

For our implementation, "Restore Default" should write the known factory binding
for that button (see Default Binding columns in Button ID tables below).

```
Disabled:    [profile] [button] [layer] 00 00 00 00 00 00 00
Macro Queue: [profile] [button] [layer] 00 00 [macro_hi] [macro_lo] 00 00 00

Examples:
  01 4b 00 00 00 00 00 00 00 00  — Disabled
  01 4b 00 00 00 24 1f 00 00 00  — Macro 0x241f in queue mode
```

### 0x01 — Mouse Button

```
[profile] [button] [layer] 01 01 [mouse_btn] 00 00 00 00
```

- Byte[4] = `0x01` (sub_type, always 0x01 for mouse)
- Byte[5] = mouse button number

| Value | Mouse Button |
|-------|-------------|
| `0x01` | Left Click |
| `0x02` | Right Click |
| `0x03` | Middle Click (Scroll Click) |
| `0x04` | Back (Button 4) |
| `0x05` | Forward (Button 5) |

```
Example: 01 4b 00 01 01 03 00 00 00 00  (Middle Click)
```

### 0x02 — Keyboard Key

```
[profile] [button] [layer] 02 02 [modifier] [keycode] 00 00 00
```

- Byte[4] = `0x02` (sub_type, always 0x02 for keyboard)
- Byte[5] = HID keyboard modifier bitmask
  - Bit 0: Left Ctrl
  - Bit 1: Left Shift
  - Bit 2: Left Alt
  - Bit 3: Left GUI (Win/Cmd)
  - Bit 4: Right Ctrl
  - Bit 5: Right Shift
  - Bit 6: Right Alt
  - Bit 7: Right GUI
- Byte[6] = HID keyboard usage code

```
Example: 01 4b 00 02 02 00 04 00 00 00  (key "a", no modifiers)
Example: 01 4b 00 02 02 01 04 00 00 00  (Ctrl+A)
```

### 0x03 — Macro (Play Once)

```
[profile] [button] [layer] 03 03 [macro_hi] [macro_lo] [play_mode] 00 00
```

- Byte[4] = `0x03` (sub_type, always 0x03 for macro play-once)
- Bytes[5:6] = Macro ID (big-endian, e.g., `0x241f`)
- Byte[7] = Play mode (`0x01` = play once)

The macro data itself is uploaded separately via cmd_class `0x06` (Keypad) commands.

```
Example: 01 4b 00 03 03 24 1f 01 00 00  (Macro 0x241f, play once)
```

### 0x06 — Sensitivity Clutch

```
[profile] [button] [layer] 06 05 [flags] [x_dpi_hi] [x_dpi_lo] [y_dpi_hi] [y_dpi_lo]
```

- Byte[4] = `0x05` (sub_type for sensitivity)
- Byte[5] = Flags (`0x05` when X-Y independent DPI enabled)
- Bytes[6:7] = X-axis DPI (big-endian, e.g., `0x0320` = 800)
- Bytes[8:9] = Y-axis DPI (big-endian, e.g., `0x09f6` = 2550)

```
Example: 01 4b 00 06 05 05 03 20 09 f6  (X=800 DPI, Y=2550 DPI)
```

### 0x0a — Multimedia / Consumer Key

```
[profile] [button] [layer] 0a 02 [usage_hi] [usage_lo] 00 00 00
```

- Byte[4] = `0x02` (sub_type, always 0x02 for consumer keys)
- Bytes[5:6] = HID Consumer Usage code (big-endian)

| Code | Function |
|------|----------|
| `0x00b5` | Next Track |
| `0x00b6` | Previous Track |
| `0x00cd` | Play/Pause |
| `0x00e2` | Mute |
| `0x00e9` | Volume Up |
| `0x00ea` | Volume Down |

```
Example: 01 4b 00 0a 02 00 ea 00 00 00  (Volume Down)
Example: 01 50 00 0a 02 00 cd 00 00 00  (Play/Pause)
```

### 0x0c — Hypershift Modifier

When setting Hypershift, Synapse sends **two writes**: one for normal layer and one for the Hypershift layer.

```
[profile] [button] [0x00] 0c 01 01 00 00 00 00  (normal layer)
[profile] [button] [0x01] 0c 01 01 00 00 00 00  (hypershift layer)
```

- Byte[4] = `0x01`
- Byte[5] = `0x01`

```
Example: 01 4b 00 0c 01 01 00 00 00 00  (Normal layer)
         01 4b 01 0c 01 01 00 00 00 00  (Hypershift layer)
```

### 0x12 — Scroll Wheel Control

```
[profile] [button] [layer] 12 [sub_type] [scroll_action] 00 00 00 00
```

- Byte[4] = `0x01` (sub_type)
- Byte[5] = Scroll action

| Value | Action |
|-------|--------|
| `0x04` | Cycle Up Scroll Wheel Stages |

```
Example: 01 4b 00 12 01 04 00 00 00 00  (Cycle Up Scroll Stages)
```

## Action Type Summary

| Type | Name | Sub-type (Byte[4]) | Notes |
|------|------|--------------------|-------|
| `0x00` | Disabled / Macro Queue | `0x00` | All zeros = disabled; with macro ID = queue mode |
| `0x01` | Mouse Button | `0x01` | |
| `0x02` | Keyboard Key | `0x02` | |
| `0x03` | Macro (Play Once) | `0x03` | |
| `0x06` | Sensitivity Clutch | `0x05` | Encodes X/Y DPI as big-endian 16-bit |
| `0x0a` | Multimedia Key | `0x02` | HID Consumer Usage codes |
| `0x0c` | Hypershift Modifier | `0x01` | Sends two writes (normal + HS layer) |
| `0x12` | Scroll Wheel Control | `0x01` | |

## Button IDs

### Standard Mouse Buttons (confirmed from capture #1 init reads)

| ID | Button |
|----|--------|
| `0x01` | Left Click |
| `0x02` | Right Click |
| `0x03` | Middle Click (scroll wheel) |
| `0x04` | Mouse Button 4 (Back) / 2-btn panel Button 2 |
| `0x05` | Mouse Button 5 (Forward) / 2-btn panel Button 1 |

### 2-Button Side Panel

The 2-button panel reuses the standard mouse back/forward button IDs.
These are the same physical buttons as Mouse Button 4 and 5.

| ID | Button | Default Binding |
|----|--------|----------------|
| `0x05` | Button 1 (top) | Mouse Button 5 / Forward (confirmed) |
| `0x04` | Button 2 (bottom) | Mouse Button 4 / Back (confirmed) |

### 6-Button Side Panel

| ID | Button | Default Binding |
|----|--------|----------------|
| `0x50` | Side Button 1 (top-left) | Key "1" |
| `0x51` | Side Button 2 | Key "2" |
| `0x52` | Side Button 3 | Key "3" |
| `0x53` | Side Button 4 | Key "4" |
| `0x54` | Side Button 5 | Key "5" |
| `0x55` | Side Button 6 (bottom-right) | Key "6" |

### 12-Button Side Panel

Button 1 = `0x40` (confirmed capture #5), Button 12 = `0x4b` (confirmed capture #4). Range `0x40`-`0x4b`.

| ID | Button | Default Binding |
|----|--------|----------------|
| `0x40` | Side Button 1 (top-left) | Key "1" (confirmed) |
| `0x41` | Side Button 2 | Key "2" |
| `0x42` | Side Button 3 | Key "3" |
| `0x43` | Side Button 4 | Key "4" |
| `0x44` | Side Button 5 | Key "5" |
| `0x45` | Side Button 6 | Key "6" |
| `0x46` | Side Button 7 | Key "7" |
| `0x47` | Side Button 8 | Key "8" |
| `0x48` | Side Button 9 | Key "9" |
| `0x49` | Side Button 10 | Key "0" |
| `0x4a` | Side Button 11 | Key "-" |
| `0x4b` | Side Button 12 (bottom-right) | Key "=" (confirmed) |

### 2-Button Side Panel (to be confirmed)

Unknown. May use a different range.

## Macro Upload (cmd_class 0x06 — Keypad)

When a macro is assigned, Synapse uploads the macro data before writing the button mapping:

| Command | Class | ID | Data Size | Description |
|---------|-------|----|-----------|-------------|
| Macro Clear | `0x06` | `0x8e` | 14 | Clear existing macro data |
| Macro Init | `0x06` | `0x08` | 6 | Initialize macro slot: `[macro_hi macro_lo 00 00 00 00]` |
| Macro Data | `0x06` | `0x0c` | 64-70 | Upload macro keystrokes in chunks |

Macro data upload uses chunked transfer with offset in the payload:
```
[macro_hi] [macro_lo] [00] [offset_hi] [00] [chunk_size] [keystroke_data...]
```

The first chunk (size=70) contains the actual keystrokes. Subsequent chunks (size=64) appear to be padding/continuation.

## Supporting Commands

### Custom Effects (0x07)

| Command | Class | ID | Data Size | Description |
|---------|-------|----|-----------|-------------|
| FX Read | `0x07` | `0x80` | 2 | Read custom effect data |
| FX Config | `0x07` | `0x84` | 2 | Custom effect config |

### General

| Command | Class | ID | Data Size | Description |
|---------|-------|----|-----------|-------------|
| Get Serial | `0x00` | `0x85` | 1 | Read device serial |
| Get FW Version | `0x00` | `0xb9` | 2 | Read firmware version |
| Unknown (panel swap?) | `0x00` | `0xbf` | 80 | Seen 3x during panel module change (all zeros). Possibly panel detection/reset. |

## Write Sequence

When Razer Synapse changes a button binding:

1. For simple bindings (keyboard, mouse, multimedia, scroll, disabled): sends a single `0x02:0x0c` SET_REPORT
2. For Hypershift modifier: sends **two** `0x02:0x0c` writes (normal layer then HS layer)
3. For macros: uploads macro data via `0x06` commands first, then sends `0x02:0x0c`
4. For sensitivity clutch: sends a single `0x02:0x0c` with DPI values encoded

No separate commit command is needed — bindings take effect immediately.

## Read Sequence (Init)

During initialization (captured in capture #1), Synapse reads all button bindings:

1. Send `0x02:0x8c` GET_REPORT for each button on each layer
2. Normal layer (Byte[2]=0x00): all button IDs
3. Hypershift layer (Byte[2]=0x01): all button IDs
4. ~80 total reads (38 normal + 42 hypershift) covering all device buttons

## Panel Detection

When a side panel is swapped, the device sends a **16-byte HID report on
endpoint 0x82** (keyboard interface 1) with the panel identifier. Synapse also
polls `0x00:0xb9` (FW version) and gets the panel ID back in the response byte.

### Panel Identification Report (endpoint 0x82)

```
05 0e [panel_id] 00 00 00 00 00 00 00 00 00 00 00 00 00
```

### Panel IDs

| Value | Panel |
|-------|-------|
| `0x00` | No panel / panel removed |
| `0x01` | 2-button panel |
| `0x03` | 12-button panel |
| `0x04` | 6-button panel |

Confirmed from capture #8 (3 panel swaps: 2→6→12→2):

| Time | Panel ID | Event |
|------|----------|-------|
| t=7.7s | `0x00` | 2-btn panel removed |
| t=13.7s | `0x04` | 6-btn panel inserted |
| t=19.6s | `0x00` | 6-btn panel removed |
| t=23.2s | `0x03` | 12-btn panel inserted |
| t=28.4s | `0x00` | 12-btn panel removed |
| t=32.5s | `0x01` | 2-btn panel inserted |

The same panel ID value also appears in the `0x00:0xb9` GET_REPORT response
payload byte[0], allowing detection via the Razer control protocol as well.

## LED Color Data (NOT button mapping)

Command `0x0f:0x03` with `data_size=11` is LED matrix color data:

```
[row:1][col:1][00][00][flag:1][R1:1][G1:1][B1:1][R2:1][G2:1][B2:1]
```

This is the majority of traffic in captures (95%+) due to lighting animations.

## Verified From Captures

| Source | Evidence |
|--------|----------|
| Capture #1 (6-btn panel) | 1 write: keyboard "a" on button 0x50 |
| Capture #1 (6-btn panel) | 80 reads: all button bindings during init |
| Capture #3 (6-btn panel) | 4 writes: keyboard "a", mouse middle, multimedia Play/Pause, disabled |
| Capture #4 (12-btn panel) | 10 writes: keyboard, mouse, scroll, sensitivity, macro x2, hypershift, multimedia, disabled |
| Capture #4 (12-btn panel) | Button 12 = ID `0x4b`, macro upload via 0x06 commands |
| Capture #5 (12-btn panel) | 4 Disabled writes for button 0x40, no Default command found |
| Capture #5 (12-btn panel) | Button 1 = ID `0x40`, confirming 12-btn range `0x40`-`0x4b` |
| Capture #6 (12-btn panel) | Definitive: 3 Disabled + 3 Default = only 3 writes. All endpoints checked. |
| Capture #6 (12-btn panel) | Endpoint 2.3.3 key output confirmed: button 1 sends HID keycode `0x1e` ("1") |
| Capture #7 (2-btn panel) | Button 1 = `0x05`, Button 2 = `0x04` (same as Mouse Btn 5/4) |
| Capture #7 (2-btn panel) | "Default" sends no write even from non-disabled state (keyboard→Default = 0 writes) |
| Capture #7 (2-btn panel) | `0x00:0xbf` command (size=80, all zeros) seen 3x during panel module swap |
| Capture #8 (panel swaps) | Panel IDs: 0x01=2-btn, 0x03=12-btn, 0x04=6-btn, 0x00=none |
| Capture #8 (panel swaps) | Panel ID in 16-byte HID report on ep 0x82: `05 0e [panel_id] ...` |
| Capture #8 (panel swaps) | Panel ID also in `0x00:0xb9` FW version response byte[0] |

## Still To Confirm

- [x] ~~Disabled vs Default: "Default" sends no USB command (confirmed across 4 captures, all endpoints, both from disabled and non-disabled states)~~
- [x] ~~12-button panel button ID range: `0x40`-`0x4b` (button 1=`0x40`, button 12=`0x4b`)~~
- [x] ~~USB device interface structure: 3 HID interfaces (mouse + 2x keyboard) on single dongle device~~
- [x] ~~Default from non-disabled state: NO write sent (capture #7: "keyboard a"→Default produced 0 writes)~~
- [x] ~~2-button panel button IDs: `0x05` (btn 1) and `0x04` (btn 2), same as Mouse Btn 5/4~~
- [x] ~~Panel detection: HID report `05 0e XX` on ep 0x82 + `0x00:0xb9` response (0x00=none, 0x01=2btn, 0x03=12btn, 0x04=6btn)~~
- [ ] Profile switching commands (0x0f:0x02, 0x0f:0x04)
- [ ] Sensitivity clutch flags byte (0x05 = X-Y independent, other values?)
- [ ] Scroll wheel actions beyond "Cycle Up" (Cycle Down, etc.)
- [ ] Macro play modes beyond play-once (0x01) and queue (0x00)
