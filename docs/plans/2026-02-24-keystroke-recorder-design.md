# Keystroke Recorder & Expanded Keyboard Keys — Design

## Overview

Add a keystroke recorder ("Record" button) to the Keyboard Key action editor for side button mapping, and expand the key dropdown to cover all standard HID Keyboard/Keypad page (0x07) keys.

Two ways to assign a keyboard key to a side button:
1. **Manual** (existing) — pick from grouped dropdown + modifier checkboxes
2. **Record** (new) — click Record, press the key combo, captured automatically

## Capture Mechanism

DOM `KeyboardEvent` (`keydown`/`keyup`) in the renderer process. No main process or driver changes.

`KeyboardEvent.code` maps to physical keys (e.g. `"KeyA"`, `"BracketLeft"`) which correspond nearly 1:1 to HID usage codes. Modifiers come from `event.ctrlKey/shiftKey/altKey/metaKey`.

### Why not iohook?

- iohook uses OS-level keycodes (different from HID usage codes, needs separate mapping)
- Global capture is unnecessary — the user is already focused on the UI
- More complex (main process IPC, start/stop lifecycle)
- iohook is somewhat unmaintained (v0.9.3)

## Capture Rules

### Combo capture (modifier + key)

Capture fires immediately on `keydown` of a non-modifier key:
- `editActionValue` = `CODE_TO_HID[event.code]`
- `editModifier` = bitmask from ctrlKey (0x01), shiftKey (0x02), altKey (0x04), metaKey (0x08)
- Exit recording mode

### Standalone modifier capture

On `keyup` of any modifier, if no non-modifier was pressed during this recording session, capture the released modifier as a standalone key:
- `editActionValue` = HID code for that modifier (0xE0-0xE7)
- `editModifier` = 0
- Exit recording mode

### Unsupported keys

Keys not in the HID Keyboard/Keypad page (e.g. Globe/Fn, media keys) show a brief "Key not supported" flash. Recording stays active.

Globe/Fn lives on Apple Vendor Top Case (0xFF, usage 0x03) and Consumer (0x0C, usage 0x029D) pages — not bindable through Razer's keyboard action type (0x02).

## UI Design

### Normal state (recording = false)

```
☐ Ctrl  ☐ Shift  ☐ Alt  ☐ Cmd           [⏺ Record]
[▼ Key dropdown (grouped by category)              ]
```

- Modifier checkboxes + expanded grouped dropdown (existing flow, enhanced)
- "Record" pill button added to the right of the modifier row

### Recording state (recording = true)

```
[Ctrl] [Shift]  ← live modifier badges, light up as held
Press a key...   (pulsing text)              [Cancel]
```

- Modifier checkboxes and dropdown replaced by live feedback area
- Pulsing "Press a key..." prompt
- Cancel button to exit without capturing
- Hidden auto-focused `<input>` receives keydown/keyup events
- Escape is capturable (not used as cancel)

### After capture

Values pre-fill the normal editor controls (checkboxes + dropdown). Identical display regardless of whether the key was recorded or manually selected.

## Expanded Key Table

New shared data module: `src/renderer/data/keyboardkeys.js`

Exports:
- `KEYBOARD_KEYS` — array of `{ value, label, category, code }` covering all HID page 0x07 keys
- `CODE_TO_HID` — object mapping `KeyboardEvent.code` strings to HID usage bytes

### Categories

| Category | Keys | HID Range |
|---|---|---|
| Letters | A-Z | 0x04-0x1D |
| Numbers | 0-9 | 0x1E-0x27 |
| Punctuation | `-` `=` `[` `]` `\` `;` `'` `` ` `` `,` `.` `/` | 0x2D-0x38 |
| System | Enter, Escape, Backspace, Tab, Space, Caps Lock, Print Screen, Scroll Lock, Pause | 0x28-0x2C, 0x39, 0x46-0x48 |
| Navigation | Insert, Home, Page Up, Delete, End, Page Down, Arrows | 0x49-0x52 |
| Function | F1-F24 | 0x3A-0x45, 0x68-0x73 |
| Keypad | Num Lock, Numpad 0-9, operators, Enter, Decimal | 0x53-0x63 |
| Modifiers | Left/Right Ctrl, Shift, Alt, GUI | 0xE0-0xE7 |

The dropdown uses `<optgroup>` labels for each category.

## Files Changed

| File | Change |
|---|---|
| `src/renderer/data/keyboardkeys.js` | **New.** Shared key table + CODE_TO_HID lookup |
| `src/renderer/sections/sectionsettingbuttonmapping.jsx` | Remove inline KEYBOARD_KEYS. Import from new module. Add recording state, startRecording/stopRecording/handleRecordKeyDown/handleRecordKeyUp methods. Revise renderEditor for recording UI. Update dropdown to use optgroup. |

No changes to main process, IPC, driver, or C layer.

## Component State Additions

```
recording: false          // whether keystroke capture is active
recordingModifiers: 0     // live modifier bitmask during recording (for badge display)
recordingUnsupported: false  // flash "Key not supported"
```

Instance variable (not state):
```
this.nonModifierPressed = false  // tracks if a non-modifier was pressed during recording
```

## Scope Exclusions

- No multi-key sequences (macros)
- No modifier-only combos (Ctrl+Shift without a key — standalone modifiers OR modifier+key only)
- No Consumer/Vendor page keys in keyboard action type
- No main process or driver changes
