# Button Mapping UI v2 — Design

**Date:** 2026-02-23
**Status:** Approved
**Scope:** Naga V2 Pro side button mapping — UI overhaul + missing action types

## Problem

The current button mapping UI uses a flat list with inline dropdown editors. With 12 buttons, navigating and editing is cumbersome. Several action types from the protocol spec are missing (Hypershift Modifier, Scroll Wheel, Sensitivity Clutch), keyboard modifier combos aren't supported, and there's a sub_type bug in multimedia params.

## Approach

Incremental refactor of the existing `SectionSettingButtonMapping` component. No new files, no architectural changes. Stays consistent with the single-file pattern used by all other sections.

## UI Design

### Grid Layout

Replace the flat button list with a CSS grid matching the physical panel arrangement:

- **12-Button Panel:** 4 rows x 3 cols (`[1][2][3] / [4][5][6] / [7][8][9] / [10][11][12]`)
- **6-Button Panel:** 2 rows x 3 cols (`[1][2][3] / [4][5][6]`)
- **2-Button Panel:** 1 row x 2 cols (`[1][2]`)

Each grid cell shows:
- Button label (top, e.g., "Button 7")
- Current mapping (bottom, smaller, e.g., "Key 7")
- Green border highlight when selected

### Editor Panel

Appears below the grid when a button is clicked. Contains:

1. **Header:** Button name + Cancel/Apply buttons
2. **Action type selector:** Row of pill-shaped toggle buttons:
   - Disabled | Mouse Button | Keyboard Key | Multimedia | Hypershift | Scroll Wheel | Sensitivity Clutch | Restore Default
3. **Action-specific parameters:**
   - **Disabled (0x00):** No params
   - **Mouse Button (0x01):** Pill buttons for Left/Right/Middle/Back/Forward
   - **Keyboard Key (0x02):** Modifier checkboxes (Ctrl, Shift, Alt, Cmd) + key dropdown
   - **Multimedia (0x0a):** Pill buttons for Play/Pause, Next, Prev, Mute, Vol Up, Vol Down
   - **Hypershift Modifier (0x0c):** Info text only ("Assigns Hypershift to this button")
   - **Scroll Wheel Control (0x12):** Single option "Cycle Up Scroll Stages"
   - **Sensitivity Clutch (0x06):** X/Y DPI inputs + "Independent X/Y DPI" checkbox
   - **Restore Default:** Info text ("Restores factory default binding for this button")

### Layer Toggle

Keep the existing Normal/Hypershift pill-button toggle above the grid.

## Data Flow Changes

### Renderer (`sectionsettingbuttonmapping.jsx`)

- **Constants:** Add `ACTION_TYPES` entries for 0x0c, 0x12, 0x06, and "Restore Default"
- **`buildParams`:** Add cases for new action types. Fix multimedia sub_type from `0x03` to `0x02`.
- **`describeMapping`:** Add human-readable labels for new action types
- **State:** Add `editModifier` (bitmask) for keyboard modifier checkboxes
- **Restore Default:** Look up `defaultAction` from feature config and send as normal `set-button-mapping`

### IPC Handler (`application.js`)

- **Hypershift two-write:** When `set-button-mapping` receives actionType `0x0c`, the handler sends two writes: one to normal layer (0x00) and one to hypershift layer (0x01). The renderer sends a single IPC call and doesn't know about the two-write protocol detail.

### No C/addon changes needed

The existing `razer_mouse_attr_write_button_mapping` passes action_type and params through generically. All new action types work with the existing driver function.

## Bug Fixes

- Multimedia `buildParams` sends sub_type `0x03` but spec requires `0x02` — fix this.

## Out of Scope

- Macros (0x03) — requires macro upload infrastructure (cmd_class 0x06)
- Profile switching
- Macro Queue mode within Disabled action type

## Files Changed

1. `src/renderer/sections/sectionsettingbuttonmapping.jsx` — Grid layout, editor panel, new action types
2. `src/main/application.js` — Hypershift two-write logic in `set-button-mapping` IPC handler
