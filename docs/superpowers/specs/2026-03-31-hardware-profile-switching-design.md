# Hardware Profile Switching

## Problem

The Razer Naga V2 Pro supports 5 on-board profile slots, but the macOS app hardcodes `profile = 0x01` for all button mapping and DPI operations. Users cannot read, switch, or edit different hardware profiles. Only Razer Synapse on Windows can manage on-board profiles.

## Solution

Un-hardcode the profile byte throughout the stack, add driver functions for profile get/set, and add a profile slot selector to the button mapping UI.

## Hardware Profile Architecture

Based on USB capture analysis (`docs/specs/naga-v2-pro-profile-switching-analysis.md`):

- **Slot 1** — "Hybrid/live" profile. The firmware dispatches button presses from this slot. Synapse mirrors the active profile's bindings here on every switch.
- **Slots 2–5** — On-board storage slots (red, green, blue, cyan indicator LEDs). Persist in device flash.
- **Profile switching** requires writing button mappings to both the target slot AND slot 1.

### Key Protocol Commands

| Command | Class:ID | Data Size | Description |
|---|---|---|---|
| Get Active Profile | `0x05:0x02` | 1 | Read active profile slot (1–5). Response echoes back as `0x05:0x82` (high bit set = response). |
| Set Active Profile | `0x05:0x03` | 1 | Switch to slot / clear slot |
| Profile Data | `0x05:0x08` | 69/63 | Write profile metadata (4 chunks) — not needed for this pass |
| Set DPI | `0x04:0x05` | 7 | Per-profile DPI (profile byte in arg[0]) |
| Get DPI | `0x04:0x86` | 80 | Per-profile DPI read (profile byte in arg[0]). Note: the existing codebase uses `0x04:0x85` in `razer_chroma_misc_get_dpi_xy`, which hardcodes profile `0x01`. The USB capture shows `0x04:0x86` for per-profile DPI reads. Implementation should try `0x86` first (matching the capture); if it fails, fall back to `0x85` with the profile byte in arg[0]. |
| DPI Stages | `0x04:0x06` | 38 | Per-profile DPI stages |
| Button Write | `0x02:0x0c` | 10 | Per-profile button mapping (profile byte in arg[0]) |
| Button Read | `0x02:0x8c` | 10 | Per-profile button mapping read |
| Macro Clear | `0x06:0x8e` | 14 | Clear macro buffer — follows every profile operation |

## Driver Layer Changes

### New C Functions (`librazermacos/src/lib/razermouse_driver.c`)

**`razer_mouse_attr_read_active_profile`** — sends `get_razer_report(0x05, 0x02, 0x01)`, returns 1-byte profile slot number from the response.

**`razer_mouse_attr_write_active_profile`** — sends `get_razer_report(0x05, 0x03, 0x01)` with `arguments[0] = slot`. Sets the active on-board profile.

**`razer_mouse_attr_write_macro_clear`** — sends `get_razer_report(0x06, 0x8e, 0x0e)` with all-zero arguments. Clears macro buffer.

**`razer_mouse_attr_read_dpi_profile`** — sends `get_razer_report(0x04, 0x86, 0x07)` with `arguments[0] = profile`. Returns DPI X/Y for the specified profile. Required because existing `razer_chroma_misc_get_dpi_xy` hardcodes `0x01`.

**`razer_mouse_attr_write_dpi_profile`** — sends `get_razer_report(0x04, 0x05, 0x07)` with `arguments[0] = profile`, `arguments[1..2] = X DPI`, `arguments[3..4] = Y DPI`. Required because existing `razer_chroma_misc_set_dpi_xy` hardcodes `0x01`.

### New N-API Exports (`src/driver/addon.cc`)

| Export | Params | Returns | Description |
|---|---|---|---|
| `mouseGetActiveProfile` | `internalId` | number (1–5) | Read active profile slot |
| `mouseSetActiveProfile` | `internalId, slot` | void | Set active profile slot (sends `0x05:0x03`) |
| `mouseMacroClear` | `internalId` | void | Clear macro buffer |
| `mouseGetDpiProfile` | `internalId, profile` | `{ x, y }` | Read DPI for a specific profile |
| `mouseSetDpiProfile` | `internalId, profile, x, y` | void | Set DPI for a specific profile |

### Existing — No Changes Needed

The existing `mouseGetButtonMapping` and `mouseSetButtonMapping` already accept `profile` as a parameter in `addon.cc` (it's `info[1]`). The hardcoding is only in `razerdevicemouse.js`.

## Device Layer Changes (`src/main/device/razerdevicemouse.js`)

### New State

- `this.activeProfile` — current active slot (1–5), populated on `init()` via `getActiveProfile()`
- `this.slotOccupied` — `{ 1: true, 2: false, 3: false, 4: false, 5: false }` — tracked locally by the app after `saveToSlot` / `clearSlot` / `init` operations. See "Determining Slot Occupancy" below.

### Modified Methods — Add `profile` Parameter

All methods default `profile` to `this.activeProfile` when omitted, maintaining backward compatibility.

| Method | Change |
|---|---|
| `getButtonMapping(buttonId, layer, profile)` | Use `profile` instead of hardcoded `0x01` |
| `setButtonMapping(buttonId, layer, actionType, params, profile)` | Use `profile` instead of hardcoded `0x01`. **When `this.activeProfile !== 1` and `profile === this.activeProfile`, also writes to slot 1** (slot 1 mirroring). |
| `getAllButtonMappings(panelId, layer, profile)` | Pass `profile` through to `getButtonMapping` |
| `setDPI(dpi, profile)` | Use new `addon.mouseSetDpiProfile`. **When `this.activeProfile !== 1` and `profile === this.activeProfile`, also writes to slot 1.** |
| `getDPI(profile)` | Use new `addon.mouseGetDpiProfile` |

### Slot 1 Mirroring

Mirroring is owned **exclusively by the device layer** (`razerdevicemouse.js`). The IPC/application layer does NOT implement mirroring — it simply calls the device methods.

Rules:
- **When `this.activeProfile !== 1` and writing to the active profile:** `setButtonMapping` and `setDPI` write to both `this.activeProfile` AND slot 1. This ensures the live dispatch profile stays current.
- **When `this.activeProfile === 1`:** writes to slot 1 only. Current behavior, no change.
- **When writing to a non-active profile explicitly** (e.g. during `saveToSlot`): writes to the specified profile only, no mirroring.
- **Hypershift interaction:** when `actionType === 0x0c`, the existing dual-layer write (layer 0 + layer 1) applies to each profile independently. If mirroring is active, this means 4 USB writes per button: (active slot, layer 0), (active slot, layer 1), (slot 1, layer 0), (slot 1, layer 1).

### New Methods

**`getActiveProfile()`** — calls `addon.mouseGetActiveProfile(this.internalId)`, returns slot number.

**`setActiveProfile(slot)`** — calls `addon.mouseSetActiveProfile(this.internalId, slot)` then `addon.mouseMacroClear(this.internalId)`. Updates `this.activeProfile`.

**`switchProfile(slot)`** — high-level profile switch:
1. Read all button mappings from `slot` (both layers, all buttons for current panel)
2. Write all read mappings to slot 1 — write every button, including those with default/zero values, to ensure slot 1 is a complete mirror with no stale bindings from a previous profile
3. Read DPI from `slot`, write to slot 1
4. Update `this.activeProfile = slot`

**Note on SET_PROFILE during switching:** The USB capture (Groups 5–6) shows NO explicit `SET_PROFILE` command during profile switching — only button writes to both slots. `SET_PROFILE` (`0x05:0x03`) was only observed during slot clearing. Therefore, `switchProfile` does NOT call `setActiveProfile`. It only writes bindings/DPI to slot 1 and updates the local `activeProfile` tracking. **This must be verified empirically during implementation.** If the device does not respond to button presses with the new bindings after a switchProfile without SET_PROFILE, add the SET_PROFILE call as a fallback.

**`saveToSlot(targetSlot)`** — creates a point-in-time snapshot of slot 1 into a storage slot:
1. Read all button mappings + DPI from slot 1
2. Write all button mappings + DPI to `targetSlot` (direct write, no mirroring)
3. Call `addon.mouseMacroClear(this.internalId)`
4. Mark `this.slotOccupied[targetSlot] = true`

This is a snapshot, not a live-synced copy. Subsequent edits to the active profile will NOT automatically propagate to `targetSlot`. The user must save again to update the stored slot.

**`clearSlot(slot)`** — clears an on-board slot. Sends exactly what the capture shows:
1. `addon.mouseSetActiveProfile(this.internalId, slot)` — sends `SET_PROFILE(slot)`
2. `addon.mouseMacroClear(this.internalId)` — sends `MACRO_CLEAR`
3. Mark `this.slotOccupied[slot] = false`
4. If `slot === this.activeProfile`, set `this.activeProfile = 1` and notify renderer

Note: `clearSlot` calls the addon functions directly rather than the higher-level `setActiveProfile()` method, to avoid sending a double `MACRO_CLEAR`.

### `activeProfile` and State Serialization

`this.activeProfile` is NOT included in `getState()` / `resetToState()`. The hardware is authoritative — on resume from suspend, `init()` re-reads the active profile from the device via `getActiveProfile()`. The renderer re-fetches on mount. No cached profile state needs to survive suspend/resume.

**Important:** the existing `resetToState` calls `this.setDPI(state.dpi)` with no profile argument. After adding the `profile` parameter, this would default to `this.activeProfile` and trigger mirroring. To preserve the existing behavior (state restore always targets slot 1 directly), `resetToState` must be updated to call `this.setDPI(state.dpi, 1)` explicitly, bypassing mirroring.

## IPC & Application Layer Changes (`src/main/application.js`)

### Modified IPC Channels

| Channel | Current Payload | New Payload |
|---|---|---|
| `get-button-mappings` | `{ device, panelId, layer }` | `{ device, panelId, layer, profile }` |
| `set-button-mapping` | `{ device, buttonId, layer, actionType, params }` | `{ device, buttonId, layer, actionType, params, profile }` |

When `profile` is omitted, defaults to `device.activeProfile` (backward compatible).

The IPC handler passes `profile` through to the device method. **Slot 1 mirroring is NOT implemented here** — it is handled inside `razerdevicemouse.js`'s `setButtonMapping` and `setDPI` methods.

### New IPC Channels

| Channel | Direction | Payload | Purpose |
|---|---|---|---|
| `get-active-profile` | renderer -> main | `{ device }` | Read active profile slot |
| `active-profile-response` | main -> renderer | `{ profile, slotOccupied }` | Returns slot number and occupancy map |
| `switch-profile` | renderer -> main | `{ device, profile }` | Full profile switch with slot 1 mirroring |
| `profile-switched` | main -> renderer | `{ profile, error? }` | Confirms switch completed |
| `save-to-slot` | renderer -> main | `{ device, targetSlot }` | Copy slot 1 to target slot |
| `slot-saved` | main -> renderer | `{ targetSlot, slotOccupied, error? }` | Confirms save completed, returns updated occupancy |
| `clear-slot` | renderer -> main | `{ device, slot }` | Clear an on-board slot |
| `slot-cleared` | main -> renderer | `{ slot, slotOccupied, error? }` | Confirms clear completed, returns updated occupancy |
| `get-all-profile-mappings` | renderer -> main | `{ device, panelId, layer }` | Read mappings for all 5 slots |
| `all-profile-mappings-response` | main -> renderer | `{ profiles: { 1: [...], 2: [...], ... } }` | Mappings per slot |

## Renderer UI Changes (`src/renderer/sections/sectionsettingbuttonmapping.jsx`)

### Profile Slot Selector

Added to the button mapping panel header, above the existing layer toggle.

**Visual design:** Row of 5 slot buttons styled as SD card icons with colored dot indicators, matching the Synapse "On-Board Memory" UI:
- Slot 1: white/default dot (hybrid/live slot)
- Slot 2: red dot
- Slot 3: green dot
- Slot 4: blue dot
- Slot 5: cyan dot

Active slot is highlighted. Empty slots appear dimmed/outline-only.

### Interaction Model

| Slot State | Click | Hover |
|---|---|---|
| Empty | Confirmation prompt: "Save current profile to this slot?" | — |
| Occupied (not active) | Switches to this profile via `switch-profile` IPC | Shows small "x" icon to clear |
| Occupied (active) | No-op (already selected) | Shows small "x" icon to clear |

**Clearing a slot:** Clicking the "x" on hover sends `clear-slot`. If the cleared slot was active, the UI switches to slot 1.

**Saving to a slot:** Clicking an empty slot triggers `save-to-slot`, which copies slot 1's current config to the target slot.

### New Component State

| State | Type | Description |
|---|---|---|
| `activeProfile` | number | Currently active slot (1–5) |
| `slotOccupied` | object | `{ 1: true, 2: false, 3: true, ... }` — which slots have profiles |
| `profileSwitching` | boolean | Disables UI during switch/save/clear operations |

### Determining Slot Occupancy

Slot occupancy is **tracked locally by the app**, not derived from button mapping content. Reasons:
- A profile with all-default button mappings (like "Gaming" in the USB capture) is still a valid occupied slot. Checking for non-default mappings would incorrectly mark it as empty.
- The device has no known "is slot occupied" command.

**On `init()`:** attempt to read one button mapping from each slot (2–5). If the device returns a valid response, mark the slot as occupied. If it returns an error or all-zero response, mark as empty. This heuristic must be verified empirically during implementation — the device may always return a valid response even for unused slots.

**After operations:** `saveToSlot` marks the target as occupied. `clearSlot` marks it as empty. These local updates are authoritative within a session.

**On fresh app launch:** re-probe all slots as described above. The `slotOccupied` state is not persisted to disk — it is re-derived each session from the device.

### Panel Switch While On Non-Default Profile

When the user physically swaps the side panel while viewing profile 3's mappings, the `panel-type-changed` event fires. The renderer re-fetches button mappings via `get-button-mappings`. The `profile` field is omitted, so the IPC handler defaults to `device.activeProfile` (which is 3). No special handling needed — the existing flow works correctly with the profile default.

### No Changes to Existing Edit Flow

The inline button editor, action type pills, apply/cancel, layer toggle, and recording functionality remain unchanged. They operate on whichever profile is currently active. The slot 1 mirroring is handled transparently in `razerdevicemouse.js`.

## Error Handling

- **Profile switch failure:** respond via `profile-switched` with `{ error }`. UI re-fetches active profile to resync.
- **Save to occupied slot:** the UI only offers save on empty slots, so this shouldn't happen. If it does, overwrite silently and update occupancy.
- **Clear active slot:** `clearSlot` handles this — switches to slot 1, then clears. If slot 1 is cleared, no-op (slot 1 cannot be cleared — it's always the live profile).
- **Device disconnected during operation:** log error, UI will resync on next device refresh.
- **SET_PROFILE not working during switch:** see the verification note in `switchProfile`. If empirical testing shows buttons don't update without SET_PROFILE, add it as step 4 of `switchProfile`.

## Out of Scope

- **Profile metadata (`0x05:0x08`)** — profile names, UUIDs, hashes. Not needed; slots are identified by number and color.
- **Per-profile LED indicator colors (`0x0f:0x04`)** — the colored dots are hardcoded in the UI to match the hardware LEDs.
- **Per-profile brightness** — can be added later.
- **Synapse `.synapse4` file import/export** — separate feature, can build on top of this.
- **Local persistence of profiles** — covered by the deferred button mapping persistence spec.
