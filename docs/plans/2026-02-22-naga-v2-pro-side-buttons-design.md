# Naga V2 Pro Side Button Configuration — Design Document

**Date:** 2026-02-22
**Status:** Approved
**Approach:** Hardware-first (on-device remapping via USB protocol reverse engineering)

## Overview

Add configurable side button support for the Razer Naga V2 Pro, including:
- Button remapping (on-device, persistent in firmware)
- Per-panel profiles (2-button, 6-button, 12-button)
- Hypershift layer support (secondary binding layer via trigger button)

## Background

No open-source project has implemented hardware-level button remapping for Razer Naga mice. The USB protocol for button mapping on the Naga V2 Pro is undocumented. The closest reference is openrazer Issue #2031 which documented keyboard remapping commands (Command Class `0x02`, Command ID `0x0d`/`0x12`), but nothing specific to mice. Partially documented onboard profile commands (`0x05`/`0x06`) exist on the openrazer Unknown Commands wiki.

### References
- [openrazer Issue #2031 — Key remapping protocol](https://github.com/openrazer/openrazer/issues/2031)
- [openrazer Unknown Commands wiki](https://github.com/openrazer/openrazer/wiki/Unknown-commands)
- [openrazer Reverse Engineering USB Protocol wiki](https://github.com/openrazer/openrazer/wiki/Reverse-Engineering-USB-Protocol)

## Phase 1: USB Protocol Reverse Engineering

### Goal
Capture and decode the USB commands Razer Synapse sends for button remapping, panel detection, Hypershift, and profile management.

### Tooling
- Windows machine with Razer Synapse installed
- Wireshark + USBPcap (or USB hardware analyzer)
- All three side panels (2/6/12 button)

### Capture Plan
1. Remap one button at a time, capture traffic, identify the pattern
2. Test each action type: keyboard key, mouse button, multimedia key, macro, disabled
3. Swap panels and capture any detection/configuration commands
4. Configure Hypershift trigger and layer bindings, capture those commands
5. Create/switch profiles, capture profile management commands

### Expected Protocol Structure
Based on the keyboard remapping analogy:
```
Command Class: 0x02 (or possibly 0x05 for profile-based devices)
Command ID:    TBD (capture will reveal)
Data:          [profile_slot] [button_id] [hypershift_flag] [action_type] [action_params...]
```

### Output
A protocol specification document mapping each USB command to its function, with hex examples.

## Phase 2: C Driver Layer (`librazermacos`)

### New Functions in `razermouse_driver.c`

```c
// Panel detection (if protocol supports it)
razer_mouse_attr_read_side_panel_type()
// Returns which panel is installed (2/6/12 button)

// Button mapping (normal layer)
razer_mouse_attr_write_button_mapping(side, button_id, action_type, action_data)
razer_mouse_attr_read_button_mapping(side, button_id)

// Hypershift layer
razer_mouse_attr_write_hypershift_mapping(side, button_id, action_type, action_data)
razer_mouse_attr_read_hypershift_mapping(side, button_id)
razer_mouse_attr_write_hypershift_trigger(button_id)

// Profile management
razer_mouse_attr_write_active_profile(profile_index)
razer_mouse_attr_read_active_profile()
razer_mouse_attr_write_profile_button_mapping(profile, button_id, ...)
```

### Action Types (expected, based on keyboard protocol)
| Value | Type |
|-------|------|
| `0x00` | Disabled |
| `0x01` | Mouse button |
| `0x02` | Keyboard key |
| `0x0A` | Multimedia key |
| `0x0B` | Double-click |

Each function follows the existing pattern: construct a `razer_report`, set command class/ID/arguments, send via `razer_send_payload()`.

## Phase 3: N-API Bridge (`addon.cc`)

### New Exported Functions

```javascript
// Panel detection
addon.mouseGetSidePanelType(deviceId)  // -> 2 | 6 | 12

// Button mapping (normal layer)
addon.mouseSetButtonMapping(deviceId, buttonId, actionType, actionData)
addon.mouseGetButtonMapping(deviceId, buttonId)

// Hypershift layer
addon.mouseSetHypershiftMapping(deviceId, buttonId, actionType, actionData)
addon.mouseGetHypershiftMapping(deviceId, buttonId)
addon.mouseSetHypershiftTrigger(deviceId, buttonId)

// Profile management
addon.mouseSetActiveProfile(deviceId, profileIndex)
addon.mouseGetActiveProfile(deviceId)
```

## Phase 4: Device Model

### `RazerDeviceMouse` Changes
- New methods mirroring the addon functions
- `getButtonMappings()` — reads all button bindings as an array
- `getHypershiftMappings()` — reads all Hypershift bindings
- State includes button mappings for save/restore via `StateManager`

### New Feature Classes

```javascript
FeatureButtonMapping
// config: { panelType: 2|6|12, maxProfiles: 5 }

FeatureHypershift
// config: { triggerButton: null }
```

Added to `naga_v2_pro_wired.json` and `naga_v2_pro_wireless.json` device configs.

## Phase 5: Renderer UI

### New Components

1. **`SectionSettingButtonMapping`** — Main container
   - Visual representation of the installed side panel
   - Grid/list of buttons with current bindings
   - Each button clickable to open binding editor

2. **`ButtonBindingEditor`** (modal/popover)
   - Action type selector: Keyboard Key, Mouse Button, Multimedia, Macro, Disabled
   - Keyboard: key listener capturing next keypress
   - Mouse: dropdown (Left, Right, Middle, Back, Forward)
   - Multimedia: dropdown (Play/Pause, Next, Previous, Volume Up/Down, Mute)
   - Apply / Cancel buttons

3. **`HypershiftToggle`** — Layer switcher
   - Toggle between Normal and Hypershift layer views
   - "Set Hypershift Trigger" mode

4. **`ProfileSelector`** — Profile management
   - Dropdown/tabs showing profiles (up to 5)
   - Create / Delete / Rename

### Visual Layout (12-button panel)
```
┌─────────────────────────┐
│  [Profile: Default v]   │
│  [Normal] [Hypershift]  │
│                         │
│   ┌───┬───┬───┐        │
│   │ 1 │ 2 │ 3 │        │
│   ├───┼───┼───┤        │
│   │ 4 │ 5 │ 6 │        │
│   ├───┼───┼───┤        │
│   │ 7 │ 8 │ 9 │        │
│   ├───┼───┼───┤        │
│   │10 │11 │12 │        │
│   └───┴───┴───┘        │
│                         │
│  Click a button to edit │
└─────────────────────────┘
```

### IPC Messages
- `get-button-mappings` / `set-button-mapping`
- `get-hypershift-mappings` / `set-hypershift-mapping`
- `set-hypershift-trigger`
- `get-active-profile` / `set-active-profile`
- `get-side-panel-type`

## Phase 6: Persistence and State Management

### On-Device Storage
Button mappings are stored in device firmware. The device retains bindings across power cycles.

### Local Cache (`SettingsManager`)
- Mappings cached per profile, keyed as `razer_<productId>_buttons`
- Serves as: display cache, backup, and reconnect restore source

### Per-Panel Configuration
- Settings stored per panel type: `razer_<productId>_buttons_12`, `_buttons_6`, `_buttons_2`
- Panel swap automatically loads the correct configuration

### `StateManager` Integration
- On suspend/resume: re-apply active profile's mappings to device
- On device connect: read current mappings from device, update local cache
- On panel swap: detect new panel type, load appropriate mappings

### Error Handling
- USB command failure: queue and retry on reconnect
- Panel type undetectable: default to 12-button, allow user override

## Implementation Phases

| Phase | Description | Dependency |
|-------|-------------|------------|
| 1 | USB Protocol RE | Windows + Synapse + Wireshark |
| 2 | C Driver | Phase 1 (protocol spec) |
| 3 | N-API Bridge | Phase 2 |
| 4 | Device Model | Phase 3 |
| 5 | Renderer UI | Phase 4 |
| 6 | Testing | All phases |
