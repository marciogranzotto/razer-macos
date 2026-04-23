# Razer Naga V2 Pro — USB Protocol Reference

**Device:** Razer Naga V2 Pro (productId `0x00A7` wired, `0x00A8` wireless)
**Applies to:** macOS driver in this repo. Protocol verified via USB capture analysis of Synapse traffic + live on-device probing. Original investigation: git log on the `feature/naga-v2-pro-side-buttons` branch.

## Operating modes

This device has two operating modes. Only the PC mode is fully useful to software.

### HW (stand-alone) mode
- Colored profile LED matches the active slot (2=red, 3=green, 4=blue, 5=cyan — roughly; exact colors per slot).
- The physical profile button on the bottom of the mouse cycles through slots 1–5. Each slot has its own stored DPI and button mappings; the mouse loads them on switch.
- Software SET_ACTIVE_PROFILE is inert: the device ACKs but ignores.

### PC mode
- Profile LED turns white and the physical profile button is dead.
- Software takes over fully: `SET_ACTIVE_PROFILE` (`0x05:0x04`) moves the active slot, GET/SET of per-profile DPI and button mappings work as expected.

**Switching between modes:** writing anything that modifies profile 1's state flips HW → PC mode. Our app enters PC mode as soon as the user adjusts a setting. We do NOT have a known command to return to HW mode; the user would presumably power-cycle the mouse for that.

## Razer report format (90 bytes)

| byte | field | notes |
|------|-------|-------|
| 0 | status | Host→device: 0x00 new command. Device response: 0x02 success, 0x03 failure, 0x01 busy, 0x04 no-response, 0x05 not-supported |
| 1 | transaction_id | Echo identifier; this driver uses `0x1f` for Naga V2 Pro commands |
| 2–3 | remaining_packets | Big-endian u16; non-zero only for multi-packet commands |
| 4 | protocol_type | 0 for all commands we use |
| 5 | data_size | Number of meaningful bytes in arguments |
| 6 | command_class | Functional grouping (0x02 buttons, 0x04 DPI, 0x05 profile, 0x06 macro) |
| 7 | command_id | Operation within class; bit 7 (0x80) usually distinguishes write vs read, but NOT always on this device (notable exception: `0x05:0x04` is a write, `0x05:0x84` is the read) |
| 8–87 | arguments | 80 bytes; first `data_size` are meaningful |
| 88 | crc | XOR of bytes 2..87 |
| 89 | reserved | 0 |

## Commands used by this driver

### Profile management (class 0x05)

**`0x05:0x04` — SET_ACTIVE_PROFILE** — moves the active profile in PC mode.
- `data_size = 0x01`
- `arguments[0]` = target profile (1–5)
- Driver function: `razer_mouse_attr_activate_profile`
- Note: the device's standalone `0x05:0x03` also nominally sets a profile, but on this device in PC mode it does *not* move the active slot; `0x05:0x04` is what actually works. Empirically confirmed via a command-sweep (commit log for the investigation).

**`0x05:0x84` — GET_ACTIVE_PROFILE** — returns the currently-active profile.
- `data_size = 0x01`
- Request `arguments[0]` = 0 (ignored)
- Response `arguments[0]` = active profile (1–5)
- Driver function: `razer_mouse_attr_read_active_profile`

**`0x05:0x03` — unresolved.** Documented in openrazer as "set active profile" but on this device it behaves differently (doesn't move the hardware active slot in PC mode). Kept in the driver for completeness (`razer_mouse_attr_write_active_profile`), not used by the device layer. May correspond to a hardware-mode-only setter or a different semantic we haven't pinned down.

**`0x05:0x02`** — profile-metadata query (`arg[0]` = profile index; response echoes the profile byte back, plus additional metadata in subsequent bytes — PROFILE_METADATA query, not a context setter). Not used by this driver.

**`0x05:0x08`** — multi-packet profile metadata (includes profile UUID and ASCII name). Not used by this driver.

### DPI (class 0x04)

**`0x04:0x06` — SET_DPI_STAGES** — writes per-profile DPI stage table. **This is the per-profile DPI persistence mechanism on this device** — VARSTORE (0x04:0x05) is a single global register that does NOT persist per-profile.
- `data_size = 3 + num_stages * 7` (typically `0x26` = 38 bytes for 5 stages)
- `arguments[0]` = profile (1–5)
- `arguments[1]` = active_stage (**1-based; firmware rejects 0 with status 0x03**)
- `arguments[2]` = num_stages (typically 5)
- Then `num_stages × 7 bytes`: `(stage_id, x_hi, x_lo, y_hi, y_lo, 0, 0)`. Stage IDs are 0-based on write (and device returns them 1-based on read — quirk).
- At least two stages must have distinct DPI values (identical-all-stages is rejected with status 0x03).
- Driver function: `razer_mouse_attr_write_dpi_stages`

**`0x04:0x86` — GET_DPI_STAGES** — reads per-profile DPI stage table.
- `data_size = 0x26` (request); same size for response
- Request `arguments[0]` = profile (1–5)
- Response layout matches the write format, but stage IDs in the response are 1-based.
- Driver function: `razer_mouse_attr_read_dpi_stages_active` (returns only the active stage's DPI; full-table read isn't needed by the app)

**`0x04:0x05` — SET_DPI (VARSTORE)** — single global DPI register.
- `data_size = 0x07`
- Writes affect the live cursor speed but do NOT persist per profile. Used as a no-op "live DPI" view; the real per-profile DPI lives in the stage table above.
- Driver function: `razer_attr_write_dpi` (common)

**`0x04:0x85` — GET_DPI (VARSTORE)** — returns the single global DPI.
- Driver function: `razer_attr_read_dpi` (common)

### Button mapping (class 0x02)

**`0x02:0x0c` — SET_BUTTON_MAPPING** — per-profile button mapping. On this device, `arg[0]` is a real slot number; writes target slot N independent of the active profile.
- `data_size = 0x0a`
- `arguments[0]` = profile (1–5)
- `arguments[1]` = button id
- `arguments[2]` = layer (0x00 normal, 0x01 hypershift)
- `arguments[3]` = action_type (`0x01` mouse button, `0x02` keyboard, `0x0a` multimedia, `0x0c` hypershift)
- `arguments[4..9]` = action params
- Driver function: `razer_mouse_attr_write_button_mapping`

**`0x02:0x8c` — GET_BUTTON_MAPPING** — per-profile button mapping read.
- Same arg layout as SET; response populates `arguments[3..9]` with the stored mapping.
- Driver function: `razer_mouse_attr_read_button_mapping`

### Macro clear (class 0x06)

**`0x06:0x8e` — MACRO_CLEAR** — sent at the end of profile-related operations as housekeeping (clears transient macro state).
- `data_size = 0x0e`
- All 14 argument bytes = 0
- Driver function: `razer_mouse_attr_write_macro_clear`

## Per-profile DPI handling (why it's unusual)

- VARSTORE DPI (`0x04:0x05` / `0x04:0x85`) is a single global register. Writes affect live cursor speed but don't persist when the hardware switches profiles.
- Each profile's *persistent* DPI lives in its stage table, written by `SET_DPI_STAGES` and read by `GET_DPI_STAGES`.
- When `SET_ACTIVE_PROFILE(N)` moves the active slot, the hardware loads profile N's active-stage DPI into the live cursor-speed register. Subsequent `GET_DPI` (VARSTORE) returns that value.
- The device layer caches per-slot DPI in `slotDpi` because a round-trip through hardware on every UI update is unnecessary — we know what we wrote, and we seed from `GET_DPI_STAGES` at startup.

## Device-layer architecture

- `razerdevicemouse.js:init()` reads `activeProfile` via `mouseGetActiveProfile`, populates `slotDpi` by calling `mouseGetDpiForProfile` for each slot.
- `setDPI(dpi, profile)` writes a 5-stage table via `mouseSetDpiStages` (stages centered on the user's value, active_stage=3). Updates the local cache.
- `switchProfile(slot)` calls `mouseActivateProfile(slot)`, updates `activeProfile`, and reads `this.dpi` from the cache (falls back to `mouseGetDpi` if cache is null).
- `saveToSlot(targetSlot)` snapshots the current slot's button mappings, activates the target slot, writes button mappings and the DPI stage table to the target.
- `setButtonMapping` / `getButtonMapping` use per-slot reads/writes directly (no mirror).

## Known quirks not currently handled

- **Software SET occasionally fails after extended idle.** A prior session observed that `0x05:0x04` can stop moving the profile for reasons we did not pin down; running any substantial command sequence appears to restore it. Real-world usage in the app hasn't surfaced this yet — keep an eye on it.
- **HW-mode fallback.** We don't have a command to exit PC mode back to HW mode. Not needed for the app; documented in case a future user wants the profile LED to be colored again.

## References in this repo

- Driver: `librazermacos/src/lib/razermouse_driver.c`
- Common protocol helpers: `librazermacos/src/lib/razerchromacommon.c`
- N-API bindings: `src/driver/addon.cc`
- Device layer: `src/main/device/razerdevicemouse.js`
- USB captures used during investigation: `captures/razer-naga-pannel-swaps.pcapng` + `captures/*.py` analyzers
