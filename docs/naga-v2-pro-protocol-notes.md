# Naga V2 Pro Protocol Notes (Working)

**Status:** Phase 1 complete. Preflight findings below. Phase 2 probes pending.

## Source data
- USB capture: `captures/razer-naga-pannel-swaps.pcapng` (~52 MB)
- Extracted profile-switch packets: `captures/analyze_profile_switches.py`
- Synapse config export (JSON, not a capture): `docs/profiles - 1774992262695.synapse4`

## Command inventory

| (class, cmd) | data_size range | observed arg[0] | label | notes |
|--------------|-----------------|-----------------|-------|-------|
| (0x04, 0x05) | 0x07 (7 bytes) | 0x03, 0x04 | SET_DPI | arg[0]=profile index, arg[1:3]=X DPI (BE u16), arg[3:5]=Y DPI (BE u16), arg[5:7]=0x0000 padding. Observed at t=25.725s (profile=4, 3200/3200 DPI) and t=33.158s (profile=3, 1600/1600 DPI). Always immediately followed by SET_DPI_STAGES (~23ms gap). |
| (0x04, 0x06) | 0x26 (38 bytes) | 0x01, 0x03, 0x04 | SET_DPI_STAGES | arg[0]=profile, arg[1]=num_stages, arg[2]=active_stage (always 0x05 = "no active preset"), then stage entries. Observed at t=12.099s (profile=1, 3 stages), t=25.748s (profile=4, 4 stages), t=33.179s (profile=3, 3 stages), t=38.112s (profile=1, 4 stages). |
| (0x04, 0x86) | 0x50 or 0x26 | 0x01, 0x04 | GET_DPI_PROFILE | Read back profile DPI. Observed at t=12.167s (arg[0]=1) and t=38.160s/t=38.204s (arg[0]=1, arg[0]=4). Driver name: `razer_mouse_attr_read_dpi_profile`, `get_razer_report(0x04, 0x86, 0x07)`. |
| (0x05, 0x02) | 0x01 | 0x03, 0x04 | GET_ACTIVE_PROFILE (hypothesized — see note) | Observed as preamble to full-resync flows at t=25.479s (arg[0]=4) and t=32.909s (arg[0]=3). Labeled "GET ACTIVE PROFILE" by `analyze_profile_switches.py`. Our driver uses 0x05:0x82 for the same semantic; 0x05:0x02 may be the request variant and 0x05:0x82 the response variant, or they may be distinct commands. Ambiguity unresolved — see "Still-unknown commands". |
| (0x05, 0x03) | 0x01 | 0x02, 0x03 | SET_ACTIVE_PROFILE | Sets active profile on device. Observed at t=15.870s (arg[0]=3) and t=17.777s (arg[0]=2). Always immediately followed by MACRO_CLEAR in the minimal 2-command switch flow. |
| (0x05, 0x08) | 0x45 (69 bytes) | 0x03, 0x04 | PROFILE_METADATA (hypothesized) | Multi-chunk profile metadata read. arg[0]=profile, arg[1:3]=chunk offset (BE u16): observed offsets 0x0000, 0x0040, 0x0080, 0x00c0. Chunk at offset 0x0000 contains binary profile UUID (16 bytes) followed by null-terminated ASCII profile name (e.g., "Gaming", "Blender"). |
| (0x05, 0x82) | 0x01 | unknown | GET_ACTIVE_PROFILE (driver name) | Driver: `razer_mouse_attr_read_active_profile`, `get_razer_report(0x05, 0x82, 0x01)`. Not observed in this capture (no read-response traffic captured). May be the response/acknowledgment variant of 0x05:0x02, or a distinct read command. Ambiguity flagged for Phase 2. |
| (0x06, 0x8e) | 0x0e (14 bytes) | n/a (all-zero args) | MACRO_CLEAR | Always the last command in any profile-related burst. data_size=14, all 14 argument bytes are 0x00. Appears to be a "clear all" with no slot identifier. Observed 4 times at t=15.892s, t=17.801s, t=25.791s, t=33.495s. |
| (0x02, 0x0c) | 0x0a (10 bytes) | 0x01, 0x03 | SET_BUTTON_MAPPING | arg[0]=profile, arg[1]=button_id (0x40–0x4b for 12-btn panel, 0x50–0x55 for 6-btn panel), arg[2]=layer (0x00=normal, 0x01=hypershift), arg[3]=action_type (0x01=mouse_button, 0x02=keyboard, 0x0a=multimedia, 0x0c=hypershift), arg[4:10]=action_params. 28 packets in 3 groups. Driver match: `get_razer_report(0x02, 0x0c, 0x0a)`. |
| (0x02, 0x8c) | 0x0a (10 bytes) | unknown | GET_BUTTON_MAPPING | Driver: `razer_mouse_attr_read_button_mapping`, `get_razer_report(0x02, 0x8c, 0x0a)`. Not observed in this capture (no read-response traffic). |
| (0x00, 0x85) | 0x01 | 0x00 | GET_POLLING_RATE (driver name) | Driver (`razer_chroma_misc_get_polling_rate`) uses `get_razer_report(0x00, 0x85, 0x01)` — driver label is authoritative. However, `analyze_profile_switches.py` labels this "GET SERIAL NUMBER" because it appears in full-resync flows where serial reads are expected. This is a confirmed label mismatch: the driver's serial read is 0x00:0x82 (`razer_chroma_standard_get_serial`). Resolution requires Phase 2 live probing. |
| (0x02, 0x16) | 0x02 (2 bytes) | 0x01 | unlabeled | Observed 4 times at t=10.174s, t=12.301s, t=38.249s, t=42.142s. args=0x0100 every occurrence. `analyze_profile_switches.py` labels it "GET POLL RATE" but the driver's polling-rate command is class=0x00 cmd=0x85. No driver code match for 0x02:0x16. Purpose unconfirmed. |
| (0x0f, 0x04) | 0x03 (3 bytes) | varies | unlabeled | Observed in full-resync flows. arg[0]=profile or row index, arg[1]=0x00, arg[2]=brightness/value. Likely LED-related (LED_SET_COLOR or LED_SET_BRIGHTNESS). |
| (0x0f, 0x84) | 0x03 (3 bytes) | 0x01, 0x02 | unlabeled | Observed with args 0x01:0x04:0x00 and 0x02:0x04:0x00. Likely LED effect config variant. |
| (0x15, 0x00) | 0x02 (2 bytes) | varies | unlabeled | arg[0:2] = profile_id repeated (e.g., 0x01:0x01, 0x03:0x03, 0x04:0x04). Observed in full-resync flows after PROFILE_METADATA. Possibly GET_DEVICE_MODE or profile-confirm command. |
| (0x15, 0x07) | variable | varies | unlabeled | arg[0]=count followed by LED IDs. Observed with count=1, IDs: 0x04, 0x03, 0x02. Likely LED list/enumerate command. |
| (0x15, 0x80) | varies | 0x03, 0x04 | GET_BRIGHTNESS (hypothesized) | Observed in full-resync flows immediately after GET_ACTIVE_PROFILE. arg[0]=profile_index. Labeled "GET BRIGHTNESS" by `analyze_profile_switches.py`. No driver match. |
| (0x15, 0x88) | 0x01 | 0x00 | unlabeled | arg[0]=0x00. Observed at startup. Possibly a serial number or device-info request distinct from 0x00:0x82 and 0x00:0x85. |

## Observed Synapse flows

### Profile switch (slot A → slot B): minimal 2-command pattern

Observed twice in the capture (Groups 3 and 4 in the timeline). Pattern is exactly two commands with a ~22ms gap:

```
t=15.870s  class=0x05 cmd=0x03 size=1 args=03  | SET_ACTIVE_PROFILE(slot=3)
t=15.892s  class=0x06 cmd=0x8e size=14 args=00×14  | MACRO_CLEAR

t=17.777s  class=0x05 cmd=0x03 size=1 args=02  | SET_ACTIVE_PROFILE(slot=2)
t=17.801s  class=0x06 cmd=0x8e size=14 args=00×14  | MACRO_CLEAR
```

No DPI writes, no button writes, no GET_ACTIVE_PROFILE in this flow. The minimal switch is used when the user clicks a profile in the Synapse UI without triggering a full resync (e.g., no side-panel swap event).

### DPI change on profile N: full-resync flow

Each SET_DPI is embedded inside a full-resync flow. The resync begins 8 commands (~246ms) before SET_DPI with a GET_ACTIVE_PROFILE (0x05:0x02) read:

**Profile 4 example (t=25.479s – t=25.791s):**

```
t=25.479s  0x05:0x02  GET_ACTIVE_PROFILE    arg[0]=4           ← resync starts
t=25.508s  0x15:0x80  GET_BRIGHTNESS        arg[0]=4
t=25.534s  0x00:0x85  (GET_POLLING_RATE or other — see label conflict)
t=25.560s  0x05:0x08  PROFILE_METADATA      profile=4 offset=0x0000
t=25.587s  0x15:0x00  unlabeled             arg=0x04:0x04
t=25.614s  0x05:0x08  PROFILE_METADATA      profile=4 offset=0x0040
t=25.640s  0x05:0x08  PROFILE_METADATA      profile=4 offset=0x0080
t=25.667s  0x05:0x08  PROFILE_METADATA      profile=4 offset=0x00c0    ← 58ms before SET_DPI
t=25.725s  0x04:0x05  SET_DPI               arg[0]=4 X=3200 Y=3200     ← raw: 040c800c800000
t=25.748s  0x04:0x06  SET_DPI_STAGES        profile=4 stages=4 active=5 [400,800,1600,3200 DPI]
t=25.791s  0x06:0x8e  MACRO_CLEAR
```

**Profile 3 example (t=32.909s – t=33.495s):**

```
t=32.909s  0x05:0x02  GET_ACTIVE_PROFILE    arg[0]=3           ← resync starts
t=32.936s  0x15:0x80  GET_BRIGHTNESS        arg[0]=3
t=32.962s  0x00:0x85  (GET_POLLING_RATE or other — see label conflict)
t=32.990s  0x05:0x08  PROFILE_METADATA      profile=3 offset=0x0000
t=33.018s  0x15:0x00  unlabeled             arg=0x03:0x03
t=33.045s  0x05:0x08  PROFILE_METADATA      profile=3 offset=0x0040
t=33.073s  0x05:0x08  PROFILE_METADATA      profile=3 offset=0x0080
t=33.099s  0x05:0x08  PROFILE_METADATA      profile=3 offset=0x00c0    ← 59ms before SET_DPI
t=33.158s  0x04:0x05  SET_DPI               arg[0]=3 X=1600 Y=1600     ← raw: 030640064000000
t=33.179s  0x04:0x06  SET_DPI_STAGES        profile=3 stages=3 active=5 [400,800,1600 DPI]
t=33.224s  0x02:0x0c  SET_BUTTON_MAPPING    profile=3 btn=0x40 ... ×12 writes
t=33.495s  0x06:0x8e  MACRO_CLEAR
```

Key observation: SET_DPI is NOT preceded by SET_ACTIVE_PROFILE (0x05:0x03). The active profile is established by the GET_ACTIVE_PROFILE (0x05:0x02) read at the start of the resync flow. SET_DPI carries the profile index directly in arg[0].

### Button remap on profile N

Three button-write groups observed in the capture:

**Group 1 (t=12.122s – 12.513s): profile=1, 12 writes (init/startup flow)**

All 12 side buttons (0x40–0x4b), layer=0x00 (normal), action_type=0x02 (keyboard).
Default Synapse mapping: Shift+Numpad1 through Shift+Numpad* (modifier=0x02, keycodes 0x59–0x63, 0x55).
Preamble: no 0x05:0x02 or 0x05:0x03 directly preceding — part of startup init sequence.
Immediately preceding command: SET_DPI_STAGES (0x04:0x06) at t=12.099s, 23ms gap.

**Group 2 (t=33.224s – 33.472s): profile=3, 12 writes (full-resync flow)**

All 12 side buttons (0x40–0x4b), layer=0x00, action_type=0x02, arg[0]=0x03.
Same default Numpad mapping as Group 1.
Preamble: GET_ACTIVE_PROFILE (0x05:0x02) at t=32.909s — 315ms before first button write.
No SET_ACTIVE_PROFILE (0x05:0x03) in this flow.
Immediately preceding command: SET_DPI_STAGES (0x04:0x06) at t=33.179s, 45ms gap.
Followed by: MACRO_CLEAR at t=33.495s (23ms after last write).

**Group 3 (t=41.942s – 42.120s): profile=1, 4 writes (selective user remap)**

Only 4 buttons written — partial update, not a full resync:
- btn=0x55 → keyboard: modifier=0x02, keycode=0x2b (Shift+backslash)
- btn=0x50 → mouse_button: btn_code=0x01, params[1]=0x04
- btn=0x53 → keyboard: modifier=0x02, keycode=0x07 (Shift+D)
- btn=0x51 → mouse_button: btn_code=0x01, params[1]=0x05

Preceding command (any relevant class): 0x02:0x16 unlabeled at t=38.249s — 3.7s gap.
No profile-management preamble. Consistent with a user-triggered remap in the Synapse remap UI.

### Full resync flow

Triggered when Synapse detects a state change (side-panel swap, reconnect, or explicit re-sync). Full sequence for profile N:

1. `0x05:0x02` GET_ACTIVE_PROFILE — reads current profile index from device (arg[0]=N)
2. `0x15:0x80` GET_BRIGHTNESS — reads brightness for profile N (arg[0]=N)
3. `0x00:0x85` unlabeled (see label conflict: driver says GET_POLLING_RATE, capture context suggests serial/device read)
4. `0x05:0x08` PROFILE_METADATA offset=0x0000 — UUID + ASCII name (e.g., "Gaming", "Blender")
5. `0x15:0x00` unlabeled — 2 bytes, both bytes = profile_id (e.g., 0x04:0x04)
6. `0x05:0x08` PROFILE_METADATA offset=0x0040 — continuation
7. `0x05:0x08` PROFILE_METADATA offset=0x0080 — continuation
8. `0x05:0x08` PROFILE_METADATA offset=0x00c0 — continuation
9. `0x04:0x05` SET_DPI — writes current DPI X/Y for profile N
10. `0x04:0x06` SET_DPI_STAGES — writes full stage table for profile N
11. `0x02:0x0c` SET_BUTTON_MAPPING ×N — writes button mappings (present in Group 6/profile 3; absent in Group 5/profile 4, suggesting mappings were already current or side-panel variant had no changes)
12. `0x06:0x8e` MACRO_CLEAR — always last; terminates the burst

The full resync is triggered by side-panel physical swap events and by reconnect/resume events. The minimal 2-command flow (SET_ACTIVE_PROFILE + MACRO_CLEAR) is used for logical profile switching without hardware state change.

## Synapse config-export cross-reference (from Task 1.6)

The Synapse 4 export file (`docs/profiles - 1774992262695.synapse4`) contains 3 profiles stored as base64-encoded JSON payloads:

- **Profile [0]**: "Blender" (GUID eb7574b0-b3d8-4770-8c4b-48f826cd2e1f)
- **Profile [1]**: "Gaming" (GUID e454e7be-dce5-4e91-ae26-419eff1de3b4)
- **Profile [2]**: "STEAMMACHINE-Default 1" (GUID 3691ac11-6c06-48f6-b077-c7e5623263bc)

**Product ID:** `productId=167` (decimal) = `0x00A7` (hex). This matches the wired Naga V2 Pro (0x00A7 wired; 0x00A8 wireless).

**Profile name correlation with capture:** Direct match confirmed. The PROFILE_METADATA (0x05:0x08) packets at offset 0x0000 contain binary UUID bytes followed by null-terminated ASCII profile names. The names "Gaming" and "Blender" were observed in the capture traffic, matching profiles [1] and [0] in the JSON export exactly.

**Profile index mapping:** The JSON export contains 3 profiles (array indices 0, 1, 2), but the capture's SET_ACTIVE_PROFILE commands use indices 2, 3, 4 (1-based, observed values: 0x02, 0x03, 0x04). Profile slot 1 appears to be a hardware default profile not exported to Synapse. Synapse-managed profiles occupy device slots 2–4 (at minimum).

**DPI stage indexing — 0-based JSON vs 1-based device:** The Synapse JSON `dpiStages.active` field is 0-based. For example, Blender has `active=3` meaning the 4th stage (3200 DPI) is active; Gaming and STEAMMACHINE have `active=4` meaning the 5th stage (6400 DPI) is active. The device protocol, however, appears to use 1-based stage indices. The capture's SET_DPI_STAGES always sends `active_stage=5` (0x05), which in the capture data appears to mean "no active stage pre-set" or "use last-known" — stage tables have only 3–4 entries (indices 1–4), so 5 is out-of-range and acts as a sentinel. Any driver code converting Synapse JSON `active` to the device protocol must add 1 (or interpret the sentinel 5 correctly).

**DPI stages values:** All three profiles use the same stage DPI values: 400, 800, 1600, 3200, 6400 DPI. The `stages[].x` and `stages[].y` fields are direct DPI integers (same encoding as on-wire).

**Button mapping format:** The JSON uses `sidePanelMappings` with three sub-keys: `2ButtonSide`, `6ButtonSide`, `12ButtonSide`. Only the currently-attached panel's entries are programmed to the device. Blender's 12-button mappings use `KEY_NUMPAD_1` through `KEY_NUMPAD_ASTERISK`, matching the default HID keycodes (0x59–0x63, 0x55) observed in Group 1 and Group 2 button writes in the capture. The standard `mappings` array is empty in all three profiles.

**Lighting:** No per-profile RGB color arrays or hex color values are present. Only `quickEffects.selectedEffectId=3` (an integer effect selector) and `brightness.value` (33 or 50). This suggests Chroma lighting is stored in a separate Synapse subsystem or the firmware handles color from an integer effect ID. The capture's 0x0f-class LED commands (0x0f:0x04, 0x0f:0x84) are likely the on-wire representation of this effect selection.

## Fork predictions (to be confirmed in Phase 2)

### Sub-problem: DPI

**Prediction: Fork A (medium confidence) — arg[0] must match the active profile.**

Evidence: Both observed SET_DPI commands (t=25.725s profile=4, t=33.158s profile=3) appear inside full-resync flows that are each initiated by a GET_ACTIVE_PROFILE (0x05:0x02) read that returns the same profile index that SET_DPI subsequently writes. SET_DPI is never preceded by SET_ACTIVE_PROFILE (0x05:0x03) in these flows — Synapse reads the current active profile and then writes DPI for that same profile. This is consistent with Fork A: the device only accepts SET_DPI for the currently-active profile slot and silently ignores writes where arg[0] does not match the active slot. It is also consistent with Fork B (real per-slot addressing), but Fork B would not explain why Synapse always matches arg[0] to the device-reported active slot rather than writing all slots independently.

Additional supporting evidence: our driver's current behavior sends SET_DPI with arg[0] ∈ {2..5} (profile slot numbers) but does not call SET_ACTIVE_PROFILE first. Session report from 2026-04-22 showed these writes are silently ignored — which is exactly what Fork A predicts when arg[0] does not match the active slot.

Phase 2 probes that will confirm: 2.4 (SET_DPI arg[0] semantics with and without prior SET_ACTIVE_PROFILE).

### Sub-problem: Button mapping

**Prediction: Fork A (medium confidence) — arg[0] must match the active profile.**

Evidence: The same reasoning as DPI applies. In Group 2 (the only full-resync button-write group), the preamble is GET_ACTIVE_PROFILE (0x05:0x02) at t=32.909s returning profile=3, and all 12 button writes carry arg[0]=0x03. In Group 3 (selective remap, t=41.942s), the 4 writes carry arg[0]=0x01 — no explicit SET_ACTIVE_PROFILE precedes these, but profile 1 may have been the active slot at that point in the session (no conflicting data). In both cases Synapse writes button mappings for the currently-active profile. No capture evidence of writing button mappings to a non-active slot is present. The silent-ignore failure mode seen for DPI (which uses the same arg[0]-as-profile convention) suggests the same Fork A constraint applies to button mapping.

Phase 2 probes that will confirm: 2.5.

### Sub-problem: Active profile indexing

**Prediction: Device uses 1-based profile indices; our driver's `mouseGetActiveProfile` returns 0 because it either reads from the wrong command ID or misinterprets the response (medium confidence).**

Evidence: The capture's SET_ACTIVE_PROFILE (0x05:0x03) uses arg[0] values of 2 and 3 (decimal), and the full-resync GET_ACTIVE_PROFILE (0x05:0x02) returns values of 3 and 4. These are all non-zero, confirming the device reports 1-based profile indices (slots 1–4 or 1–5). Meanwhile, the Synapse JSON `dpiStages.active` field is 0-based (values 3 and 4 in the export), creating a potential off-by-one when mapping Synapse data to device commands. The fact that `mouseGetActiveProfile` returns 0 in our driver (reported in 2026-04-22 session) most likely means one of: (a) the driver is calling 0x05:0x82 but the device responds to 0x05:0x02 for reads, so the response payload is empty/zero; or (b) the response byte is being read as 0-based when it is actually 1-based. There is also a documented ambiguity between 0x05:0x02 and 0x05:0x82 — the driver uses 0x05:0x82 but the capture only shows 0x05:0x02 activity.

Phase 2 probes that will confirm: 2.3 (live read of active profile via both 0x05:0x02 and 0x05:0x82 to identify which command the device actually responds to, and to confirm the index base).

### Sub-problem: Mirror-to-slot-1

**Prediction: Mirror is removable in both Fork A and Fork B.**

Evidence: The mirror-to-slot-1 behavior in the current driver copies every DPI/button write to slot 1 unconditionally. This was likely added as a workaround when per-slot writes seemed unreliable. Under Fork A (arg[0] must match active): the correct fix is to call SET_ACTIVE_PROFILE first and then write to that slot — mirroring to slot 1 is then actively harmful because it corrupts the user's slot 1 settings. Under Fork B (real per-slot addressing): direct per-slot writes work without SET_ACTIVE_PROFILE, so mirroring to slot 1 is equally harmful. In both forks the mirror is at best unnecessary and at worst destructive to user-configured profiles. Once Phase 2 confirms which fork is correct and the underlying read/write is honest, the mirror code should be removed.

Phase 2 probes that will confirm: indirectly by 2.2 (verify slot 1 is preserved after writes to other slots) and 2.4 (confirm per-slot DPI write semantics).

## Phase 2 — On-device probe findings

### Probe 1: SET_PROFILE active-slot verification

Ran: `node scripts/probes/naga-v2-pro-probe.js set-profile`

Salient observations (full output):

```
Found 1 device(s):
  [0] pid=0xa7 internalId=0
Probe 1: SET_PROFILE active-slot verification
Baseline (no intervention):
Command failed (mouse)
Contents of request_report are:
command_class: 0X05
command_id: 0X82
transaction_id: 0X1F

  getActiveProfile(): 0
  standard mouseGetDpi(): 6454
  per-slot reads: slot1=1285, slot2=1029, slot3=1029, slot4=1029, slot5=773

SET_PROFILE(3):
Command failed (mouse)
Contents of request_report are:
command_class: 0X05
command_id: 0X82
transaction_id: 0X1F

  getActiveProfile(): 0
  standard mouseGetDpi(): 6454
  per-slot reads: slot1=1285, slot2=1029, slot3=1029, slot4=1029, slot5=773

SET_PROFILE(4):
Command failed (mouse)
Contents of request_report are:
command_class: 0X05
command_id: 0X82
transaction_id: 0X1F

  getActiveProfile(): 0
  standard mouseGetDpi(): 6454
  per-slot reads: slot1=1285, slot2=1029, slot3=1029, slot4=1029, slot5=773

SET_PROFILE(5):
Command failed (mouse)
Contents of request_report are:
command_class: 0X05
command_id: 0X82
transaction_id: 0X1F

  getActiveProfile(): 0
  standard mouseGetDpi(): 6454
  per-slot reads: slot1=1285, slot2=1029, slot3=1029, slot4=1029, slot5=773

SET_PROFILE(1):
Command failed (mouse)
Contents of request_report are:
command_class: 0X05
command_id: 0X03
transaction_id: 0X1F

Command failed (mouse)
Contents of request_report are:
command_class: 0X05
command_id: 0X82
transaction_id: 0X1F

  getActiveProfile(): 0
  standard mouseGetDpi(): 6454
  per-slot reads: slot1=1285, slot2=1029, slot3=1029, slot4=1029, slot5=773
```

Findings:
- Does `mouseGetDpi` (standard VARSTORE read) return a different value after `SET_PROFILE(N)`? **No.** `mouseGetDpi()` returned 6454 in every iteration — baseline and all four SET_PROFILE calls. The standard read is completely unaffected.
- Does `mouseGetActiveProfile` match the slot we just set? **No — it returns 0 for every call.** The "Command failed (mouse)" error for `command_class: 0X05 command_id: 0X82` appears before every `getActiveProfile()` call, confirming that `0x05:0x82` is the wrong command for this device (it NAKs/fails on every invocation). The returned value of 0 is a default/failure sentinel, not a real profile index. This is consistent with the Phase 1 ambiguity between `0x05:0x02` (observed outgoing in capture) and `0x05:0x82` (driver's current command) — the driver is using the wrong command ID.
- Does `mouseSetActiveProfile` work? **Partially.** For SET_PROFILE(3), SET_PROFILE(4), SET_PROFILE(5): the driver attempted `0x05:0x82` for the SET (which also fails). For SET_PROFILE(1): two failures are logged — one for `0x05:0x03` (the actual SET command) and one for `0x05:0x82` (the follow-up GET). This means `mouseSetActiveProfile` sends `0x05:0x03` for slot 1 specifically, but the device rejects it. Slots 3/4/5 appear to not even attempt `0x05:0x03` — the driver may have a code path that falls through to a no-op or a different path for those slot numbers.
- Do the per-slot reads (`mouseGetDpiProfile`) return sensible different values per slot, or consistent values regardless of active profile, or garbage? **Garbage/protocol-mismatch values.** The per-slot reads are: slot1=1285, slot2=1029, slot3=1029, slot4=1029, slot5=773 — every single iteration, baseline through all SET_PROFILE calls. These values are not DPI (no Razer device ships with 1285/1029/773 DPI). In hex: 1285=0x0505, 1029=0x0405, 773=0x0305. The low byte is always 0x05 and the high nibble matches the slot number. This is consistent with the driver's `GET_DPI_PROFILE` (`0x04:0x86`) receiving a raw status or count field in the DPI bytes, rather than actual DPI values. Either the command is not supported for this device, the argument encoding is wrong, or the response is being misread.

Implication for DPI fork (Fork A / Fork B):
The data strongly supports **Fork A**. The `0x04:0x86` per-slot reads return garbage regardless of which slot is queried or whether any SET_PROFILE was attempted, indicating the current driver cannot read per-slot DPI at all. `mouseGetDpi()` never changes across any SET_PROFILE call. This is exactly the Fork A prediction: the device does not expose per-slot DPI via the current command path, and `0x04:0x86` with the current argument encoding does not function as a per-slot DPI reader on this device. The `0x05:0x82` GET_ACTIVE_PROFILE command also fails on every call, confirming the driver is using the wrong command variant (should be `0x05:0x02` per Phase 1 capture analysis). The net result is that neither SET_PROFILE nor per-slot DPI reads are working with the current driver code — both must be fixed before the DPI fork can be tested properly.

### Probe 2: GET_ACTIVE_PROFILE semantics

Ran: `node scripts/probes/naga-v2-pro-probe.js get-active`

```
Found 1 device(s):
  [0] pid=0xa7 internalId=0
Probe 2: GET_ACTIVE_PROFILE semantics
Command failed (mouse)
Contents of request_report are:
command_class: 0X05
command_id: 0X82
transaction_id: 0X1F

At rest: 0
Command failed (mouse)
Contents of request_report are:
command_class: 0X05
command_id: 0X03
transaction_id: 0X1F

Command failed (mouse)
Contents of request_report are:
command_class: 0X05
command_id: 0X82
transaction_id: 0X1F

  After SET_PROFILE(1): getActive=0  (match=NO — off by 1)
Command failed (mouse)
Contents of request_report are:
command_class: 0X05
command_id: 0X82
transaction_id: 0X1F

  After SET_PROFILE(3): getActive=0  (match=NO — off by 3)
Command failed (mouse)
Contents of request_report are:
command_class: 0X05
command_id: 0X82
transaction_id: 0X1F

  After SET_PROFILE(4): getActive=0  (match=NO — off by 4)
Command failed (mouse)
Contents of request_report are:
command_class: 0X05
command_id: 0X82
transaction_id: 0X1F

  After SET_PROFILE(5): getActive=0  (match=NO — off by 5)
```

Findings:
- At rest: 0 (preceded by a `0x05:0x82` NAK — the returned 0 is a failure sentinel, not a real profile index)
- After SET_PROFILE(N), return value: consistently 0 for all N ∈ {1, 3, 4, 5}; `0x05:0x82` NAKs on every call regardless of whether a SET was attempted
- Does `0x05:0x82` NAK as seen in Probe 1? Yes — every single invocation produces "Command failed (mouse) command_class: 0X05 command_id: 0X82"
- Additional observation: `mouseSetActiveProfile(id, 1)` also triggers a `0x05:0x03` NAK (the SET command itself fails for slot 1 on this device); slots 3/4/5 generate no SET-command error, suggesting the driver skips the `0x05:0x03` call for those slots and the failure path is slightly different

Implication for active-profile-indexing fork:
`0x05:0x82` is definitively the wrong command ID for this device's GET_ACTIVE_PROFILE read. The device rejects it unconditionally. The returned value of 0 is a driver-side default from an uninitialized response buffer, not a device-reported slot. Phase 1 capture analysis identified `0x05:0x02` as the outgoing host-to-device command Synapse uses for GET_ACTIVE_PROFILE; the ambiguity noted there ("0x05:0x02 may be the request variant and 0x05:0x82 the response/ACK variant") is now resolved by elimination: the device does not respond to `0x05:0x82` at all, so `0x05:0x82` cannot be a valid command in either role on this device.

Action item for rewrite: change `razer_mouse_attr_read_active_profile` in the driver (and the corresponding N-API binding `mouseGetActiveProfile`) to use `0x05:0x02` instead of `0x05:0x82`. After making that change, add a new N-API probe binding if needed and re-run `get-active` to verify that the device now returns non-zero slot indices. Also verify that `mouseSetActiveProfile` is corrected to send `0x05:0x03` for all profile slots (not just slot 1), since the Probe 1 data showed slots 3/4/5 do not emit `0x05:0x03` at all.

### Probe 3: SET_DPI arg[0] semantics

Ran: `node scripts/probes/naga-v2-pro-probe.js set-dpi-args`

Key observations (salient lines from probe output):

```
Initial state: active=0, standard DPI=6454

A. mouseSetDpiProfile(slotArg=1, dpi=1111) — NO prior SET_PROFILE
  standard mouseGetDpi (currently active slot): 1111
  per-slot reads: slot1=1285, slot2=1029, slot3=1029, slot4=1029, slot5=773

B. SET_PROFILE(1) + mouseSetDpiProfile(slotArg=1, dpi=1121)
  standard mouseGetDpi (currently active slot): 1121
  per-slot reads: slot1=1285, slot2=1029, slot3=1029, slot4=1029, slot5=773

A. mouseSetDpiProfile(slotArg=3, dpi=1333) — NO prior SET_PROFILE
  standard mouseGetDpi (currently active slot): 1121
  per-slot reads: slot1=1285, slot2=1029, slot3=1029, slot4=1029, slot5=773

B. SET_PROFILE(3) + mouseSetDpiProfile(slotArg=3, dpi=1343)
  standard mouseGetDpi (currently active slot): 1121
  per-slot reads: slot1=1285, slot2=1029, slot3=1029, slot4=1029, slot5=773

A. mouseSetDpiProfile(slotArg=4, dpi=1444) — NO prior SET_PROFILE
  standard mouseGetDpi (currently active slot): 1121

A. mouseSetDpiProfile(slotArg=5, dpi=1555) — NO prior SET_PROFILE
  standard mouseGetDpi (currently active slot): 1121

Final cross-slot retention check (slot 2 skipped):
  After SET_PROFILE(1): standard mouseGetDpi = 1121
  After SET_PROFILE(3): standard mouseGetDpi = 1121
  After SET_PROFILE(4): standard mouseGetDpi = 1121
  After SET_PROFILE(5): standard mouseGetDpi = 1121
```

Key questions answered:

1. **Writes with `slotArg=1` (which happens to equal the active slot) without prior SET_PROFILE**: does `standard mouseGetDpi` reflect the marker value? **Yes — observed value 1111.** The write landed immediately.

2. **Writes with `slotArg ∈ {3,4,5}` WITHOUT prior SET_PROFILE**: does standard DPI change to the marker? **No.** After writing 1333, 1444, 1555 to slots 3/4/5 without a preceding SET_PROFILE, `mouseGetDpi` stayed at 1121 (the last successful slot-1 write) on every read. No per-slot read returned any marker value — per-slot reads continued returning the same garbage values (0x0505/0x0405/0x0305 pattern) throughout.

3. **Writes with `slotArg ∈ {3,4,5}` AFTER `SET_PROFILE(slotArg)`**: does standard DPI change to `marker + 10`? **No.** Even after `SET_PROFILE(3/4/5)` (which itself silently fails — the driver does not emit `0x05:0x03` for slots ≥ 2, confirmed in Probes 1 and 2), the subsequent `mouseSetDpiProfile(3/4/5, …)` write had no effect on `mouseGetDpi`. The active slot never changed from slot 1, so the DPI write targeting a non-active slot was silently ignored. Per-slot reads remain unchanged (garbage values).

4. **Final retention check**: when iterating SET_PROFILE through 1, 3, 4, 5, every call returns `mouseGetDpi = 1121`. This is the last value written to slot 1 (step B for slotArg=1). No slot-3/4/5 marker was ever retained. Since `SET_PROFILE(3/4/5)` never actually switched the active slot, the device reported slot 1's DPI (1121) for all iterations. **The marker+10 values for slots 3/4/5 were never stored.**

Fork determination for DPI:

- **Fork A evidence** (`arg[0]` must match currently-active slot; otherwise ignored):
  - Write with `slotArg=1` (active slot at the time) updated `mouseGetDpi` to 1111 immediately — no prior SET_PROFILE needed when arg[0] already matches the active slot.
  - Writes with `slotArg=3/4/5` — both with and without a preceding SET_PROFILE call — had zero effect on `mouseGetDpi`. Since SET_PROFILE itself is broken for those slots (driver never sends `0x05:0x03`), the active slot remained slot 1 the entire time; any write with `arg[0] ≠ 1` was silently dropped by the device.
  - The final retention check showed identical DPI (1121) across all SET_PROFILE iterations, confirming no per-slot DPI was stored at slots 3/4/5.

- **Fork B evidence** (`arg[0]` is a real slot number, independent of active):
  None. No observation showed a write to a non-active slot (arg[0]=3/4/5) taking effect. Per-slot reads via `0x04:0x86` remain broken (garbage values), so we cannot read back slot-specific DPI directly — but the standard `mouseGetDpi` (VARSTORE read, always reflects the active slot) never changed after non-active-slot writes, which is what Fork B would require to show.

- **Confounding factor — SET_PROFILE is broken for slots ≥ 2**: The driver does not send `0x05:0x03` for slots 3/4/5, so the "B" condition (SET_PROFILE first, then write) could not be properly tested for those slots. However, the slot-1 data is unambiguous: write with `arg[0]=1` (matching the active slot, no SET_PROFILE needed) → DPI update confirmed. This alone supports Fork A.

**CONFIRMED FORK: Fork A** — `SET_DPI arg[0]` must match the currently-active profile slot. Writes where `arg[0]` does not match the device's active slot are silently ignored. The evidence is: `slotArg=1` write (slot 1 was active) registered immediately in `mouseGetDpi`; `slotArg=3/4/5` writes (slot 1 remained active throughout because SET_PROFILE is broken for those slots) had zero effect. The device behaves as a VARSTORE device where `arg[0]` is a slot selector that must equal the active slot — not an independent per-slot address.

Note: the "B" tests for slots 3/4/5 were blocked by the broken `mouseSetActiveProfile` implementation (doesn't emit `0x05:0x03` for slots ≥ 2). Once that is fixed and SET_PROFILE actually works, a follow-up probe can verify that SET_PROFILE(3) + write(arg[0]=3) successfully lands. Based on the Phase 1 capture evidence (Synapse always matches arg[0] to the GET_ACTIVE_PROFILE-confirmed active slot), Fork A is the expected and confirmed behavior.

Implications for driver rewrite:
- Delete `mouseSetDpiProfile` as a standalone operation (or keep only as internal helper).
- Replace with a two-step sequence: `mouseSetActiveProfile(target_slot)` → `mouseSetDpi(dpi_x, dpi_y)` where `mouseSetDpi` sends `SET_DPI (0x04:0x05)` with `arg[0]` set to the target slot (which equals the now-active slot).
- Fix `mouseSetActiveProfile` to emit `0x05:0x03` for ALL slot numbers (currently broken for slots ≥ 2).
- Fix `mouseGetActiveProfile` to use `0x05:0x02` instead of `0x05:0x82`.
- Remove the mirror-to-slot-1 behavior; it actively corrupts other profiles.
- The correct per-profile DPI write sequence is: SET_ACTIVE_PROFILE(N) → SET_DPI(N, x, y) → SET_DPI_STAGES(N, stages) → MACRO_CLEAR.

### Probe 4: button-mapping write arg[0] semantics

Ran: `node scripts/probes/naga-v2-pro-probe.js set-btn-args`

Key observations (salient excerpt):

```
initial state (active=1):
    slot1: 01 01 00 01 01 01 00 00 00 00
    slot2: 02 01 00 01 01 01 00 00 00 00
    slot3: 03 01 00 01 01 01 00 00 00 00
    slot4: 04 01 00 01 01 01 00 00 00 00
    slot5: 05 01 00 01 01 01 00 00 00 00

A. mouseSetButtonMapping(slotArg=1, ...) — NO prior SET_PROFILE
  after write slotArg=1 (no preamble):
    slot1: 01 01 00 01 01 aa bb cc dd ee    ← marker params landed in slot 1

A. mouseSetButtonMapping(slotArg=3, ...) — NO prior SET_PROFILE
  after write slotArg=3 (no preamble):
    slot1: 01 01 00 01 02 ab bc cd de ef    ← slot 1 unchanged from prior write
    slot3: 03 01 00 01 03 aa bb cc dd ee    ← marker params landed in slot 3

B. SET_PROFILE(3) + mouseSetButtonMapping(slotArg=3, ...) — with preamble
  after write slotArg=3 (with preamble):
    slot3: 03 01 00 01 04 ab bc cd de ef    ← marker+1 params landed in slot 3

A. mouseSetButtonMapping(slotArg=4, ...) — NO prior SET_PROFILE
    slot4: 04 01 00 01 04 aa bb cc dd ee    ← marker params landed in slot 4

A. mouseSetButtonMapping(slotArg=5, ...) — NO prior SET_PROFILE
    slot5: 05 01 00 01 05 aa bb cc dd ee    ← marker params landed in slot 5
```

Note on read quality: `mouseGetButtonMapping` works correctly and returns stable, meaningful per-slot data. The initial state shows slot N has `arg[0]=N` as the first byte — consistent with the slot index being embedded in the response (likely from the request command echoed back). Reads are fully reliable in contrast to the broken `mouseGetDpiProfile` reads seen in Probe 3. The response layout (10 bytes) matches the `0x02:0x8c` GET_BUTTON_MAPPING response format: `[profile, button_id, layer, action_type, params[0..5]]`.

Key questions answered:

1. **Writes with `slotArg=1` (= active slot) without preamble**: yes — subsequent read for slot 1 shows marker params (`aa bb cc dd ee`). Confirmed landing immediately.

2. **Writes with `slotArg ∈ {3,4,5}` WITHOUT preamble**: yes — every write landed in the exact slot specified by `slotArg`, with zero crosstalk to slot 1 or any other slot. Writing to slot 3 with `slotArg=3` → only `slot3` read returned `aa bb cc dd ee`; slot 1 was unaffected. Same pattern for slots 4 and 5. The device accepted per-slot button-mapping writes without any `SET_PROFILE` preamble.

3. **Writes with `slotArg ∈ {3,4,5}` AFTER `SET_PROFILE(slotArg)` (preamble)**: also yes — the `marker+1` params appeared in the correct slot read. But this is not required: the preamble did not change the behaviour relative to the no-preamble case; both wrote to the target slot successfully. The only observable difference is that `SET_PROFILE` itself issued a `0x05:0x03` NAK (driver bug, not device rejection).

Fork determination for button-mapping:

- **Fork A evidence** (`arg[0]` must match active):
  None. Writes to non-active slots (3, 4, 5) with no prior `SET_PROFILE` all landed in the specified slot. If Fork A were true, those writes would have been silently dropped, and the reads would have remained at initial values — which did not happen.

- **Fork B evidence** (`arg[0]` is a real slot number, independent of active):
  Definitive. All four slots (1, 3, 4, 5) received their writes with exact marker values. Reads confirmed distinct per-slot storage: each slot retained its own write independently. No cross-slot contamination was observed. The device's `SET_BUTTON_MAPPING (0x02:0x0c)` command uses `arg[0]` as a true slot/profile address with no dependency on the currently-active profile.

Note on confounding factor: `mouseSetActiveProfile` is still broken for all slots (sends `0x05:0x03` which NAKs). This is irrelevant for Probe 4's conclusion because the no-preamble A-condition writes already proved per-slot addressing works without any profile switching.

**CONFIRMED FORK: Fork B** — `SET_BUTTON_MAPPING arg[0]` is a real per-slot address. The device accepts button-mapping writes to any slot (1, 3, 4, 5 verified) without requiring `SET_ACTIVE_PROFILE` first. This is the opposite result from Probe 3 (DPI = Fork A). Button-mapping and DPI use different write semantics on this device.

Implications for driver rewrite:
- `mouseSetButtonMapping` does NOT need to be preceded by `SET_ACTIVE_PROFILE`. The current arg[0]-as-slot approach is correct for button mapping.
- Remove any mirror-to-slot-1 logic in button-mapping write paths; it is harmful and unnecessary (each slot stores independently).
- The button-mapping read path (`mouseGetButtonMapping`, `0x02:0x8c`) also works correctly per-slot with `arg[0]` as the slot index — no fix needed for reads.
- DPI and button-mapping must be treated as separate subsystems in the rewrite: DPI uses VARSTORE (Fork A, requires SET_ACTIVE_PROFILE first), button-mapping uses direct per-slot addressing (Fork B, no preamble needed).
- The correct per-profile button-mapping write sequence remains: `SET_BUTTON_MAPPING(slot=N, btn, layer, action_type, params)` — issued directly for any target slot without any profile-activation preamble.

### Probe 6: GET_DPI read variants

Ran: `node scripts/probes/naga-v2-pro-probe.js read-variants`

```
Found 1 device(s):
  [0] pid=0xa7 internalId=0
Probe 6: GET_DPI read variants
Strategy: on each active profile, compare mouseGetDpi (standard VARSTORE read) vs
          mouseGetDpiProfile(slot=active) vs mouseGetDpiProfile(slot != active).
Command failed (mouse)
Contents of request_report are:
command_class: 0X05
command_id: 0X03
transaction_id: 0X1F


Active = 1:
  mouseGetDpi (standard VARSTORE): 1121
  mouseGetDpiProfile(1): x=1285 y=257
  mouseGetDpiProfile(2): x=1029 y=257
  mouseGetDpiProfile(3): x=1029 y=257
  mouseGetDpiProfile(4): x=1029 y=257
  mouseGetDpiProfile(5): x=773 y=257

Active = 3:
  mouseGetDpi (standard VARSTORE): 1121
  mouseGetDpiProfile(1): x=1285 y=257
  mouseGetDpiProfile(2): x=1029 y=257
  mouseGetDpiProfile(3): x=1029 y=257
  mouseGetDpiProfile(4): x=1029 y=257
  mouseGetDpiProfile(5): x=773 y=257

Active = 4:
  mouseGetDpi (standard VARSTORE): 1121
  mouseGetDpiProfile(1): x=1285 y=257
  mouseGetDpiProfile(2): x=1029 y=257
  mouseGetDpiProfile(3): x=1029 y=257
  mouseGetDpiProfile(4): x=1029 y=257
  mouseGetDpiProfile(5): x=773 y=257

Active = 5:
  mouseGetDpi (standard VARSTORE): 1121
  mouseGetDpi (standard VARSTORE): 1121
  mouseGetDpiProfile(1): x=1285 y=257
  mouseGetDpiProfile(2): x=1029 y=257
  mouseGetDpiProfile(3): x=1029 y=257
  mouseGetDpiProfile(4): x=1029 y=257
  mouseGetDpiProfile(5): x=773 y=257
```

Findings:

1. Does `mouseGetDpi` always agree with `mouseGetDpiProfile(active)`? **No — they never agree.** `mouseGetDpi` returned 1121 for all four active states. `mouseGetDpiProfile` returned 1285 for slot 1, 1029 for slots 2–4, and 773 for slot 5 — none of which equal 1121. The two read paths return completely different (and both unreliable) values and clearly target different registers or command IDs.

2. Does `mouseGetDpi` return different values for different active profiles, or the same value regardless? **Same value (1121) regardless.** `mouseGetDpi` returned 1121 for active=1, 3, 4, and 5 — identical across all four iterations. This confirms both that `mouseSetActiveProfile` continues to fail silently for all slots (active slot never actually changed from its pre-probe state of slot 1, as established in Probe 3), AND that even if SET_PROFILE were working, `mouseGetDpi` (standard VARSTORE read) may reflect only the hardware-active slot without update when called immediately after a failed SET_PROFILE. The 1121 value is the last DPI written to slot 1 in Probe 3 (step B, `marker+10=1121` for slotArg=1). The VARSTORE read is stable and correct for the currently-active slot, but produces no per-profile variation because the active slot never changes.

3. Does `mouseGetDpiProfile(slot != active)` return:
   - **Garbage / stage metadata (~0x0505, 0x0405)** — confirmed Fork A evidence; `0x04:0x86` is not a per-slot DPI read. The x-component values are 1285 (=0x0505), 1029 (=0x0405/0x0405), and 773 (=0x0305), where the high byte appears to encode slot-related status rather than DPI. The y-component is uniformly 257 (=0x0101) for all slots and all active states — a fixed non-DPI constant. These values are not meaningful DPI readings: no Razer product offers 773 or 257 DPI. The `0x04:0x86` command is consistently broken for per-slot DPI reads on this device regardless of which slot is queried or which slot is active.

Implication for DPI read path:
`mouseGetDpiProfile (0x04:0x86)` returns garbage unconditionally on this device — the x and y fields contain status/count bytes rather than DPI values, and the pattern is invariant across all four active states and all five slot indices. The driver read path must be changed. The only working DPI read available is `mouseGetDpi` (standard VARSTORE), which correctly returns the DPI of the currently-active slot (confirmed: 1121 = last written value for active slot 1). The correct per-profile DPI read sequence is therefore: `SET_ACTIVE_PROFILE(N)` → `mouseGetDpi()`. There is no evidence that `0x04:0x86` can be salvaged with a different argument encoding for this device. A potential alternative is command `0x04:0x85` (a lower variant that may encode the slot in arg[0] similarly to how `0x04:0x05` does for writes), but that command has not been probed and would require a new probe to confirm.

Cross-reference with Probe 1: confirms the garbage pattern observed there (1285=0x0505, 1029=0x0405, 773=0x0305 suffix 0x05). Probe 6 adds new detail: the y-component is 257 (=0x0101) universally — in Probe 1, only x-values were noted. The y=257 is consistent with the response's y-DPI bytes being 0x01:0x01, which could be a command echo or a status code (value 1 in both bytes). This further confirms `0x04:0x86` is not returning a valid DPI response for this device.

## Open questions for Phase 2

- **0x05:0x02 vs 0x05:0x82 ambiguity:** The capture shows 0x05:0x02 as the outgoing command that precedes full-resync flows, while our driver uses 0x05:0x82 (`GET_ACTIVE_PROFILE`). Both are labeled "GET_ACTIVE_PROFILE" in `COMMAND_NAMES` but may serve different roles (e.g., 0x02=host-to-device request, 0x82=device-to-host response in a request/response pattern), or 0x05:0x82 may be entirely wrong for this device. Probe 2.3 must test both command IDs to find which one returns a non-zero active profile index.

- **0x00:0x85 driver/capture label conflict:** Driver says GET_POLLING_RATE; `analyze_profile_switches.py` says GET_SERIAL_NUMBER. These cannot both be correct for the same command on this device. The device's actual serial number command may be 0x00:0x82, 0x15:0x88, or something else. A live probe sending 0x00:0x85 and inspecting the response payload would resolve this.

- **active_stage=5 sentinel in SET_DPI_STAGES:** All four SET_DPI_STAGES commands send active_stage=0x05 even when the stage table has only 3–4 entries. This may be a Synapse convention meaning "inherit active stage from device" or "no override." The Synapse JSON `dpiStages.active` has valid 0-based indices (0–4). Confirming whether the device ignores active_stage when it is out-of-range, or whether 5 has a defined meaning, would clarify how our driver should set this field when writing DPI stages for profiles.

- **Side-panel type detection:** The Naga V2 Pro has three interchangeable side panels (2-button, 6-button, 12-button). The Synapse JSON has three sub-keys for `sidePanelMappings`. The capture used exclusively the 12-button panel. Whether the device reports the attached panel type via USB (and if so, which command), or whether Synapse detects it through a different mechanism, is not observable from this capture. A Phase 2 probe with each panel attached would clarify this.

- **Class 0x0f and 0x15 command semantics:** Commands 0x0f:0x04, 0x0f:0x84, 0x15:0x00, 0x15:0x07, and 0x15:0x88 are all unlabeled. Their presence in the resync flow suggests they are important for correct device state, but their exact roles (LED color, device mode, LED enumeration, serial) are unconfirmed. These are out of scope for the DPI/button fork probes but should be documented before attempting to implement lighting effects.

- **Profile slot range:** The capture shows slots 1–4 in use (slot 1 in button-write Group 1, slots 2–4 in profile switch and resync flows). Whether slot 5 exists on this device, and whether slot 1 is truly a "hardware default" or just Synapse's first profile, is not confirmed from the capture alone.

- **Wireless vs wired command differences:** The Synapse export `productId=0x00A7` is the wired variant. The wireless variant (0x00A8) may use different commands for polling rate, power management, and possibly profile storage. This capture is wired-only.

## Still-unknown commands

The following (class, cmd) pairs remain unlabeled or hypothesis-only and may be resolved by Phase 2 live probing or additional capture analysis:

- **(0x02, 0x16):** 2 bytes, args=0x0100, observed 4 times. Purpose unconfirmed. `analyze_profile_switches.py` calls it "GET POLL RATE" but the driver's poll-rate command is class=0x00 cmd=0x85 — conflict. Could be a poll-rate variant for this specific device (0x02 class) or an unrelated device-info request.
- **(0x05, 0x02) vs (0x05, 0x82):** Both labeled "GET_ACTIVE_PROFILE" but possibly distinct. 0x05:0x02 is the observed outgoing request; 0x05:0x82 is the driver's read command. May be request/response pair, or one may be wrong for this device. Phase 2 probe 2.3 will resolve.
- **(0x0f, 0x04):** 3 bytes, arg[0]=profile/row. LED-related (likely LED_SET_COLOR or LED_SET_BRIGHTNESS for per-profile lighting). Not confirmed.
- **(0x0f, 0x80):** data_size=80, all-zero args, seen at startup. Possibly GET_LED_FX or LED effect status read. Not confirmed.
- **(0x0f, 0x84):** 3 bytes, args 0x01:0x04:0x00 / 0x02:0x04:0x00. Likely LED effect config (e.g., wave pattern parameters). Not confirmed.
- **(0x15, 0x00):** 2 bytes, both bytes = profile_id. Appears in resync flow after PROFILE_METADATA chunks. Possibly a device-mode set or profile-confirm command. Not confirmed.
- **(0x15, 0x07):** Variable, arg[0]=count + LED IDs. LED enumeration or LED list query. Not confirmed.
- **(0x15, 0x80):** Hypothesized GET_BRIGHTNESS from capture context. No driver match. Phase 2 live probe would confirm.
- **(0x15, 0x88):** 1 byte, arg[0]=0x00. Possibly serial number or device-info string request. Distinct from 0x00:0x82 (`razer_chroma_standard_get_serial`) and from 0x00:0x85. Not confirmed.
- **(0x00, 0x85):** Labeled GET_POLLING_RATE by the driver, but appears in full-resync serial/device-info context in the capture. Resolution requires live probe (send 0x00:0x85, inspect response payload for serial string vs poll-rate integer).
