# Drag-to-Swap Button Mappings + Undo/Redo

**Status:** Approved
**Date:** 2026-04-22
**Scope:** `src/renderer/sections/sectionsettingbuttonmapping.jsx` (+ one CSS rule)

## Goal

In the Razer Naga V2 Pro button-mapping UI, let the user:

1. Drag one button onto another to swap their mappings.
2. Undo/redo any mapping change (drag-swap, editor edit, restore-to-default) via on-screen buttons and `cmd+z` / `cmd+shift+z`.

## Drag-to-Swap

**Interaction**

- Each button grid cell is `draggable`.
- During drag: source cell drops to ~50% opacity.
- On `dragover` of a valid target: target cell shows a 2px `#47e10c` outline.
- Drop: swap the two buttons' mappings. Dropping on self is a no-op.
- Click-to-edit still works — HTML5 drag-and-drop distinguishes drag from click.
- Drag disabled while `state.profileSwitching` is true.

**Mechanics**

- A swap issues two `set-button-mapping` IPC calls, one per side, each with the opposite button's `{actionType, params}`. Slot 1 mirroring in the device layer is unchanged.
- The local `state.mappings` array is updated optimistically so the UI reflects the swap immediately. The authoritative `button-mappings` event from the main process later overwrites the array — any discrepancy is reconciled for free.
- "Default" (factory) buttons have defined `{actionType, params}` under `btn.defaultAction`; for swaps we treat the current `btn.mapping` as the effective value, so every button has a well-defined payload on both sides.

## Undo/Redo

**Scope**

Covers every change that calls `set-button-mapping`: drag-swaps, editor edits (`applyEdit`), and restore-to-default.

**Stack entry shape**

```js
// single change
{ type: 'single', layer, buttonId, before: {actionType, params}, after: {...} }
// atomic group (one swap = one group; one undo reverts both sides)
{ type: 'group', entries: [<single>, <single>] }
```

- Two stacks on component state: `undoStack`, `redoStack`.
- Cap undo stack at 50 entries (drop oldest on overflow).
- Any new change clears the redo stack.

**Dispatcher**

A single helper funnels every mapping change:

```js
dispatchMappingChange(changes, { fromHistory = false } = {}) { ... }
// changes: [{ buttonId, layer, actionType, params }, ...]  (1 item = single, 2+ = group)
```

Responsibilities:

1. Capture `before` for each change by reading the current mapping from `state.mappings` for the entry's `layer`. Note: `state.mappings` only holds the currently-displayed layer, so cross-layer undo entries need their `before` captured at creation time (i.e., only when dispatching on the visible layer — fine because all user-initiated edits happen on the visible layer).
2. If `!fromHistory`: push one entry to `undoStack` (trim to 50), clear `redoStack`.
3. Send one `set-button-mapping` IPC per change.
4. Optimistically update `state.mappings` (only for entries whose `layer === state.layer`) so UI reflects the change before the main-process round trip.

Existing call sites (`applyEdit`, restore-default inside `applyEdit`, new drag-drop handler) route through this helper.

**Undo / Redo handlers**

```js
handleUndo() {
  // pop from undoStack; if entry.layer !== state.layer, switch layer first.
  // dispatch the reverse changes with fromHistory: true.
  // push the popped entry onto redoStack.
}
handleRedo() { /* symmetric */ }
```

When the entry's `layer` differs from the current `state.layer`, auto-switch the layer view first so the user sees the reverted change.

**Lifetime / clearing**

Both stacks are cleared when the user's editable surface changes underneath them:

- Profile switch (`profile-switched` received)
- Save-to-slot (`profile-saved` received)
- Clear-slot if it hits the active profile (`slot-cleared` with `slot === activeProfile`)
- Device selection change (`deviceSelected` changes)
- Panel type change (`panel-type-changed` received)

Layer toggle does NOT clear — one stack covers both layers per profile.

**UI**

- Two compact buttons (`↶ Undo`, `↷ Redo`) placed in the row adjacent to the Normal/Hypershift toggle.
- Greyed and `disabled` when the respective stack is empty.
- Keyboard shortcuts registered on `document` in `componentDidMount`, removed in `componentWillUnmount`:
  - `cmd+z` (metaKey + 'z', no shift) → undo
  - `cmd+shift+z` (metaKey + shiftKey + 'z') → redo
  - Both guards: only trigger if this section is mounted and `buttonMappingFeature != null`; ignore when `profileSwitching` is true; ignore when the event target is an `<input>` or editor cell (to avoid stealing shortcuts inside the editor).

## Files Touched

| File | Change |
|------|--------|
| `src/renderer/sections/sectionsettingbuttonmapping.jsx` | Drag handlers on grid cells; `dispatchMappingChange` helper; refactor `applyEdit` to route through it; `undoStack` / `redoStack` state; `handleUndo` / `handleRedo`; keyboard listener in lifecycle hooks; Undo/Redo buttons in the toggle row; stack clears on the five listed events. |
| `src/renderer/index.css` | One class rule: `.button-cell--drop-target { outline: 2px solid #47e10c; outline-offset: -2px; }` |

## Non-Goals

- Persisting history across app restarts.
- Touch support.
- Multi-select drag.
- Undoing profile switches themselves.
- A transient toast with an inline Undo button (covered by the history stack + keyboard shortcuts).

## Risk Notes

- `set-button-mapping` IPC is fire-and-forget in the current code — failures are silent. Undo/redo inherits this. If a write fails, the authoritative `button-mappings` event will still rewrite local state shortly, so divergence self-heals, but a temporarily wrong optimistic state could be briefly visible.
- The renderer cannot distinguish the active profile changing *because of our own save-to-slot* from some external cause; both clear the stack. This is intentional — the state model underneath the stack changed.
