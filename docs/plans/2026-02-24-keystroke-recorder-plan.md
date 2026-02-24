# Keystroke Recorder & Expanded Keyboard Keys — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a "Record" button for capturing keystrokes when assigning keyboard keys to Naga V2 Pro side buttons, and expand the key dropdown to all HID Keyboard/Keypad page (0x07) keys.

**Architecture:** New shared data module (`src/renderer/data/keyboardkeys.js`) holds the expanded key table and `KeyboardEvent.code` → HID lookup. The existing `sectionsettingbuttonmapping.jsx` component gains recording state and DOM event handlers. All changes are renderer-only — no main process, IPC, or driver changes.

**Tech Stack:** React 16 (class components), Electron renderer process, DOM KeyboardEvent API

**Design doc:** `docs/plans/2026-02-24-keystroke-recorder-design.md`

---

### Task 1: Create the shared keyboard key data module

**Files:**
- Create: `src/renderer/data/keyboardkeys.js`

**Step 1: Create the data file with the complete key table**

Create `src/renderer/data/keyboardkeys.js` with two exports:

```js
// Complete HID Keyboard/Keypad page (0x07) key definitions.
// Each entry: { value: HID usage code, label: display string, category: string, code: KeyboardEvent.code string }
// The `code` field enables the keystroke recorder to look up HID values from DOM events.

export const KEYBOARD_KEYS = [
  // Letters
  { value: 0x04, label: 'A', category: 'Letters', code: 'KeyA' },
  { value: 0x05, label: 'B', category: 'Letters', code: 'KeyB' },
  { value: 0x06, label: 'C', category: 'Letters', code: 'KeyC' },
  { value: 0x07, label: 'D', category: 'Letters', code: 'KeyD' },
  { value: 0x08, label: 'E', category: 'Letters', code: 'KeyE' },
  { value: 0x09, label: 'F', category: 'Letters', code: 'KeyF' },
  { value: 0x0a, label: 'G', category: 'Letters', code: 'KeyG' },
  { value: 0x0b, label: 'H', category: 'Letters', code: 'KeyH' },
  { value: 0x0c, label: 'I', category: 'Letters', code: 'KeyI' },
  { value: 0x0d, label: 'J', category: 'Letters', code: 'KeyJ' },
  { value: 0x0e, label: 'K', category: 'Letters', code: 'KeyK' },
  { value: 0x0f, label: 'L', category: 'Letters', code: 'KeyL' },
  { value: 0x10, label: 'M', category: 'Letters', code: 'KeyM' },
  { value: 0x11, label: 'N', category: 'Letters', code: 'KeyN' },
  { value: 0x12, label: 'O', category: 'Letters', code: 'KeyO' },
  { value: 0x13, label: 'P', category: 'Letters', code: 'KeyP' },
  { value: 0x14, label: 'Q', category: 'Letters', code: 'KeyQ' },
  { value: 0x15, label: 'R', category: 'Letters', code: 'KeyR' },
  { value: 0x16, label: 'S', category: 'Letters', code: 'KeyS' },
  { value: 0x17, label: 'T', category: 'Letters', code: 'KeyT' },
  { value: 0x18, label: 'U', category: 'Letters', code: 'KeyU' },
  { value: 0x19, label: 'V', category: 'Letters', code: 'KeyV' },
  { value: 0x1a, label: 'W', category: 'Letters', code: 'KeyW' },
  { value: 0x1b, label: 'X', category: 'Letters', code: 'KeyX' },
  { value: 0x1c, label: 'Y', category: 'Letters', code: 'KeyY' },
  { value: 0x1d, label: 'Z', category: 'Letters', code: 'KeyZ' },

  // Numbers
  { value: 0x1e, label: '1', category: 'Numbers', code: 'Digit1' },
  { value: 0x1f, label: '2', category: 'Numbers', code: 'Digit2' },
  { value: 0x20, label: '3', category: 'Numbers', code: 'Digit3' },
  { value: 0x21, label: '4', category: 'Numbers', code: 'Digit4' },
  { value: 0x22, label: '5', category: 'Numbers', code: 'Digit5' },
  { value: 0x23, label: '6', category: 'Numbers', code: 'Digit6' },
  { value: 0x24, label: '7', category: 'Numbers', code: 'Digit7' },
  { value: 0x25, label: '8', category: 'Numbers', code: 'Digit8' },
  { value: 0x26, label: '9', category: 'Numbers', code: 'Digit9' },
  { value: 0x27, label: '0', category: 'Numbers', code: 'Digit0' },

  // System
  { value: 0x28, label: 'Enter', category: 'System', code: 'Enter' },
  { value: 0x29, label: 'Escape', category: 'System', code: 'Escape' },
  { value: 0x2a, label: 'Backspace', category: 'System', code: 'Backspace' },
  { value: 0x2b, label: 'Tab', category: 'System', code: 'Tab' },
  { value: 0x2c, label: 'Space', category: 'System', code: 'Space' },
  { value: 0x39, label: 'Caps Lock', category: 'System', code: 'CapsLock' },
  { value: 0x46, label: 'Print Screen', category: 'System', code: 'PrintScreen' },
  { value: 0x47, label: 'Scroll Lock', category: 'System', code: 'ScrollLock' },
  { value: 0x48, label: 'Pause', category: 'System', code: 'Pause' },
  { value: 0x65, label: 'Context Menu', category: 'System', code: 'ContextMenu' },

  // Punctuation
  { value: 0x2d, label: '-', category: 'Punctuation', code: 'Minus' },
  { value: 0x2e, label: '=', category: 'Punctuation', code: 'Equal' },
  { value: 0x2f, label: '[', category: 'Punctuation', code: 'BracketLeft' },
  { value: 0x30, label: ']', category: 'Punctuation', code: 'BracketRight' },
  { value: 0x31, label: '\\', category: 'Punctuation', code: 'Backslash' },
  { value: 0x33, label: ';', category: 'Punctuation', code: 'Semicolon' },
  { value: 0x34, label: "'", category: 'Punctuation', code: 'Quote' },
  { value: 0x35, label: '`', category: 'Punctuation', code: 'Backquote' },
  { value: 0x36, label: ',', category: 'Punctuation', code: 'Comma' },
  { value: 0x37, label: '.', category: 'Punctuation', code: 'Period' },
  { value: 0x38, label: '/', category: 'Punctuation', code: 'Slash' },

  // Navigation
  { value: 0x49, label: 'Insert', category: 'Navigation', code: 'Insert' },
  { value: 0x4a, label: 'Home', category: 'Navigation', code: 'Home' },
  { value: 0x4b, label: 'Page Up', category: 'Navigation', code: 'PageUp' },
  { value: 0x4c, label: 'Delete', category: 'Navigation', code: 'Delete' },
  { value: 0x4d, label: 'End', category: 'Navigation', code: 'End' },
  { value: 0x4e, label: 'Page Down', category: 'Navigation', code: 'PageDown' },
  { value: 0x4f, label: 'Right Arrow', category: 'Navigation', code: 'ArrowRight' },
  { value: 0x50, label: 'Left Arrow', category: 'Navigation', code: 'ArrowLeft' },
  { value: 0x51, label: 'Down Arrow', category: 'Navigation', code: 'ArrowDown' },
  { value: 0x52, label: 'Up Arrow', category: 'Navigation', code: 'ArrowUp' },

  // Function Keys
  { value: 0x3a, label: 'F1', category: 'Function', code: 'F1' },
  { value: 0x3b, label: 'F2', category: 'Function', code: 'F2' },
  { value: 0x3c, label: 'F3', category: 'Function', code: 'F3' },
  { value: 0x3d, label: 'F4', category: 'Function', code: 'F4' },
  { value: 0x3e, label: 'F5', category: 'Function', code: 'F5' },
  { value: 0x3f, label: 'F6', category: 'Function', code: 'F6' },
  { value: 0x40, label: 'F7', category: 'Function', code: 'F7' },
  { value: 0x41, label: 'F8', category: 'Function', code: 'F8' },
  { value: 0x42, label: 'F9', category: 'Function', code: 'F9' },
  { value: 0x43, label: 'F10', category: 'Function', code: 'F10' },
  { value: 0x44, label: 'F11', category: 'Function', code: 'F11' },
  { value: 0x45, label: 'F12', category: 'Function', code: 'F12' },
  { value: 0x68, label: 'F13', category: 'Function', code: 'F13' },
  { value: 0x69, label: 'F14', category: 'Function', code: 'F14' },
  { value: 0x6a, label: 'F15', category: 'Function', code: 'F15' },
  { value: 0x6b, label: 'F16', category: 'Function', code: 'F16' },
  { value: 0x6c, label: 'F17', category: 'Function', code: 'F17' },
  { value: 0x6d, label: 'F18', category: 'Function', code: 'F18' },
  { value: 0x6e, label: 'F19', category: 'Function', code: 'F19' },
  { value: 0x6f, label: 'F20', category: 'Function', code: 'F20' },
  { value: 0x70, label: 'F21', category: 'Function', code: 'F21' },
  { value: 0x71, label: 'F22', category: 'Function', code: 'F22' },
  { value: 0x72, label: 'F23', category: 'Function', code: 'F23' },
  { value: 0x73, label: 'F24', category: 'Function', code: 'F24' },

  // Keypad
  { value: 0x53, label: 'Num Lock', category: 'Keypad', code: 'NumLock' },
  { value: 0x54, label: 'Numpad /', category: 'Keypad', code: 'NumpadDivide' },
  { value: 0x55, label: 'Numpad *', category: 'Keypad', code: 'NumpadMultiply' },
  { value: 0x56, label: 'Numpad -', category: 'Keypad', code: 'NumpadSubtract' },
  { value: 0x57, label: 'Numpad +', category: 'Keypad', code: 'NumpadAdd' },
  { value: 0x58, label: 'Numpad Enter', category: 'Keypad', code: 'NumpadEnter' },
  { value: 0x59, label: 'Numpad 1', category: 'Keypad', code: 'Numpad1' },
  { value: 0x5a, label: 'Numpad 2', category: 'Keypad', code: 'Numpad2' },
  { value: 0x5b, label: 'Numpad 3', category: 'Keypad', code: 'Numpad3' },
  { value: 0x5c, label: 'Numpad 4', category: 'Keypad', code: 'Numpad4' },
  { value: 0x5d, label: 'Numpad 5', category: 'Keypad', code: 'Numpad5' },
  { value: 0x5e, label: 'Numpad 6', category: 'Keypad', code: 'Numpad6' },
  { value: 0x5f, label: 'Numpad 7', category: 'Keypad', code: 'Numpad7' },
  { value: 0x60, label: 'Numpad 8', category: 'Keypad', code: 'Numpad8' },
  { value: 0x61, label: 'Numpad 9', category: 'Keypad', code: 'Numpad9' },
  { value: 0x62, label: 'Numpad 0', category: 'Keypad', code: 'Numpad0' },
  { value: 0x63, label: 'Numpad .', category: 'Keypad', code: 'NumpadDecimal' },

  // Modifiers (as standalone keys)
  { value: 0xe0, label: 'Left Ctrl', category: 'Modifiers', code: 'ControlLeft' },
  { value: 0xe1, label: 'Left Shift', category: 'Modifiers', code: 'ShiftLeft' },
  { value: 0xe2, label: 'Left Alt', category: 'Modifiers', code: 'AltLeft' },
  { value: 0xe3, label: 'Left GUI', category: 'Modifiers', code: 'MetaLeft' },
  { value: 0xe4, label: 'Right Ctrl', category: 'Modifiers', code: 'ControlRight' },
  { value: 0xe5, label: 'Right Shift', category: 'Modifiers', code: 'ShiftRight' },
  { value: 0xe6, label: 'Right Alt', category: 'Modifiers', code: 'AltRight' },
  { value: 0xe7, label: 'Right GUI', category: 'Modifiers', code: 'MetaRight' },
];

// Fast lookup: KeyboardEvent.code string -> HID usage byte
// Built from KEYBOARD_KEYS so there's a single source of truth.
export const CODE_TO_HID = Object.fromEntries(
  KEYBOARD_KEYS.filter(k => k.code).map(k => [k.code, k.value])
);

// Set of KeyboardEvent.code values that are modifier keys.
// Used by the recorder to distinguish modifier-only vs combo keypresses.
export const MODIFIER_CODES = new Set([
  'ControlLeft', 'ControlRight',
  'ShiftLeft', 'ShiftRight',
  'AltLeft', 'AltRight',
  'MetaLeft', 'MetaRight',
]);

// Ordered list of unique categories for <optgroup> rendering.
export const KEY_CATEGORIES = [
  'Letters', 'Numbers', 'System', 'Punctuation',
  'Navigation', 'Function', 'Keypad', 'Modifiers',
];
```

**Step 2: Verify the module is importable**

Run: `node -e "const m = require('./src/renderer/data/keyboardkeys.js'); console.log(Object.keys(m.CODE_TO_HID).length, 'keys mapped'); console.log(m.KEYBOARD_KEYS.length, 'total entries');"`

This will likely fail due to ES module syntax in a CJS context. That's expected — the file uses `export` and will be consumed by webpack. Just verify no syntax errors by checking with the project's build:

Run: `cd /Users/marciorodrigues/Projects/razer-macos && npx webpack --config webpack.renderer.config.js 2>&1 | tail -5`

If the project doesn't have a standalone renderer webpack config, just verify with `yarn dev` in the next task.

**Step 3: Commit**

```bash
git add src/renderer/data/keyboardkeys.js
git commit -m "feat: add comprehensive HID keyboard key data module"
```

---

### Task 2: Replace inline KEYBOARD_KEYS and update dropdown with optgroup

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx` (lines 1-61, 86-95, 392-423)

**Step 1: Add the import and remove inline constant**

At the top of the file, add the import:

```js
import { KEYBOARD_KEYS, CODE_TO_HID, MODIFIER_CODES, KEY_CATEGORIES } from '../data/keyboardkeys';
```

Remove the inline `KEYBOARD_KEYS` constant (lines 37-61).

**Step 2: Update the dropdown to use optgroup categories**

Replace the keyboard key `<select>` block (currently lines 413-421) with:

```jsx
<select
  value={editActionValue}
  onChange={(e) => this.setState({ editActionValue: parseInt(e.target.value) })}
  style={{ ...selectStyle, width: '100%' }}
>
  {KEY_CATEGORIES.map(cat => (
    <optgroup key={cat} label={cat}>
      {KEYBOARD_KEYS.filter(k => k.category === cat).map(kk => (
        <option key={kk.value} value={kk.value}>{kk.label}</option>
      ))}
    </optgroup>
  ))}
</select>
```

**Step 3: Verify `describeMapping` still works**

The `describeMapping` function at line 88 does `KEYBOARD_KEYS.find(k => k.value === params[2])`. Since the imported `KEYBOARD_KEYS` has the same `value`/`label` shape, this continues to work with no changes — and now resolves more keys (previously fell back to `Key 0x${hex}` for keys not in the 45-key list).

**Step 4: Test manually**

Run: `yarn dev`

1. Open a device with button mapping
2. Click a side button → select "Keyboard Key"
3. Verify the dropdown shows grouped categories (Letters, Numbers, System, etc.)
4. Verify all keys are selectable and Apply works
5. Verify existing mappings still display correctly in the grid

**Step 5: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx
git commit -m "feat: expand keyboard key dropdown with all HID keys and category groups"
```

---

### Task 3: Add recording state and methods to the component

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`

**Step 1: Add recording state to constructor**

In the constructor's `this.state` object (around line 175), add three new fields:

```js
this.state = {
  panelType: this.deviceSelected.panelType || null,
  mappings: [],
  layer: 0x00,
  editingButton: null,
  editActionType: 0x00,
  editActionValue: 0,
  editModifier: 0,
  recording: false,
  recordingModifiers: 0,
  recordingUnsupported: false,
};
```

Also add an instance variable after the state assignment:

```js
this.nonModifierPressed = false;
this.unsupportedTimer = null;
```

Bind the new methods:

```js
this.handleRecordKeyDown = this.handleRecordKeyDown.bind(this);
this.handleRecordKeyUp = this.handleRecordKeyUp.bind(this);
```

**Step 2: Add recording lifecycle methods**

Add these methods to the class:

```js
startRecording() {
  this.nonModifierPressed = false;
  this.setState({ recording: true, recordingModifiers: 0, recordingUnsupported: false });
}

stopRecording() {
  this.nonModifierPressed = false;
  if (this.unsupportedTimer) {
    clearTimeout(this.unsupportedTimer);
    this.unsupportedTimer = null;
  }
  this.setState({ recording: false, recordingModifiers: 0, recordingUnsupported: false });
}

handleRecordKeyDown(event) {
  event.preventDefault();
  event.stopPropagation();

  if (MODIFIER_CODES.has(event.code)) {
    // Modifier pressed — update live display, wait for more input
    const mods = (event.ctrlKey ? 0x01 : 0)
               | (event.shiftKey ? 0x02 : 0)
               | (event.altKey ? 0x04 : 0)
               | (event.metaKey ? 0x08 : 0);
    this.setState({ recordingModifiers: mods });
    return;
  }

  // Non-modifier pressed
  this.nonModifierPressed = true;
  const hidCode = CODE_TO_HID[event.code];

  if (hidCode === undefined) {
    // Key not in HID keyboard page — flash warning
    this.setState({ recordingUnsupported: true });
    if (this.unsupportedTimer) clearTimeout(this.unsupportedTimer);
    this.unsupportedTimer = setTimeout(() => {
      this.setState({ recordingUnsupported: false });
      this.unsupportedTimer = null;
    }, 1500);
    return;
  }

  const modifier = (event.ctrlKey ? 0x01 : 0)
                 | (event.shiftKey ? 0x02 : 0)
                 | (event.altKey ? 0x04 : 0)
                 | (event.metaKey ? 0x08 : 0);

  this.setState({
    editActionValue: hidCode,
    editModifier: modifier,
    recording: false,
    recordingModifiers: 0,
    recordingUnsupported: false,
  });
}

handleRecordKeyUp(event) {
  event.preventDefault();
  event.stopPropagation();

  if (!MODIFIER_CODES.has(event.code)) return;
  if (this.nonModifierPressed) return;

  // Modifier released with no non-modifier pressed — capture standalone modifier
  const hidCode = CODE_TO_HID[event.code];
  if (hidCode === undefined) return;

  this.setState({
    editActionValue: hidCode,
    editModifier: 0,
    recording: false,
    recordingModifiers: 0,
    recordingUnsupported: false,
  });
}
```

**Step 3: Clean up timer in componentWillUnmount**

In `componentWillUnmount()`, add:

```js
if (this.unsupportedTimer) {
  clearTimeout(this.unsupportedTimer);
  this.unsupportedTimer = null;
}
```

**Step 4: Also stop recording when cancelling edit or switching buttons**

In `cancelEditing()`:

```js
cancelEditing() {
  this.stopRecording();
  this.setState({ editingButton: null });
}
```

In `startEditing(btn)`, add at the top:

```js
this.stopRecording();
```

**Step 5: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx
git commit -m "feat: add keystroke recording state and event handlers"
```

---

### Task 4: Update renderEditor with recording UI

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`

**Step 1: Replace the keyboard key editor section**

Replace the `{editActionType === 0x02 && (...)}` block (the section that renders modifier checkboxes and key dropdown) with:

```jsx
{editActionType === 0x02 && (
  <div>
    {this.state.recording ? (
      // Recording mode
      <div>
        {/* Live modifier badges */}
        <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', alignItems: 'center' }}>
          {[
            { bit: 0x01, label: 'Ctrl' },
            { bit: 0x02, label: 'Shift' },
            { bit: 0x04, label: 'Alt' },
            { bit: 0x08, label: 'Cmd' },
          ].map(mod => (
            <span key={mod.bit} style={{
              fontSize: '10px',
              padding: '3px 8px',
              borderRadius: '10px',
              backgroundColor: (this.state.recordingModifiers & mod.bit) ? '#47e10c' : '#35363a',
              color: (this.state.recordingModifiers & mod.bit) ? 'black' : '#555',
              border: '1px solid #555',
              transition: 'all 0.1s',
            }}>{mod.label}</span>
          ))}
        </div>

        {/* Capture prompt + cancel */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{
            color: this.state.recordingUnsupported ? '#ff4444' : '#999',
            fontSize: '12px',
            animation: this.state.recordingUnsupported ? 'none' : 'pulse 1.5s ease-in-out infinite',
          }}>
            {this.state.recordingUnsupported ? 'Key not supported' : 'Press a key...'}
          </span>
          <button onClick={() => this.stopRecording()} style={btnStyle}>Cancel</button>
        </div>

        {/* Hidden input to capture keyboard events */}
        <input
          ref={el => el && el.focus()}
          onKeyDown={this.handleRecordKeyDown}
          onKeyUp={this.handleRecordKeyUp}
          onBlur={(e) => e.target.focus()}
          style={{ position: 'absolute', opacity: 0, width: 0, height: 0 }}
        />
      </div>
    ) : (
      // Normal mode: modifier checkboxes + dropdown + record button
      <div>
        <div style={{ display: 'flex', gap: '10px', marginBottom: '8px', alignItems: 'center' }}>
          {[
            { bit: 0x01, label: 'Ctrl' },
            { bit: 0x02, label: 'Shift' },
            { bit: 0x04, label: 'Alt' },
            { bit: 0x08, label: 'Cmd' },
          ].map(mod => (
            <label key={mod.bit} style={{ color: '#999', fontSize: '11px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '3px' }}>
              <input
                type="checkbox"
                checked={(editModifier & mod.bit) !== 0}
                onChange={() => this.setState({ editModifier: editModifier ^ mod.bit })}
                style={{ accentColor: '#47e10c' }}
              />
              {mod.label}
            </label>
          ))}
          <div style={{ flex: 1 }} />
          <button
            onClick={() => this.startRecording()}
            style={{ ...btnStyle, display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <span style={{
              display: 'inline-block',
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: '#ff4444',
            }} />
            Record
          </button>
        </div>
        <select
          value={editActionValue}
          onChange={(e) => this.setState({ editActionValue: parseInt(e.target.value) })}
          style={{ ...selectStyle, width: '100%' }}
        >
          {KEY_CATEGORIES.map(cat => (
            <optgroup key={cat} label={cat}>
              {KEYBOARD_KEYS.filter(k => k.category === cat).map(kk => (
                <option key={kk.value} value={kk.value}>{kk.label}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>
    )}
  </div>
)}
```

**Step 2: Add CSS pulse animation**

In `src/renderer/index.css`, add at the bottom:

```css
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
```

**Step 3: Test manually**

Run: `yarn dev`

Test the recording flow:
1. Click side button → select "Keyboard Key" → verify Record button visible with red dot
2. Click Record → verify "Press a key..." pulsing text appears, modifier badges show
3. Hold Ctrl → verify [Ctrl] badge lights up green
4. Press A → verify recording stops, Ctrl checkbox checked, dropdown shows A
5. Click Apply → verify mapping saved and grid updates

Test standalone modifier:
6. Click Record → press and release Left Shift → verify recording stops, dropdown shows Left Shift

Test cancel:
7. Click Record → click Cancel → verify returns to normal editor state

Test unsupported key:
8. Click Record → press a media key or other non-HID key → verify "Key not supported" flash

Test edge cases:
9. While recording, click a different button in the grid → verify recording stops cleanly
10. While recording, click Cancel on the editor → verify clean exit

**Step 4: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx src/renderer/index.css
git commit -m "feat: add keystroke recorder UI with Record button and live modifier badges"
```

---

### Task 5: Final polish and edge case cleanup

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`

**Step 1: Ensure recording stops on layer switch**

In `switchLayer(layer)`, add `this.stopRecording()` at the top:

```js
switchLayer(layer) {
  this.stopRecording();
  this.setState({ layer, editingButton: null }, () => {
    this.requestMappings();
  });
}
```

**Step 2: Ensure recording stops on panel change**

In `handlePanelTypeResponse` and `handlePanelChanged`, the `editingButton: null` reset already takes care of hiding the editor, but we should also reset recording state. Add to both handlers before `setState`:

In `handlePanelTypeResponse`:
```js
this.stopRecording();
```

In `handlePanelChanged`:
```js
this.stopRecording();
```

**Step 3: Test all edge cases**

Run: `yarn dev`

1. Start recording → switch Normal/Hypershift layer → verify recording stopped
2. Start recording → swap side panel (if possible) → verify clean state
3. Rapidly click Record, Cancel, Record → verify no stuck state
4. Record a key → Apply → re-open same button → verify the recorded values persisted
5. Record on one button → click a different button → verify first button's edit cancelled, second button opens fresh

**Step 4: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx
git commit -m "fix: stop keystroke recording on layer switch and panel change"
```
