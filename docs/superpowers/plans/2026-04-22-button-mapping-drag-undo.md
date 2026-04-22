# Drag-to-Swap Button Mappings + Undo/Redo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user drag one button's mapping onto another to swap them, and undo/redo any mapping change (drag-swap, editor edit, restore-to-default) via on-screen buttons and `cmd+z` / `cmd+shift+z`.

**Architecture:** Single-file renderer change. All mapping writes funnel through a new `dispatchMappingChange` helper that records before/after snapshots onto a per-profile undo stack. A new drag-and-drop handler on each button cell dispatches a group of two changes (a swap). Two small buttons + a document-level keyboard listener drive undo/redo. Stacks are cleared on any event that changes the editable surface underneath the user.

**Tech Stack:** React 16 class component, Electron `ipcRenderer`, HTML5 drag-and-drop (no new deps).

**Spec:** `docs/superpowers/specs/2026-04-22-button-mapping-drag-undo-design.md`

**Testing note:** This project has no renderer test harness. All verification is manual through `yarn dev` with a physical Razer Naga V2 Pro. Each code task ends with a careful self-check; Task 4 is the integration test.

---

## File Structure

| File | Role in this plan |
|------|-------------------|
| `src/renderer/sections/sectionsettingbuttonmapping.jsx` | All code changes — dispatcher, stacks, handlers, UI buttons, drag-drop |
| `src/renderer/index.css` | One class rule for drag-over visual |

---

## Task 1: Dispatcher + Undo/Redo State Plumbing

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`

Add the central `dispatchMappingChange` helper that every mapping write will go through. Wire new state fields, route the existing `applyEdit` call sites through the helper, and clear stacks on the events listed in the spec.

- [ ] **Step 1: Extend the state shape**

In `src/renderer/sections/sectionsettingbuttonmapping.jsx`, modify the constructor's `this.state = { ... }` block (currently ending at line 172) to add four new fields. The final shape should be:

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
  activeProfile: 1,
  slotOccupied: { 1: true, 2: false, 3: false, 4: false, 5: false },
  profileSwitching: false,
  undoStack: [],
  redoStack: [],
  dragSourceId: null,
  dropTargetId: null,
};
```

- [ ] **Step 2: Add `UNDO_STACK_LIMIT` module constant**

Near the other module-level constants at the top of the file (after `MODIFIER_DEFS` around line 57), add:

```js
const UNDO_STACK_LIMIT = 50;
```

- [ ] **Step 3: Add `dispatchMappingChange` method**

Insert this method in the `SectionSettingButtonMapping` class, directly after `applyEdit` (it will be used by the refactored `applyEdit` in step 4 and by the drag-drop handler later). Place it immediately before `handleSlotClick`:

```js
  dispatchMappingChange(changes, { fromHistory = false } = {}) {
    // `changes` is an array of { buttonId, layer, actionType, params }.
    // 1 item = single; 2+ items = atomic group pushed as one stack entry.
    if (!changes || changes.length === 0) return;

    let entry = null;
    if (!fromHistory) {
      const singles = changes.map(change => {
        const beforeMapping = (change.layer === this.state.layer)
          ? (this.state.mappings.find(b => b.id === change.buttonId) || {}).mapping
          : null;
        const before = beforeMapping
          ? { actionType: beforeMapping.actionType, params: beforeMapping.params }
          : null;
        return {
          type: 'single',
          layer: change.layer,
          buttonId: change.buttonId,
          before,
          after: { actionType: change.actionType, params: change.params },
        };
      });
      entry = singles.length === 1 ? singles[0] : { type: 'group', entries: singles };
    }

    changes.forEach(change => {
      ipcRenderer.send('set-button-mapping', {
        device: this.deviceSelected,
        buttonId: change.buttonId,
        layer: change.layer,
        actionType: change.actionType,
        params: change.params,
      });
    });

    // Optimistically update local state for changes on the currently-visible layer.
    const visibleChanges = changes.filter(c => c.layer === this.state.layer);
    if (visibleChanges.length > 0) {
      this.setState(prev => ({
        mappings: prev.mappings.map(b => {
          const hit = visibleChanges.find(c => c.buttonId === b.id);
          if (!hit) return b;
          return { ...b, mapping: { ...b.mapping, actionType: hit.actionType, params: hit.params } };
        }),
      }));
    }

    if (!fromHistory && entry) {
      this.setState(prev => {
        const next = prev.undoStack.concat(entry);
        if (next.length > UNDO_STACK_LIMIT) next.shift();
        return { undoStack: next, redoStack: [] };
      });
    }
  }
```

- [ ] **Step 4: Refactor `applyEdit` to use the dispatcher**

Replace the current `applyEdit` method (lines 432-459) in its entirety with:

```js
  applyEdit(buttonId) {
    const { editActionType, editActionValue, editModifier, mappings } = this.state;

    if (editActionType === 'default') {
      const btn = mappings.find(b => b.id === buttonId);
      if (btn && btn.defaultAction) {
        this.dispatchMappingChange([{
          buttonId,
          layer: this.state.layer,
          actionType: btn.defaultAction.type,
          params: btn.defaultAction.params,
        }]);
      }
      this.setState({ editingButton: null });
      return;
    }

    const params = this.buildParams(editActionType, editActionValue, editModifier);
    this.dispatchMappingChange([{
      buttonId,
      layer: this.state.layer,
      actionType: editActionType,
      params,
    }]);
    this.setState({ editingButton: null });
  }
```

- [ ] **Step 5: Add a helper to clear stacks and wire it into the five clearing events**

Insert this helper method just above `dispatchMappingChange`:

```js
  clearHistory() {
    if (this.state.undoStack.length === 0 && this.state.redoStack.length === 0) return;
    this.setState({ undoStack: [], redoStack: [] });
  }
```

Then wire it into the existing IPC listeners and panel handlers. Modify as follows:

**5a.** Inside the `profile-switched` listener in `componentDidMount` (currently lines 201-209), call `this.clearHistory()` in the success branch alongside the existing `setState`:

```js
    ipcRenderer.on('profile-switched', (event, arg) => {
      if (!arg.error) {
        this.clearHistory();
        this.setState({ activeProfile: arg.profile, profileSwitching: false }, () => {
          this.requestMappings();
        });
      } else {
        this.setState({ profileSwitching: false });
      }
    });
```

**5b.** Inside the `slot-saved` listener (currently lines 211-217), clear history in the success branch:

```js
    ipcRenderer.on('slot-saved', (event, arg) => {
      if (!arg.error) {
        this.clearHistory();
        this.setState({ slotOccupied: arg.slotOccupied, profileSwitching: false });
      } else {
        this.setState({ profileSwitching: false });
      }
    });
```

**5c.** Inside the `slot-cleared` listener (currently lines 219-233), clear history in the success branch *only when the cleared slot equals the active profile* (i.e. when `needsRefetch`). That's the only case where mappings underneath changed:

```js
    ipcRenderer.on('slot-cleared', (event, arg) => {
      if (!arg.error) {
        const needsRefetch = (arg.slot === this.state.activeProfile);
        if (needsRefetch) this.clearHistory();
        this.setState({
          slotOccupied: arg.slotOccupied,
          activeProfile: arg.activeProfile,
          profileSwitching: false,
        }, () => {
          if (needsRefetch) this.requestMappings();
        });
      } else {
        this.setState({ profileSwitching: false });
      }
    });
```

**5d.** Inside `handlePanelTypeResponse` (currently lines 251-259), clear history only when the panel type is actually changing:

```js
  handlePanelTypeResponse(event, data) {
    const newPanel = data.panelType || null;
    if (newPanel !== this.state.panelType) {
      this.stopRecording();
      this.clearHistory();
      this.setState({ panelType: newPanel, mappings: [], editingButton: null }, () => {
        this.requestMappings();
      });
    }
  }
```

**5e.** Inside `handlePanelChanged` (currently lines 261-268), clear history unconditionally (panel swap always invalidates the current stack):

```js
  handlePanelChanged(event, data) {
    if (data.productId !== this.deviceSelected.productId) return;
    const newPanel = data.panelId || null;
    this.stopRecording();
    this.clearHistory();
    this.setState({ panelType: newPanel, mappings: [], editingButton: null }, () => {
      this.requestMappings();
    });
  }
```

Device selection change is handled automatically because the component is re-mounted when `deviceSelected` changes — no explicit clearing needed.

- [ ] **Step 6: Verify the build**

Run:

```bash
source "$HOME/.nvm/nvm.sh" && nvm use 16 >/dev/null && NODE_OPTIONS=--openssl-legacy-provider yarn compile 2>&1 | tail -20
```

Expected: `Done in ...` with no errors. Webpack may warn about unused variables if any were introduced — fix them.

- [ ] **Step 7: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx
git commit -m "$(cat <<'EOF'
feat(ui): add dispatchMappingChange helper with undo/redo stacks

Routes every button mapping write through a central dispatcher that
captures before/after snapshots. Adds undoStack/redoStack state and
clears them on profile switch, slot save, active-slot clear, and panel
type change. Refactors applyEdit to use the dispatcher. No user-visible
behavior change yet — UI handlers come in the next commits.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Undo/Redo Handlers + UI Buttons + Keyboard Shortcuts

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`

- [ ] **Step 1: Add `handleUndo` / `handleRedo` methods**

Insert both methods in the `SectionSettingButtonMapping` class, directly after `dispatchMappingChange`:

```js
  handleUndo() {
    if (this.state.profileSwitching) return;
    const { undoStack } = this.state;
    if (undoStack.length === 0) return;
    const entry = undoStack[undoStack.length - 1];
    const singles = entry.type === 'group' ? entry.entries : [entry];

    // Build reverse changes: apply each single's `before`.
    const changes = singles
      .filter(s => s.before) // skip singles with no captured before (shouldn't happen for user actions)
      .map(s => ({
        buttonId: s.buttonId,
        layer: s.layer,
        actionType: s.before.actionType,
        params: s.before.params,
      }));
    if (changes.length === 0) return;

    const targetLayer = singles[0].layer;
    const commit = () => {
      this.dispatchMappingChange(changes, { fromHistory: true });
      this.setState(prev => ({
        undoStack: prev.undoStack.slice(0, -1),
        redoStack: prev.redoStack.concat(entry),
      }));
    };
    if (targetLayer !== this.state.layer) {
      // Clear mappings so the grid doesn't briefly show wrong-layer data.
      this.setState({ layer: targetLayer, editingButton: null, mappings: [] }, () => {
        this.requestMappings();
        commit();
      });
    } else {
      commit();
    }
  }

  handleRedo() {
    if (this.state.profileSwitching) return;
    const { redoStack } = this.state;
    if (redoStack.length === 0) return;
    const entry = redoStack[redoStack.length - 1];
    const singles = entry.type === 'group' ? entry.entries : [entry];

    const changes = singles.map(s => ({
      buttonId: s.buttonId,
      layer: s.layer,
      actionType: s.after.actionType,
      params: s.after.params,
    }));

    const targetLayer = singles[0].layer;
    const commit = () => {
      this.dispatchMappingChange(changes, { fromHistory: true });
      this.setState(prev => ({
        redoStack: prev.redoStack.slice(0, -1),
        undoStack: prev.undoStack.concat(entry),
      }));
    };
    if (targetLayer !== this.state.layer) {
      this.setState({ layer: targetLayer, editingButton: null, mappings: [] }, () => {
        this.requestMappings();
        commit();
      });
    } else {
      commit();
    }
  }
```

- [ ] **Step 2: Add keyboard listener with proper guarding**

Add a bound handler in the constructor. Modify the constructor's bind block (currently lines 177-182) to add:

```js
    this.handleKeyDown = this.handleKeyDown.bind(this);
```

Then add this method to the class (place it right after `handleRedo`):

```js
  handleKeyDown(event) {
    if (!event.metaKey) return; // macOS cmd only
    if (event.key !== 'z' && event.key !== 'Z') return;

    // Don't steal the shortcut from active text inputs or during key recording.
    if (this.state.recording) return;
    const tag = event.target && event.target.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (this.buttonMappingFeature == null) return;
    if (this.state.panelType == null) return;

    event.preventDefault();
    if (event.shiftKey) {
      this.handleRedo();
    } else {
      this.handleUndo();
    }
  }
```

Register it in `componentDidMount` (append after the existing listener registrations, before the closing `}` of `componentDidMount`):

```js
    document.addEventListener('keydown', this.handleKeyDown);
```

Remove it in `componentWillUnmount` (append before the `unsupportedTimer` cleanup):

```js
    document.removeEventListener('keydown', this.handleKeyDown);
```

- [ ] **Step 3: Render Undo / Redo buttons**

Modify the Normal/Hypershift toggle row inside `renderSettings` (currently lines 822-841). Replace the entire `<div>` containing the two buttons with:

```jsx
      <div style={{ display: 'flex', padding: '0 10px 10px', gap: '5px', alignItems: 'center' }}>
        <button
          onClick={() => this.switchLayer(0x00)}
          style={{
            flex: 1, fontSize: '12px', padding: '5px', borderRadius: '15px',
            border: '1px solid black', outline: 'none', cursor: 'pointer',
            backgroundColor: layer === 0x00 ? '#47e10c' : '#35363a',
            color: layer === 0x00 ? 'black' : '#47e10c',
          }}
        >Normal</button>
        <button
          onClick={() => this.switchLayer(0x01)}
          style={{
            flex: 1, fontSize: '12px', padding: '5px', borderRadius: '15px',
            border: '1px solid black', outline: 'none', cursor: 'pointer',
            backgroundColor: layer === 0x01 ? '#47e10c' : '#35363a',
            color: layer === 0x01 ? 'black' : '#47e10c',
          }}
        >Hypershift</button>
        <button
          onClick={() => this.handleUndo()}
          disabled={this.state.undoStack.length === 0 || this.state.profileSwitching}
          title="Undo (⌘Z)"
          style={{
            fontSize: '14px', padding: '5px 10px', borderRadius: '15px',
            border: '1px solid black', outline: 'none',
            cursor: (this.state.undoStack.length === 0 || this.state.profileSwitching) ? 'default' : 'pointer',
            backgroundColor: '#35363a',
            color: this.state.undoStack.length === 0 ? '#555' : '#47e10c',
          }}
        >↶</button>
        <button
          onClick={() => this.handleRedo()}
          disabled={this.state.redoStack.length === 0 || this.state.profileSwitching}
          title="Redo (⇧⌘Z)"
          style={{
            fontSize: '14px', padding: '5px 10px', borderRadius: '15px',
            border: '1px solid black', outline: 'none',
            cursor: (this.state.redoStack.length === 0 || this.state.profileSwitching) ? 'default' : 'pointer',
            backgroundColor: '#35363a',
            color: this.state.redoStack.length === 0 ? '#555' : '#47e10c',
          }}
        >↷</button>
      </div>
```

- [ ] **Step 4: Verify the build**

```bash
source "$HOME/.nvm/nvm.sh" && nvm use 16 >/dev/null && NODE_OPTIONS=--openssl-legacy-provider yarn compile 2>&1 | tail -20
```

Expected: `Done in ...` with no errors.

- [ ] **Step 5: Smoke-test via dev server**

```bash
source "$HOME/.nvm/nvm.sh" && nvm use 16 >/dev/null && yarn dev
```

With the Naga V2 Pro connected: open the Button Mapping section, edit one button via the editor, click Apply. Verify the ↶ button becomes clickable (colored green). Click it — button should revert. Click ↷ — button should re-apply. Try the cmd+z / cmd+shift+z shortcuts. Close dev server (Ctrl-C in the terminal).

- [ ] **Step 6: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx
git commit -m "$(cat <<'EOF'
feat(ui): add undo/redo for button mapping changes

Adds ↶/↷ buttons next to the Normal/Hypershift toggle and a document-
level cmd+z / cmd+shift+z listener. Auto-switches layer when an undo
entry targets the non-visible layer. Guards against hijacking shortcuts
during key recording or while typing in inputs.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Drag-to-Swap

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`
- Modify: `src/renderer/index.css`

- [ ] **Step 1: Add drag handler methods**

Insert these methods in the `SectionSettingButtonMapping` class, directly after `handleRedo`:

```js
  handleDragStart(e, btn) {
    if (this.state.profileSwitching) {
      e.preventDefault();
      return;
    }
    e.dataTransfer.effectAllowed = 'move';
    // Firefox needs dataTransfer to be set for drag to start.
    e.dataTransfer.setData('text/plain', String(btn.id));
    this.setState({ dragSourceId: btn.id, editingButton: null });
  }

  handleDragEnd() {
    this.setState({ dragSourceId: null, dropTargetId: null });
  }

  handleDragOver(e, btn) {
    const { dragSourceId } = this.state;
    if (dragSourceId == null || dragSourceId === btn.id) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    if (this.state.dropTargetId !== btn.id) {
      this.setState({ dropTargetId: btn.id });
    }
  }

  handleDragLeave(e, btn) {
    if (this.state.dropTargetId === btn.id) {
      this.setState({ dropTargetId: null });
    }
  }

  handleDrop(e, targetBtn) {
    e.preventDefault();
    const { dragSourceId, mappings, layer } = this.state;
    this.setState({ dragSourceId: null, dropTargetId: null });
    if (dragSourceId == null || dragSourceId === targetBtn.id) return;

    const source = mappings.find(b => b.id === dragSourceId);
    const target = mappings.find(b => b.id === targetBtn.id);
    if (!source || !target || !source.mapping || !target.mapping) return;

    this.dispatchMappingChange([
      {
        buttonId: target.id,
        layer,
        actionType: source.mapping.actionType,
        params: source.mapping.params,
      },
      {
        buttonId: source.id,
        layer,
        actionType: target.mapping.actionType,
        params: target.mapping.params,
      },
    ]);
  }
```

- [ ] **Step 2: Make grid cells draggable**

Replace the cell `<div>` inside `renderButtonGrid` (currently lines 781-794) with a draggable version that also shows the drag/drop visual state:

```jsx
      {orderedMappings.map(btn => {
        const isDragSource = this.state.dragSourceId === btn.id;
        const isDropTarget = this.state.dropTargetId === btn.id;
        const baseStyle = gridCellStyle(editingButton === btn.id);
        const style = {
          ...baseStyle,
          opacity: isDragSource ? 0.4 : 1,
          outline: isDropTarget ? '2px solid #47e10c' : 'none',
          outlineOffset: isDropTarget ? '-2px' : undefined,
        };
        return (
          <div
            key={btn.id}
            draggable={!this.state.profileSwitching}
            onDragStart={(e) => this.handleDragStart(e, btn)}
            onDragEnd={() => this.handleDragEnd()}
            onDragOver={(e) => this.handleDragOver(e, btn)}
            onDragLeave={(e) => this.handleDragLeave(e, btn)}
            onDrop={(e) => this.handleDrop(e, btn)}
            onClick={() => this.startEditing(btn)}
            style={style}
          >
            <div style={{ color: '#47e10c', fontSize: '11px', fontWeight: 'bold' }}>
              {btn.label}
            </div>
            <div style={{ color: '#999', fontSize: '9px', marginTop: '2px', textAlign: 'center' }}>
              {describeMapping(btn.mapping)}
            </div>
          </div>
        );
      })}
```

(No separate CSS class needed — the inline style handles the visual. The CSS file change in Step 3 is still worth doing for the `user-select: none` to prevent text selection during drag.)

- [ ] **Step 3: Add CSS rule preventing text selection during drag**

Append to `src/renderer/index.css`:

```css
[draggable="true"] {
  -webkit-user-select: none;
  user-select: none;
}
```

- [ ] **Step 4: Verify the build**

```bash
source "$HOME/.nvm/nvm.sh" && nvm use 16 >/dev/null && NODE_OPTIONS=--openssl-legacy-provider yarn compile 2>&1 | tail -20
```

Expected: `Done in ...` with no errors.

- [ ] **Step 5: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx src/renderer/index.css
git commit -m "$(cat <<'EOF'
feat(ui): drag-to-swap button mappings

Each button cell is draggable; dropping onto another cell swaps their
mappings via a two-change group dispatched through the undo-aware
helper, so a single cmd+z reverts both sides. Drag is disabled during
profile switching.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Manual Integration Verification

**Files:** None (manual checks only)

- [x] **Step 1: Start the dev server**

```bash
source "$HOME/.nvm/nvm.sh" && nvm use 16 >/dev/null && yarn dev
```

- [x] **Step 2: Verify editor edits undo/redo**

With the Razer Naga V2 Pro connected, open Button Mapping. Pick Button 1, change its mapping via the editor, click Apply. Confirm the ↶ button lights up. Press `cmd+z`. Button reverts to the prior mapping both in the UI and (test physically by pressing the button) on the device. Press `cmd+shift+z`. Change re-applies.

- [x] **Step 3: Verify restore-to-default undo**

Pick a button with a non-default mapping. In the editor pick "Default", click Apply. ↶ active. `cmd+z` — button returns to the previous custom mapping. `cmd+shift+z` — back to default.

- [x] **Step 4: Verify drag-swap and one-shot undo**

Drag Button 7 onto Button 4. Confirm: both cells swap labels, ↶ active. `cmd+z` — both cells revert *in one press*. Physically test both buttons on the device.

- [x] **Step 5: Verify drag visual feedback**

During a drag: source cell fades to ~40% opacity. Dragging over a valid target: target shows a green outline. Drop outside grid: no change, visuals reset. Dragging onto the source itself: no swap, no outline.

- [ ] **Step 6: Verify stack limits and redo clearing**

Make 5+ edits. Press ↶ to undo two of them. Make a new edit. Confirm ↷ becomes disabled (redo cleared). Make 60+ rapid edits (hold an editor open and mash). Confirm the UI stays responsive and the oldest entries drop silently (you'll be able to undo 50 steps, not 60).

- [x] **Step 7: Verify history clears on profile switch**

Make 2 edits on profile 1. Save to slot 2 — observe ↶ disables. Switch to slot 2, make an edit, switch back to slot 1 — observe ↶ disables each switch.

- [x] **Step 8: Verify cross-layer undo auto-switches**

On Normal layer, edit Button 1. Toggle to Hypershift. Press `cmd+z`. UI should auto-switch to Normal and revert Button 1.

- [ ] **Step 9: Verify shortcut guarding**

While the editor is open and focused on the "Record Key" input (actively recording), press `cmd+z`. Expected: nothing happens in the undo stack; recording continues normally (the record handler owns the event).

- [ ] **Step 10: Verify drag disabled during profile switching**

Click an unoccupied profile slot, confirm "Save to slot?" dialog → Save. While `profileSwitching` is true (brief), attempt a drag — cells should not drag. (The window here is short; best observed by watching the ↶/↷ buttons and grid cells during the round trip.)

- [ ] **Step 11: Close dev server**

Ctrl-C in the terminal running `yarn dev`.

- [ ] **Step 12: No additional commits for Task 4** (verification-only task).

---

## Summary

| # | Task | Files |
|---|------|-------|
| 1 | Dispatcher + stacks + clearing | `sectionsettingbuttonmapping.jsx` |
| 2 | Undo/Redo handlers, buttons, keyboard | `sectionsettingbuttonmapping.jsx` |
| 3 | Drag-to-swap | `sectionsettingbuttonmapping.jsx`, `index.css` |
| 4 | Manual verification | — |
