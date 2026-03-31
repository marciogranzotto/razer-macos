# Button Mapping Persistence

## Problem

Button mappings on Razer mice are stored exclusively in device firmware. When the mouse is connected to a Windows machine running Razer Synapse, Synapse overwrites the on-device mappings. The macOS app has no local backup and cannot restore them.

## Solution

A new `ButtonMappingManager` that persists button mappings locally on the user's Mac, with auto-restore on app launch, auto-save on edit, and a comparison flow for resolving conflicts when the device mappings have been changed externally.

## Storage Format

Stored via `electron-json-storage` under key `razer_buttonmappings_<productId>`.

`productId` is the device's decimal integer product ID (matching the existing convention from `RazerDevice.getSettingsKey()` which produces keys like `razer_590`). For example, a device with USB product ID `0x024e` produces key `razer_buttonmappings_590`.

```json
{
  "activeProfile": "default",
  "autoRestore": true,
  "profiles": {
    "default": {
      "panelType": 3,
      "profile": 1,
      "layers": {
        "0": {
          "64": { "actionType": 1, "params": [1, 1, 0, 0, 0, 0] },
          "65": { "actionType": 2, "params": [2, 0, 40, 0, 0, 0] }
        },
        "1": {
          "64": { "actionType": 12, "params": [1, 1, 0, 0, 0, 0] }
        }
      }
    }
  }
}
```

### Field Reference

| Field | Type | Description |
|---|---|---|
| `activeProfile` | string | Name of the profile used for auto-save and auto-restore |
| `autoRestore` | boolean | Whether to push saved mappings to device on app launch |
| `profiles` | object | Named profiles, keyed by profile name |
| `profiles.<name>.panelType` | number | Side panel type ID when mappings were saved (`0x01`=2-btn, `0x03`=12-btn, `0x04`=6-btn) |
| `profiles.<name>.profile` | number | Hardware profile byte (currently always `0x01`) |
| `profiles.<name>.layers` | object | Keyed by layer index: `"0"` = normal, `"1"` = hypershift |
| `profiles.<name>.layers.<layer>.<buttonId>` | object | Button mapping keyed by hardware button ID as a decimal string (e.g. `0x40` -> `"64"`, `0x50` -> `"80"`) |
| `profiles.<name>.layers.<layer>.<buttonId>.actionType` | number | Action type byte (e.g. `0x01` mouse, `0x02` keyboard, `0x0c` hypershift) |
| `profiles.<name>.layers.<layer>.<buttonId>.params` | number[6] | 6-byte action parameter array, format depends on `actionType` |

### Button ID Ranges by Panel

Button ID keys are always the **decimal string representation** of the hardware button ID byte.

| Panel | `panelType` | Button IDs (hex) | Button IDs (decimal string keys) |
|---|---|---|---|
| 2-Button | `0x01` (1) | `0x04`, `0x05` | `"4"`, `"5"` |
| 6-Button | `0x04` (4) | `0x50`–`0x55` | `"80"`–`"85"` |
| 12-Button | `0x03` (3) | `0x40`–`0x4b` | `"64"`–`"75"` |

The button IDs come from `FeatureButtonMapping` in `src/main/feature/featurebuttonmapping.js`. The iteration order when saving/restoring does not matter — buttons are keyed by ID, not by position.

## ButtonMappingManager

New file: `src/main/buttonmappingmanager.js`

### Core API

| Method | Description |
|---|---|
| `save(device)` | Reads all button mappings from device (both layers, all buttons for current panel), saves to local storage under `activeProfile`. **Aborts with an error if `device.panelType` is falsy** (null or 0 — no panel attached). Note: `init()` sets `panelType` from the raw driver byte (0 = no panel), while the interrupt listener converts 0 to null. The guard must handle both. |
| `restore(device)` | Reads saved `activeProfile` from storage, writes all mappings to device. **Aborts with an error if stored `panelType` does not match `device.panelType`** — does not write mismatched button IDs to the device. |
| `saveFromEdit(device, buttonId, layer, actionType, params)` | Updates a single button in the local `activeProfile` after a UI edit. **When `actionType === 0x0c` (hypershift), ignores the `layer` argument and writes to both layer `"0"` and layer `"1"`**, mirroring the device write behavior. |
| `hasSavedMappings(device)` | Returns whether local storage exists for this device |
| `getSavedMappings(device)` | Returns the full stored data |
| `setAutoRestore(device, enabled)` | Toggles the `autoRestore` flag in storage |
| `getStorageKey(device)` | Returns `razer_buttonmappings_<productId>` (decimal integer) |
| `readAllFromDevice(device)` | Reads button mappings for both layers (normal and hypershift) for hardware profile `0x01` from the device. The driver only supports profile `0x01` — there is no multi-profile enumeration. Returns data in the same shape as `profiles.<name>`: `{ panelType, profile, layers: { "0": { "<buttonId>": { actionType, params } }, "1": { ... } } }` |

### Profile API (implemented, UI deferred)

| Method | Description |
|---|---|
| `createProfile(device, name)` | Snapshots current device mappings into a new named profile |
| `switchProfile(device, name)` | Restores profile's mappings to device immediately, updates `activeProfile` in storage. Auto-save on edit now targets this profile. |
| `deleteProfile(device, name)` | Removes profile. Blocked if `name === "default"` or last remaining profile |
| `renameProfile(device, oldName, newName)` | Renames a profile. Blocked if `oldName === "default"` or `newName === "default"` — prevents renaming away from or into the reserved name |
| `listProfiles(device)` | Returns array of profile names and which is active |

### Profile Rules

- `"default"` profile always exists and cannot be deleted or renamed
- Auto-save on edit writes to whichever profile is `activeProfile`
- "Save from device" writes to `activeProfile`
- `switchProfile` immediately restores the target profile to the device (same as calling `restore` for that profile)
- On app launch, all profiles are loaded from storage into memory (no extra disk reads when switching)

### Error Handling

- **Storage read error on launch:** log the error, proceed as if no saved mappings exist. Do not crash or block app startup.
- **Storage write error:** log the error, surface to renderer via the response IPC channel with an `error` field.
- **Panel type mismatch on restore:** abort restore, respond via `button-mappings-restored` with `{ error: "panel-type-mismatch" }`.
- **No panel attached (panelType is falsy — null or 0):** abort save/restore, log warning. UI should disable save/restore controls when no panel is detected.
- **`saveFromEdit` failure:** log the error only. The device write already succeeded, so the renderer does not need to be notified — the local backup is best-effort. The next explicit "Save from device" action will reconcile.

## Wiring in RazerApplication

`ButtonMappingManager` is instantiated in `RazerApplication` alongside `SettingsManager` and `StateManager`.

### On App Launch

Auto-restore is wired into the initial `refresh()` call during app startup only — **not** on every tray-click refresh. After `DeviceManager` populates active devices:

1. For each mouse device with button mapping support: load full storage (all profiles) into memory
2. If `autoRestore` is true and saved mappings exist, call `restore(device)` to push `activeProfile` to device

Device hot-plug restore (USB connect/disconnect detection) is out of scope for this design and can be added as a future enhancement.

### On Button Mapping Edit (existing flow)

After the `set-button-mapping` IPC handler writes to the device, it additionally calls `buttonMappingManager.saveFromEdit(device, buttonId, layer, actionType, params)` to persist the change locally.

### Hypershift Special Case

The existing `set-button-mapping` handler writes hypershift (`actionType === 0x0c`) to both layers. `saveFromEdit` mirrors this: when `actionType === 0x0c`, it ignores the `layer` argument and saves the mapping to both layer `"0"` and layer `"1"` in local storage.

## IPC Channels

Channel naming follows the existing codebase convention: `get-X` -> `X-response`, action verbs for commands.

| Channel | Direction | Payload | Purpose |
|---|---|---|---|
| `save-button-mappings` | renderer -> main | `{ device }` | Full device read + save to `activeProfile` |
| `button-mappings-saved` | main -> renderer | `{ error? }` | Confirms save completed or reports error |
| `restore-button-mappings` | renderer -> main | `{ device }` | Push `activeProfile` to device |
| `button-mappings-restored` | main -> renderer | `{ error? }` | Confirms restore completed or reports error |
| `get-device-mappings` | renderer -> main | `{ device }` | Read current mappings from device for comparison |
| `device-mappings-response` | main -> renderer | `{ deviceMappings, savedMappings, error? }` | Returns device's current mappings and saved mappings for side-by-side comparison. `deviceMappings` and `savedMappings` share the same shape as `profiles.<name>`. |
| `resolve-mapping-conflict` | renderer -> main | `{ device, profileName, resolution }` | Per-profile choice: `"keep-device"` or `"push-saved"` |
| `mapping-conflict-resolved` | main -> renderer | `{ profileName, resolution, error? }` | Confirms resolution applied |
| `set-auto-restore` | renderer -> main | `{ device, enabled }` | Toggles auto-restore flag |
| `get-button-mapping-status` | renderer -> main | `{ device }` | Check saved state |
| `button-mapping-status-response` | main -> renderer | `{ hasSaved, autoRestore }` | Returns current status |

## UI Changes

### Button Mapping Panel Header

Added to the existing button mapping section in `sectionsettingbuttonmapping.jsx`:

- **"Auto-restore on connect" toggle** — checkbox, on by default, persists `autoRestore` flag
- **"Read from device" button** — triggers comparison flow
- **Status text** — "Mappings saved" / "No saved mappings"

All save/restore controls are disabled when `device.panelType` is null (no panel attached).

### Comparison View

Triggered by "Read from device":

1. App reads current mappings from the device via `get-device-mappings`
2. Response includes both `deviceMappings` and `savedMappings` in the same profile shape
3. Shows a side-by-side view per profile: saved (local) vs device (current)
4. Per profile, user chooses:
   - **"Keep device mappings"** — sends `resolve-mapping-conflict` with `resolution: "keep-device"`, overwrites local profile with device data
   - **"Push saved mappings"** — sends `resolve-mapping-conflict` with `resolution: "push-saved"`, writes local profile to device
5. Each resolution gets a `mapping-conflict-resolved` confirmation
6. View closes after all profiles are resolved

### No Changes to Existing Edit Flow

The inline button editor, action type pills, apply/cancel, and recording functionality remain unchanged. The only addition is the background `saveFromEdit()` call after each successful edit.
