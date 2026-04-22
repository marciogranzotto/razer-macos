# Naga V2 Pro — Per-Profile Protocol Correctness (Design)

**Date:** 2026-04-22
**Branch:** `feature/naga-v2-pro-side-buttons`
**Scope:** Full protocol-correctness pass for per-profile operations (DPI, button mappings, active-profile indexing, mirror-to-slot-1 assumptions).
**Prior session:** `docs/feature/naga-v2-pro-side-buttons/session-2026-04-22.md`

---

## Problem

The Naga V2 Pro "per-profile" DPI driver functions are built on a false premise. `razer_mouse_attr_write_dpi_profile` uses the same USB command (`0x04:0x05`) as the standard VARSTORE DPI write in `razerchromacommon.c:1070`, but passes `arg[0] = profile_slot (1–5)` where the standard protocol expects `arg[0] = VARSTORE (0x01)` or `NOSTORE (0x00)`. The device silently rejects writes with `arg[0] ∈ {2, 3, 4, 5}`. Reads via `0x04:0x86 + arg[0] = profile` return what appears to be DPI-stage metadata, not stored per-profile DPI.

Symptoms observed by the user (session 2026-04-22, Finding 4):

1. Set DPI 6400 while on profile 2 → mouse fast (VARSTORE write on the active slot works).
2. Switch to profile 3 → mouse slow (broken read returns garbage; mirror-to-slot-1 propagates garbage).
3. Switch back to profile 2 → DPI reverts to Synapse's original value, not the user's 6400.

Additionally:

- `razer_mouse_attr_read_active_profile` (command `0x05:0x82`) returns `0` at rest — either the device is 0-indexed or the command ID is wrong for this model.
- Button-mapping per-profile writes have never been validated. The same `arg[0]` pattern may be similarly broken.
- The current `switchProfile` / `saveToSlot` / `setDPI` / `setButtonMapping` code relies on a mirror-to-slot-1 scheme to make live behaviour appear correct. This masks the real bug and actively corrupts slot-1 data.

## Goal

Replace the broken protocol assumptions with ones that match the actual Naga V2 Pro behavior, verified against USB captures of Synapse and on-device probes. Deliver:

1. **Behavioral correctness.** Per-profile DPI and button mappings persist correctly across profile switches. Active-profile tracking is correct at startup and after switches. Matches Synapse behavior. `[DPI-DIAG]` logging removed.
2. **Protocol documentation.** `docs/naga-v2-pro-protocol.md` — a concise reference for each command we use, what `arg[0..N]` means on this device, confirmed side effects, and openrazer equivalence notes where relevant.

Not in scope:

- USB capture on Windows VM. The existing `captures/razer-naga-pannel-swaps.pcapng` is the canonical source.
- Persistent test/probe harness checked into the repo. Probes are one-shot scripts during preflight.
- Renderer-layer changes. Session `a72aff9` already refreshes the DPI slider via IPC; no further UI work is needed unless preflight reveals something unexpected.
- Other Razer devices. Any protocol-documentation spillover is incidental.
- Undo/redo persistence across restarts (prior-session Non-Goal, unchanged).

## Approach

Four phases, sequential. Each phase produces an artifact that feeds the next.

### Phase 1 — Capture analysis (primary source of truth)

Parse `captures/razer-naga-pannel-swaps.pcapng` and the `analyze_profile_switches.py` extracted data. Produce `docs/naga-v2-pro-protocol-notes.md` (working notes) containing:

- A decoded sequence table for each workflow observed: profile switch, DPI change, button remap, panel swap. Format per row: *timestamp · command_class:command_id · arg[0..N] · direction · response*.
- A per-command inventory: every `(class, cmd)` pair Synapse issues, with the observed `arg[0]` values, the observed data_size, and a best-guess semantic label.
- Specific attention to commands currently unknown to our driver: `0x05:0x02` (observed preceding per-profile DPI writes), `0x05:0x08` (large multi-packet response, likely profile metadata/name), `0x00:0x85`, `0x15:0x80`.
- A cross-check against the `.synapse4` file (`docs/profiles - 1774992262695.synapse4`) to confirm it is a Synapse configuration export rather than a USB capture, and extract any profile-shape info useful for interpreting the pcapng.

Output of Phase 1: working protocol notes + a concrete **prediction** for each of the four sub-problems (DPI, buttons, active-profile indexing, mirror logic) — specifically, which "fork" (see Phase 3) each sub-problem falls into.

### Phase 2 — On-device probes (gap-filling)

Write a short Node.js probe script (one-off, not committed long-term) that exercises the real device via the existing addon bindings and logs responses. The probe targets gaps Phase 1 cannot close:

1. **Does `SET_PROFILE(N)` actually move the active slot?**
   Sequence: `SET_PROFILE(2)` → standard VARSTORE `GET_DPI` → change DPI → `SET_PROFILE(3)` → `SET_PROFILE(2)` → VARSTORE `GET_DPI`. Expected: the DPI read after returning to slot 2 matches the value written.

2. **What does `GET_ACTIVE_PROFILE` return at rest, and after `SET_PROFILE(N)`?**
   Determines whether Finding 1 is a 0-indexing quirk (normalize at device-layer boundary) or a wrong command ID (driver fix).

3. **`SET_DPI` arg[0] semantics.** Write DPI values with `arg[0] ∈ {0, 1, 2, 3, 4, 5}` and read back via standard VARSTORE after each. Determines whether `arg[0]` is VARSTORE-flag, slot-number, or something that requires a preamble command (e.g., `0x05:0x02`) to make slot addressing valid.

4. **Same three probes for button-mapping write** (`mouseSetButtonMapping` under varying `profile` args, with and without preceding `SET_PROFILE`).

5. **Side-effect observation.** During the probes above, user visually observes whether `SET_PROFILE` triggers a profile-indicator LED blink, lighting reset, or other visible/audible state change. User reports back as part of probe output.

6. **`GET_DPI` read variants.** Call with each plausible `arg[0]` value and compare responses. Identifies the correct per-slot read path (if any).

Output of Phase 2: confirmed answers for each sub-problem, driving the Phase 3 implementation fork selection.

### Phase 3 — Rewrite

The rewrite branches on Phase 1+2 findings. The spec does **not** pre-commit to one fork; the implementation plan will be written against the confirmed fork.

**Fork A — `arg[0]` is a VARSTORE flag (no per-slot addressing).**

- Driver: delete `razer_mouse_attr_read_dpi_profile` and `razer_mouse_attr_write_dpi_profile`. Expose thin wrappers around `razer_chroma_misc_set_dpi_xy` / `razer_chroma_misc_get_dpi_xy` (standard VARSTORE). All DPI ops target the hardware's currently-active slot.
- Device layer: `setDPI(dpi)` is a single VARSTORE write. `switchProfile(slot)` is `SET_PROFILE(slot)` + re-read live state. `saveToSlot(targetSlot)` is `SET_PROFILE(targetSlot)` + write current values. Whether to `SET_PROFILE` back to the previous active after a save is determined by Phase 1 — specifically, whether the captured Synapse flow returns to the prior profile after a save-to-slot operation or leaves the switch visible. Match Synapse's behavior.
- Same pattern for button-mapping if the button-write probe confirms the symmetric bug.

**Fork B — `arg[0]` is a real slot number, requires a preamble.**

- Driver: keep the per-profile functions; internally send the preamble (e.g., `0x05:0x02`) before the write, OR expose the preamble as a separate binding and let the device layer orchestrate. Decision based on whether Synapse sends the preamble once-per-edit-session or once-per-write.
- Device layer: thinner than Fork A (fewer `SET_PROFILE` calls), but still eliminates the mirror-to-slot-1 hack.

**Sub-problem decisions, independent per-command:**

- **DPI:** Fork A or Fork B, per probe 3.
- **Buttons:** Fork A or Fork B, per probe 4. May diverge from DPI.
- **Active profile indexing:** 0-indexed-hardware → normalize at device-layer boundary (renderer stays 1–5). Wrong-command-id → fix driver command.
- **Mirror-to-slot-1:** in both forks, the mirror is removed entirely. Once the underlying read/write is honest, the mirror is actively harmful (it overwrites user slot-1 data).

**Active-profile tracking.** `this.activeProfile` in `razerdevicemouse.js` is kept in sync with every `SET_PROFILE` we issue and every `profile-switched` event we emit. We gate outgoing `SET_PROFILE` calls on "target slot differs from tracked active" to minimize hardware churn — important if Phase 2 confirms visible side effects.

**IPC / renderer.** No changes planned. Existing `profile-switched` / `slot-cleared` replies (already including `dpi`) continue to flow; the renderer's `useEffect` prop-sync handles display updates. If preflight reveals a surprise requiring renderer work, it gets a follow-up spec.

### Phase 4 — Documentation and cleanup

- Promote `docs/naga-v2-pro-protocol-notes.md` (working) into `docs/naga-v2-pro-protocol.md` (reference). One section per command actually used by our driver: `0x04:0x05`, `0x04:0x85` or `0x04:0x86` (whichever is correct), `0x05:0x03`, `0x05:0x82`, `0x06:0x8e`, plus any newly-decoded command Synapse issues that we adopt. Each section: purpose, arg layout, side effects, openrazer-equivalence note.
- Remove `[DPI-DIAG]` logging (the console.log calls added in commit `6d4e26c`). Deliberately retained through Phases 1–3 so validation can observe traffic; removed in the final cleanup commit.
- Delete dead code: broken per-profile driver functions if Fork A, their N-API bindings in `src/driver/addon.cc`, the mirror-to-slot-1 branches in `setDPI` / `setButtonMapping` / `switchProfile` / `saveToSlot`, and `slotOccupied` probing that depends on broken read semantics (re-base if still useful after protocol fix).
- Delete the one-off probe script from Phase 2. Protocol doc is the durable artifact.

## Validation

- **Preflight itself is the primary correctness gate.** Phase 2 probes establish what Synapse does; Phase 3 verifies our driver does the same.
- **Manual smoke tests post-rewrite**, matching the failing scenarios from the session report:
  1. On profile 2, set DPI 6400 → switch to profile 3 → switch back to profile 2 → DPI is still 6400. (DPI acceptance criterion.)
  2. On profile 2, set a distinctive button mapping → switch to profile 3 → switch back → mapping persists. (Button acceptance criterion.)
  3. Kill-and-relaunch the app. `this.activeProfile` matches the hardware's physically-active slot; UI reflects correct DPI and mappings for that slot. (Startup acceptance criterion.)
  4. On profile 1, set DPI 6400 → switch to profile 2 → switch back to profile 1 → DPI is still 6400 (slot-1 is not a special case after the mirror is removed; verify it).
- No automated tests (consistent with the project's current test posture and with Bar 2 which declined a persistent harness).

## Risks and open questions

- **`SET_PROFILE` side effects.** If Phase 2 observation shows multi-second LED animation or HID re-enumeration on every `SET_PROFILE`, the architecture must still minimize calls even beyond the "track locally" mitigation. If side effects are prohibitive, the spec may need to be reopened to consider alternative flows (e.g., batch reads of all five slots once on startup and cache).
- **Probes may reveal a command the captures don't show.** Preflight is cheap to extend; we iterate rather than treating Phase 1+2 as one-shot.
- **DPI and buttons may land in different forks.** Accepted; the design accommodates it, but it adds complexity to the final driver surface.
- **Synapse-written values we don't recognize.** Reads after the rewrite may return values that look wrong but are actually correct — because Synapse previously wrote something we don't understand. Do not "fix" unrecognized values; document in the protocol notes.
- **Active-profile normalization boundary.** If the hardware is 0-indexed, the device layer adds 1 on read and subtracts 1 on write. This boundary must be applied consistently — any new code path that calls the driver directly (bypassing device layer) would re-introduce the off-by-one. Mitigation: keep the normalization localized to `getActiveProfile` / `setActiveProfile` in `razerdevicemouse.js`; add a short comment on why the `+1`/`-1` exists.

## Key files expected to change

| File | Expected change |
|------|------------------|
| `librazermacos/src/lib/razermouse_driver.c` | Driver functions (rewritten, deleted, or re-based depending on fork) |
| `src/driver/addon.cc` | N-API bindings follow driver changes |
| `src/main/device/razerdevicemouse.js` | `setDPI`, `switchProfile`, `saveToSlot`, `clearSlot`, `setButtonMapping`, `getActiveProfile`, `setActiveProfile`, `probeSlotOccupancy`, and the mirror-to-slot-1 removals |
| `docs/naga-v2-pro-protocol.md` | New protocol reference |
| `docs/naga-v2-pro-protocol-notes.md` | Phase 1 working notes (may be deleted after Phase 4 promotes them) |
| `src/main/application.js` | Possibly minor, only if IPC payload shape needs adjustment |

## References

- Session report: `docs/feature/naga-v2-pro-side-buttons/session-2026-04-22.md`
- Prior-session plan (hardware profile switching): `docs/superpowers/plans/2026-03-31-hardware-profile-switching.md`
- Existing captures: `captures/razer-naga-pannel-swaps.pcapng`, `captures/analyze_profile_switches.py`, plus ~40 sibling analysis scripts
- Synapse config export (non-capture): `docs/profiles - 1774992262695.synapse4`
- Diagnostic logging (to be removed in Phase 4): commit `6d4e26c`
- C driver current state: `librazermacos/src/lib/razermouse_driver.c:2473-2522`
- Standard VARSTORE DPI reference: `librazermacos/src/lib/razerchromacommon.c:1070-1130`
