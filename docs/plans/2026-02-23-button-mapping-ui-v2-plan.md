# Button Mapping UI v2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Overhaul the Naga V2 Pro side button mapping UI with a physical-layout grid, improved editor panel, and all missing action types.

**Architecture:** Incremental refactor of two files: renderer component (`sectionsettingbuttonmapping.jsx`) for the entire UI overhaul, and main process IPC handler (`application.js`) for Hypershift two-write logic. No new files or architectural changes.

**Tech Stack:** React 16 class components, Electron IPC, inline styles (matching existing codebase conventions).

---

### Task 1: Fix multimedia sub_type bug and add keyboard modifier support to data layer

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`

**Context:** The `buildParams` function at line 222 sends sub_type `0x03` for multimedia but the USB protocol spec says it must be `0x02`. Also, keyboard key mappings don't support modifier keys (Ctrl/Shift/Alt/Cmd) — the modifier byte at params[1] is hardcoded to `0x00`.

**Step 1: Fix multimedia sub_type bug**

In `buildParams` (line 222), change the multimedia case from:
```javascript
case 0x0a: return [0x03, (actionValue >> 8) & 0xff, actionValue & 0xff, 0, 0, 0];
```
to:
```javascript
case 0x0a: return [0x02, (actionValue >> 8) & 0xff, actionValue & 0xff, 0, 0, 0];
```

**Step 2: Add `editModifier` to component state**

In the constructor (line 114-121), add `editModifier: 0` to the initial state object:
```javascript
this.state = {
  panelType: this.deviceSelected.panelType || null,
  mappings: [],
  layer: 0x00,
  editingButton: null,
  editActionType: 0x00,
  editActionValue: 0,
  editModifier: 0,
};
```

**Step 3: Update `getValueFromMapping` to extract modifier**

Update `startEditing` (line 194-201) to also extract the modifier byte:
```javascript
startEditing(btn) {
  const mapping = btn.mapping || {};
  this.setState({
    editingButton: btn.id,
    editActionType: mapping.actionType || 0x00,
    editActionValue: this.getValueFromMapping(mapping),
    editModifier: (mapping.actionType === 0x02 && mapping.params) ? (mapping.params[1] || 0) : 0,
  });
}
```

**Step 4: Update `buildParams` to use modifier for keyboard**

Change the keyboard case in `buildParams` (line 221) from:
```javascript
case 0x02: return [0x02, 0x00, actionValue, 0, 0, 0];
```
to a method that reads `this.state.editModifier`:
```javascript
case 0x02: return [0x02, modifier, actionValue, 0, 0, 0];
```

Since `buildParams` is called from `applyEdit`, update `applyEdit` to pass modifier:
```javascript
applyEdit(buttonId) {
  const { editActionType, editActionValue, editModifier } = this.state;
  const params = this.buildParams(editActionType, editActionValue, editModifier);
  ipcRenderer.send('set-button-mapping', {
    device: this.deviceSelected,
    buttonId,
    layer: this.state.layer,
    actionType: editActionType,
    params,
  });
  this.setState({ editingButton: null });
}
```

Update `buildParams` signature to accept modifier:
```javascript
buildParams(actionType, actionValue, modifier = 0) {
  switch (actionType) {
    case 0x00: return [0, 0, 0, 0, 0, 0];
    case 0x01: return [0x01, actionValue, 0, 0, 0, 0];
    case 0x02: return [0x02, modifier, actionValue, 0, 0, 0];
    case 0x0a: return [0x02, (actionValue >> 8) & 0xff, actionValue & 0xff, 0, 0, 0];
    default: return [0, 0, 0, 0, 0, 0];
  }
}
```

**Step 5: Update `describeMapping` to show modifiers**

Update the keyboard case in `describeMapping` (line 71-73) to include modifier prefix:
```javascript
case 0x02: {
  const mod = params[1] || 0;
  const key = KEYBOARD_KEYS.find(k => k.value === params[2]);
  const keyName = key ? key.label : `Key 0x${params[2].toString(16)}`;
  const mods = [];
  if (mod & 0x01) mods.push('Ctrl');
  if (mod & 0x02) mods.push('Shift');
  if (mod & 0x04) mods.push('Alt');
  if (mod & 0x08) mods.push('Cmd');
  return mods.length > 0 ? `${mods.join('+')}+${keyName}` : keyName;
}
```

**Step 6: Verify the app builds**

Run: `cd /Users/marciorodrigues/Projects/razer-macos && yarn dev`

Open the device settings window, navigate to a Naga V2 Pro. Confirm the button mapping section loads without errors.

**Step 7: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx
git commit -m "fix: multimedia sub_type bug and add keyboard modifier support

Fix buildParams sending 0x03 instead of 0x02 for multimedia sub_type.
Add editModifier state and modifier bitmask support for keyboard key
mappings, enabling Ctrl/Shift/Alt/Cmd combinations."
```

---

### Task 2: Add missing action types to constants and data functions

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`

**Context:** The protocol spec defines action types 0x0c (Hypershift), 0x12 (Scroll Wheel), and 0x06 (Sensitivity Clutch) which aren't in the UI yet. We also need a pseudo-action "Restore Default" that sends the factory default binding.

**Step 1: Add new action type constants**

Replace the `ACTION_TYPES` array (lines 12-17) with:
```javascript
const ACTION_TYPES = [
  { value: 0x00, label: 'Disabled' },
  { value: 0x01, label: 'Mouse Button' },
  { value: 0x02, label: 'Keyboard Key' },
  { value: 0x0a, label: 'Multimedia' },
  { value: 0x0c, label: 'Hypershift' },
  { value: 0x12, label: 'Scroll Wheel' },
  { value: 0x06, label: 'Sensitivity' },
  { value: 'default', label: 'Default' },
];
```

**Step 2: Add scroll wheel options constant**

Add after `MEDIA_KEYS` (after line 60):
```javascript
const SCROLL_ACTIONS = [
  { value: 0x04, label: 'Cycle Up Scroll Stages' },
];
```

**Step 3: Update `describeMapping` for new action types**

Add cases before the `default` case (before line 81):
```javascript
case 0x06: {
  const xDpi = (params[2] << 8) | params[3];
  const yDpi = (params[4] << 8) | params[5];
  return xDpi === yDpi ? `Clutch ${xDpi} DPI` : `Clutch ${xDpi}/${yDpi} DPI`;
}
case 0x12: {
  const scrollAction = SCROLL_ACTIONS.find(s => s.value === params[1]);
  return scrollAction ? scrollAction.label : `Scroll 0x${params[1].toString(16)}`;
}
```

And update the existing `case 0x0c` (line 80) to stay as-is (already returns 'Hypershift').

**Step 4: Update `buildParams` for new action types**

Add cases to `buildParams` before `default`:
```javascript
case 0x0c: return [0x01, 0x01, 0, 0, 0, 0];
case 0x12: return [0x01, actionValue, 0, 0, 0, 0];
case 0x06: {
  // actionValue encodes xDpi, modifier encodes yDpi (reusing modifier param)
  // We'll handle this specially — see Task 5 for DPI input UI
  const xDpi = (actionValue >> 16) & 0xffff;
  const yDpi = actionValue & 0xffff;
  const flags = xDpi !== yDpi ? 0x05 : 0x00;
  return [0x05, flags, (xDpi >> 8) & 0xff, xDpi & 0xff, (yDpi >> 8) & 0xff, yDpi & 0xff];
}
```

**Step 5: Update `getValueFromMapping` for new types**

Add cases to `getValueFromMapping`:
```javascript
case 0x0c: return 0;
case 0x12: return mapping.params[1] || 0x04;
case 0x06: {
  const xDpi = (mapping.params[2] << 8) | mapping.params[3];
  const yDpi = (mapping.params[4] << 8) | mapping.params[5];
  return (xDpi << 16) | yDpi;
}
```

**Step 6: Update action type change handler defaults**

In `renderEditor`, the `onChange` handler for action type selector (around line 256-262) needs defaults for new types. After the existing defaults, add:
```javascript
else if (at === 0x0c) defaultVal = 0;
else if (at === 0x12) defaultVal = 0x04;
else if (at === 0x06) defaultVal = (800 << 16) | 800; // default 800 DPI
```

**Step 7: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx
git commit -m "feat: add Hypershift, Scroll Wheel, Sensitivity Clutch, and Default action types

Add constants, param encoding/decoding, and display labels for all
missing action types from the protocol spec."
```

---

### Task 3: Replace flat button list with physical-layout grid

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`

**Context:** The current UI lists buttons in a flat scrollable list (lines 369-390 in `renderSettings`). Replace this with a CSS grid that mirrors the physical panel arrangement: 12-button = 4x3, 6-button = 2x3, 2-button = 1x2.

**Step 1: Add grid configuration constant**

Add after `PANEL_NAMES` (after line 10):
```javascript
const PANEL_GRID = {
  0x01: { columns: 2, rows: 1 },  // 2-button
  0x03: { columns: 3, rows: 4 },  // 12-button
  0x04: { columns: 3, rows: 2 },  // 6-button
};
```

**Step 2: Add grid cell style**

Add a `gridCellStyle` function (after the existing style constants, after line 105):
```javascript
function gridCellStyle(isSelected) {
  return {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '8px 4px',
    borderRadius: '6px',
    border: isSelected ? '2px solid #47e10c' : '2px solid #35363a',
    backgroundColor: isSelected ? '#35363a' : '#2a2a2e',
    cursor: 'pointer',
    minHeight: '48px',
    transition: 'border-color 0.15s',
  };
}
```

**Step 3: Replace the button list with a grid in `renderSettings`**

Replace the `{mappings.map(btn => (...))}` block (lines 369-390) with:
```javascript
{(() => {
  const grid = PANEL_GRID[panelType] || { columns: 2, rows: 1 };
  return <div style={{
    display: 'grid',
    gridTemplateColumns: `repeat(${grid.columns}, 1fr)`,
    gap: '6px',
    padding: '0 10px 10px',
  }}>
    {mappings.map(btn => (
      <div
        key={btn.id}
        onClick={() => this.startEditing(btn)}
        style={gridCellStyle(editingButton === btn.id)}
      >
        <div style={{ color: '#47e10c', fontSize: '11px', fontWeight: 'bold' }}>
          {btn.label}
        </div>
        <div style={{ color: '#999', fontSize: '9px', marginTop: '2px', textAlign: 'center' }}>
          {describeMapping(btn.mapping)}
        </div>
      </div>
    ))}
  </div>;
})()}
```

**Step 4: Move editor panel below the grid**

The editor currently renders inline within each button row. Move it to render after the grid, conditionally based on `editingButton`:
```javascript
{editingButton != null && this.renderEditor(editingButton)}
```

This goes right after the grid `</div>` closes, still inside the outer `renderSettings` return.

**Step 5: Verify the grid looks correct**

Run: `yarn dev`

Verify:
- 12-button panel shows as 4 rows x 3 columns
- 6-button panel shows as 2 rows x 3 columns
- 2-button panel shows as 1 row x 2 columns
- Clicking a cell highlights it with green border
- Editor panel appears below the grid

**Step 6: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx
git commit -m "feat: replace flat button list with physical-layout grid

Show buttons in a CSS grid matching the physical panel arrangement:
12-button = 4x3, 6-button = 2x3, 2-button = 1x2. Each cell shows
button label and current mapping. Editor panel appears below grid."
```

---

### Task 4: Redesign editor panel with pill-button action selector

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`

**Context:** The current editor uses a `<select>` dropdown for action type and dropdowns for parameters. Replace with pill-shaped toggle buttons for action type selection and context-specific parameter editors. Add modifier checkboxes for keyboard key type. The editor panel is rendered by `renderEditor` (lines 244-324).

**Step 1: Add pill toggle style helper**

Add after the `gridCellStyle` function:
```javascript
function pillStyle(isActive) {
  return {
    fontSize: '10px',
    padding: '4px 8px',
    borderRadius: '12px',
    border: '1px solid black',
    backgroundColor: isActive ? '#47e10c' : '#35363a',
    color: isActive ? 'black' : '#47e10c',
    cursor: 'pointer',
    outline: 'none',
    whiteSpace: 'nowrap',
  };
}
```

**Step 2: Rewrite `renderEditor` method**

Replace the entire `renderEditor` method (lines 244-324) with a new version that uses:

1. **Header:** Shows button label from mappings array + Cancel/Apply.
2. **Action type pills:** Row of pills for each `ACTION_TYPES` entry, wrapping to multiple lines with `flexWrap: 'wrap'`.
3. **Parameter sections:**
   - Mouse Button (0x01): pills for each `MOUSE_BUTTONS` entry
   - Keyboard Key (0x02): modifier checkboxes row + key dropdown
   - Multimedia (0x0a): pills for each `MEDIA_KEYS` entry
   - Hypershift (0x0c): info text
   - Scroll Wheel (0x12): pills for each `SCROLL_ACTIONS` entry
   - Sensitivity Clutch (0x06): two number inputs for X/Y DPI
   - Default: info text

```javascript
renderEditor(btnId) {
  const { editActionType, editActionValue, editModifier, mappings } = this.state;
  const btn = mappings.find(b => b.id === btnId);
  const btnLabel = btn ? btn.label : `Button 0x${btnId.toString(16)}`;

  return <div style={{
    padding: '10px',
    backgroundColor: '#2a2a2e',
    borderTop: '1px solid #47e10c',
    margin: '0 10px 10px',
    borderRadius: '0 0 6px 6px',
  }}>
    {/* Header */}
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
      <span style={{ color: '#47e10c', fontSize: '12px', fontWeight: 'bold' }}>{btnLabel}</span>
      <div style={{ display: 'flex', gap: '5px' }}>
        <button onClick={() => this.cancelEditing()} style={btnStyle}>Cancel</button>
        <button onClick={() => this.applyEdit(btnId)}
          style={{ ...btnStyle, backgroundColor: '#47e10c', color: 'black' }}
        >Apply</button>
      </div>
    </div>

    {/* Action type pills */}
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '10px' }}>
      {ACTION_TYPES.map(at => (
        <button
          key={at.value}
          onClick={() => {
            let defaultVal = 0;
            if (at.value === 0x01) defaultVal = 0x01;
            else if (at.value === 0x02) defaultVal = 0x04;
            else if (at.value === 0x0a) defaultVal = 0x00cd;
            else if (at.value === 0x12) defaultVal = 0x04;
            else if (at.value === 0x06) defaultVal = (800 << 16) | 800;
            this.setState({ editActionType: at.value, editActionValue: defaultVal, editModifier: 0 });
          }}
          style={pillStyle(editActionType === at.value)}
        >{at.label}</button>
      ))}
    </div>

    {/* Mouse Button params */}
    {editActionType === 0x01 && (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
        {MOUSE_BUTTONS.map(mb => (
          <button key={mb.value}
            onClick={() => this.setState({ editActionValue: mb.value })}
            style={pillStyle(editActionValue === mb.value)}
          >{mb.label}</button>
        ))}
      </div>
    )}

    {/* Keyboard Key params */}
    {editActionType === 0x02 && (
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
        </div>
        <select
          value={editActionValue}
          onChange={(e) => this.setState({ editActionValue: parseInt(e.target.value) })}
          style={{ ...selectStyle, width: '100%' }}
        >
          {KEYBOARD_KEYS.map(kk => (
            <option key={kk.value} value={kk.value}>{kk.label}</option>
          ))}
        </select>
      </div>
    )}

    {/* Multimedia params */}
    {editActionType === 0x0a && (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
        {MEDIA_KEYS.map(mk => (
          <button key={mk.value}
            onClick={() => this.setState({ editActionValue: mk.value })}
            style={pillStyle(editActionValue === mk.value)}
          >{mk.label}</button>
        ))}
      </div>
    )}

    {/* Hypershift info */}
    {editActionType === 0x0c && (
      <div style={{ color: '#999', fontSize: '11px' }}>
        Assigns Hypershift to this button. Both normal and Hypershift layers will be configured.
      </div>
    )}

    {/* Scroll Wheel params */}
    {editActionType === 0x12 && (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
        {SCROLL_ACTIONS.map(sa => (
          <button key={sa.value}
            onClick={() => this.setState({ editActionValue: sa.value })}
            style={pillStyle(editActionValue === sa.value)}
          >{sa.label}</button>
        ))}
      </div>
    )}

    {/* Sensitivity Clutch params */}
    {editActionType === 0x06 && (
      <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
        <label style={{ color: '#999', fontSize: '11px' }}>X DPI:
          <input type="number" min="100" max="30000" step="50"
            value={(editActionValue >> 16) & 0xffff}
            onChange={(e) => {
              const x = parseInt(e.target.value) || 800;
              const y = editActionValue & 0xffff;
              this.setState({ editActionValue: (x << 16) | y });
            }}
            style={{ ...selectStyle, width: '70px', marginLeft: '4px' }}
          />
        </label>
        <label style={{ color: '#999', fontSize: '11px' }}>Y DPI:
          <input type="number" min="100" max="30000" step="50"
            value={editActionValue & 0xffff}
            onChange={(e) => {
              const x = (editActionValue >> 16) & 0xffff;
              const y = parseInt(e.target.value) || 800;
              this.setState({ editActionValue: (x << 16) | y });
            }}
            style={{ ...selectStyle, width: '70px', marginLeft: '4px' }}
          />
        </label>
      </div>
    )}

    {/* Restore Default info */}
    {editActionType === 'default' && (
      <div style={{ color: '#999', fontSize: '11px' }}>
        Restores the factory default binding for this button.
      </div>
    )}
  </div>;
}
```

**Step 3: Verify editor works for all action types**

Run: `yarn dev`

Click each button in the grid, cycle through all action types in the editor, verify:
- Pills highlight correctly on selection
- Keyboard modifier checkboxes toggle independently
- DPI inputs accept numeric values
- Cancel/Apply buttons work
- Info text shows for Hypershift and Default types

**Step 4: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx
git commit -m "feat: redesign editor panel with pill-button action selector

Replace dropdown-based editor with pill-shaped toggle buttons for action
types and parameters. Add modifier checkboxes for keyboard combos, DPI
inputs for sensitivity clutch, and info sections for Hypershift/Default."
```

---

### Task 5: Handle Restore Default action in renderer

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`

**Context:** When the user selects "Default" and clicks Apply, the renderer should look up the button's factory default binding from the feature configuration and send that as a normal `set-button-mapping` IPC call. The defaults are already defined in `featurebuttonmapping.js` and available on each button object in `mappings` (as `btn.defaultAction`).

**Step 1: Update `applyEdit` to handle the 'default' pseudo-action**

Replace the `applyEdit` method with:
```javascript
applyEdit(buttonId) {
  const { editActionType, editActionValue, editModifier, mappings } = this.state;

  if (editActionType === 'default') {
    const btn = mappings.find(b => b.id === buttonId);
    if (btn && btn.defaultAction) {
      ipcRenderer.send('set-button-mapping', {
        device: this.deviceSelected,
        buttonId,
        layer: this.state.layer,
        actionType: btn.defaultAction.type,
        params: btn.defaultAction.params,
      });
    }
    this.setState({ editingButton: null });
    return;
  }

  const params = this.buildParams(editActionType, editActionValue, editModifier);
  ipcRenderer.send('set-button-mapping', {
    device: this.deviceSelected,
    buttonId,
    layer: this.state.layer,
    actionType: editActionType,
    params,
  });
  this.setState({ editingButton: null });
}
```

**Step 2: Verify default restore works**

Run: `yarn dev`

Change a button to "Disabled", then select "Default" and Apply. The button should revert to its factory binding (e.g., "Key 7" for 12-panel button 7).

**Step 3: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx
git commit -m "feat: implement Restore Default action for button mapping

When Default is selected, look up the factory binding from the feature
configuration and send it via the existing set-button-mapping IPC."
```

---

### Task 6: Add Hypershift two-write logic to IPC handler

**Files:**
- Modify: `src/main/application.js`

**Context:** Per the USB protocol spec, setting Hypershift Modifier (action type 0x0c) requires two USB writes: one for the normal layer (0x00) and one for the hypershift layer (0x01). The current IPC handler at lines 185-191 does a single write. We handle this transparently in the main process so the renderer doesn't need to know.

**Step 1: Update the `set-button-mapping` IPC handler**

Replace the handler (lines 185-191) with:
```javascript
ipcMain.on('set-button-mapping', (event, arg) => {
  const { device, buttonId, layer, actionType, params } = arg;
  const currentDevice = this.razerApplication.deviceManager.getByInternalId(device.internalId);
  if (!currentDevice) return;

  if (actionType === 0x0c) {
    // Hypershift Modifier requires two writes: normal layer + hypershift layer
    currentDevice.setButtonMapping(buttonId, 0x00, actionType, params);
    currentDevice.setButtonMapping(buttonId, 0x01, actionType, params);
  } else {
    currentDevice.setButtonMapping(buttonId, layer, actionType, params);
  }

  event.reply('button-mapping-updated', { buttonId, layer, actionType, params });
});
```

**Step 2: Verify Hypershift binding works**

Run: `yarn dev`

Assign Hypershift to a side button. The device should receive two writes (can confirm by checking that the binding appears on both Normal and Hypershift layers when toggling the layer selector).

**Step 3: Commit**

```bash
git add src/main/application.js
git commit -m "feat: handle Hypershift two-write protocol in IPC handler

When actionType is 0x0c (Hypershift Modifier), send two USB writes
(normal layer + hypershift layer) per the protocol spec. Transparent
to the renderer."
```

---

### Task 7: Final verification and cleanup

**Files:**
- Verify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`
- Verify: `src/main/application.js`

**Step 1: Full functional verification**

Run: `yarn dev`

Test all action types on each panel size:
- [ ] Disabled — sends all-zero params
- [ ] Mouse Button — all 5 buttons (Left, Right, Middle, Back, Forward)
- [ ] Keyboard Key — plain key, key with Ctrl, key with Shift+Alt combo
- [ ] Multimedia — all 6 media keys
- [ ] Hypershift — confirm both layers configured
- [ ] Scroll Wheel — Cycle Up Scroll Stages
- [ ] Sensitivity Clutch — same X/Y DPI, different X/Y DPI
- [ ] Restore Default — reverts to factory binding
- [ ] Layer toggle — Normal/Hypershift shows correct mappings
- [ ] Panel detection — grid layout matches panel type
- [ ] Grid layout — 12-btn=4x3, 6-btn=2x3, 2-btn=1x2

**Step 2: Check for stale code**

Ensure no dead code remains from the old flat-list or dropdown-based editor.

**Step 3: Final commit if any cleanup needed**

```bash
git add -A
git commit -m "chore: cleanup after button mapping UI v2 refactor"
```
