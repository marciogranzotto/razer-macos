# Naga V2 Pro Per-Profile Protocol — Rewrite Implementation Plan (Phases 3 + 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the confirmed fork decisions from preflight to fix the per-profile DPI, per-profile button mapping, active-profile-tracking, and mirror-to-slot-1 bugs; clean up diagnostics; produce a final protocol reference doc.

**Architecture:** Three layers change. In the C driver, fix one command ID (`0x05:0x82 → 0x05:0x02` for GET_ACTIVE_PROFILE) and delete two architecturally-wrong functions (`razer_mouse_attr_*_dpi_profile`). In the device layer (`razerdevicemouse.js`), replace the mirror-to-slot-1 pattern with honest reads/writes: DPI uses standard VARSTORE (Fork A, so writes implicitly target the hardware-active slot); button mapping uses the existing driver bindings (Fork B, real per-slot addressing). `switchProfile` becomes a thin `SET_ACTIVE_PROFILE + re-read live state` wrapper. `saveToSlot` becomes `SET_ACTIVE_PROFILE(targetSlot) + VARSTORE DPI write + per-slot button writes`. Validation is the session-report smoke tests (set DPI on profile N, switch away, switch back, confirm DPI persists).

**Tech Stack:** C (USB HID driver), C++ (N-API bindings), JavaScript (Electron main + device layer), Python 3 (one probe helper for verification). Node 16 per `.nvmrc`, `yarn rebuild` required after C changes.

**Preflight artifact:** `docs/naga-v2-pro-protocol-notes.md` (will be promoted to `docs/naga-v2-pro-protocol.md` in Phase 4).

**Spec:** `docs/superpowers/specs/2026-04-22-naga-v2-pro-per-profile-protocol-design.md`

**Hardware constraints (carried over from preflight):**
- Slot 2 is a real user-configured profile. Do not overwrite slot 2's contents. The rewrite does not target slot 2 specifically, but the smoke tests in Task 10 must avoid slot 2 as a write target. Reading slot 2 is OK.
- Don't touch button `0x01` (primary left-click) — only side-panel buttons are valid test targets.
- Keep DPI markers reasonable (~6000–7000); no sub-1000 values.

---

## File structure map

| File | Change | Responsibility |
|------|--------|----------------|
| `librazermacos/src/lib/razermouse_driver.c` | modify, delete | C driver: fix `0x05:0x82 → 0x05:0x02`; delete `razer_mouse_attr_{read,write}_dpi_profile` |
| `src/driver/addon.cc` | delete bindings | N-API: remove `MouseGetDpiProfile` / `MouseSetDpiProfile` functions and their `exports.Set` registrations |
| `build/Release/addon.node` | regenerated | Native binary: `yarn rebuild` produces this |
| `src/main/device/razerdevicemouse.js` | extensive rewrite | Device layer: DPI via VARSTORE, no mirror, thin `switchProfile`, `saveToSlot` uses SET_PROFILE pattern |
| `scripts/probes/naga-v2-pro-probe.js` | delete in Phase 4 | One-off probe script |
| `scripts/probes/verify-rewrite.js` | create in Task 3, delete in Phase 4 | Throwaway verification probe run after driver rebuild |
| `docs/naga-v2-pro-protocol-notes.md` | delete in Phase 4 | Working notes (promoted to final) |
| `docs/naga-v2-pro-protocol.md` | create in Phase 4 | Final protocol reference |

Files that stay: `captures/*.py` (useful capture-analysis tooling for any future protocol work), `src/driver/addon.cc` bindings for button-mapping and active-profile (they work correctly), and all IPC handlers in `src/main/application.js` (no changes needed — the signatures from `a72aff9` already work).

---

## Preconditions

- On branch `feature/naga-v2-pro-side-buttons` with the preflight commits merged.
- Naga V2 Pro wired connected (`pid=0xa7`).
- Electron dev server (`yarn dev`) NOT running during tasks that touch the native addon — it holds exclusive USB access. User must stop `yarn dev` before Tasks 3, 4 (verification & smoke), and restart after.
- Working directory clean or only with expected in-progress changes.

---

## Phase 3 — Rewrite

### Task 1: Fix GET_ACTIVE_PROFILE command ID (0x05:0x82 → 0x05:0x02)

**Files:**
- Modify: `librazermacos/src/lib/razermouse_driver.c:2473-2479`

**Rationale:** Probe 2 confirmed the device NAKs `0x05:0x82` on every call; the correct read command per Synapse captures is `0x05:0x02`.

- [ ] **Step 1: Edit the driver function**

Open `librazermacos/src/lib/razermouse_driver.c`. Find (around line 2473):

```c
unsigned char razer_mouse_attr_read_active_profile(IOUSBDeviceInterface **usb_dev)
{
    struct razer_report report = get_razer_report(0x05, 0x82, 0x01);
    report.transaction_id.id = 0x1f;
    struct razer_report response_report = razer_send_payload(usb_dev, &report);
    return response_report.arguments[0];
}
```

Change `0x82` to `0x02`:

```c
unsigned char razer_mouse_attr_read_active_profile(IOUSBDeviceInterface **usb_dev)
{
    struct razer_report report = get_razer_report(0x05, 0x02, 0x01);
    report.transaction_id.id = 0x1f;
    struct razer_report response_report = razer_send_payload(usb_dev, &report);
    return response_report.arguments[0];
}
```

- [ ] **Step 2: Commit**

```bash
git add librazermacos/src/lib/razermouse_driver.c
git commit -m "fix(driver): correct GET_ACTIVE_PROFILE command ID to 0x05:0x02"
```

(Do NOT rebuild yet — Task 2 also changes this file; rebuild once after both.)

---

### Task 2: Delete broken per-slot DPI driver functions and N-API bindings

**Files:**
- Modify: `librazermacos/src/lib/razermouse_driver.c:2496-2522` (delete two functions)
- Modify: `librazermacos/src/lib/razermouse_driver.h` (delete corresponding prototypes if present)
- Modify: `src/driver/addon.cc:1049-1067` (delete `MouseGetDpiProfile` and `MouseSetDpiProfile` definitions)
- Modify: `src/driver/addon.cc:1117-1118` (delete `exports.Set("mouseGetDpiProfile", ...)` and `exports.Set("mouseSetDpiProfile", ...)`)

**Rationale:** Preflight Probe 3 confirmed Fork A for DPI — these per-slot functions are architecturally wrong. The write-command wrapper sends `0x04:0x05` with `arg[0]=profile`, but `0x04:0x05` is the standard VARSTORE DPI command where `arg[0]` must be a VARSTORE flag. The read (`0x04:0x86`) returns garbage. Both are unsalvageable; delete rather than repurpose.

- [ ] **Step 1: Delete the two driver functions**

In `librazermacos/src/lib/razermouse_driver.c`, find and delete this block (around line 2496–2522):

```c
int razer_mouse_attr_read_dpi_profile(IOUSBDeviceInterface **usb_dev, unsigned char profile,
    unsigned short *dpi_x, unsigned short *dpi_y)
{
    struct razer_report report = get_razer_report(0x04, 0x86, 0x07);
    report.transaction_id.id = 0x1f;
    report.arguments[0] = profile;

    struct razer_report response_report = razer_send_payload(usb_dev, &report);
    *dpi_x = (response_report.arguments[1] << 8) | (response_report.arguments[2] & 0xFF);
    *dpi_y = (response_report.arguments[3] << 8) | (response_report.arguments[4] & 0xFF);
    return 0;
}

void razer_mouse_attr_write_dpi_profile(IOUSBDeviceInterface **usb_dev, unsigned char profile,
    unsigned short dpi_x, unsigned short dpi_y)
{
    struct razer_report report = get_razer_report(0x04, 0x05, 0x07);
    report.transaction_id.id = 0x1f;
    report.arguments[0] = profile;
    report.arguments[1] = (dpi_x >> 8) & 0x00FF;
    report.arguments[2] = dpi_x & 0x00FF;
    report.arguments[3] = (dpi_y >> 8) & 0x00FF;
    report.arguments[4] = dpi_y & 0x00FF;
    report.arguments[5] = 0x00;
    report.arguments[6] = 0x00;
    razer_send_payload(usb_dev, &report);
}
```

- [ ] **Step 2: Delete prototypes from the header (if present)**

Open `librazermacos/src/lib/razermouse_driver.h`. Grep for `razer_mouse_attr_read_dpi_profile` and `razer_mouse_attr_write_dpi_profile`. If either appears, delete those prototype lines. If the header does not declare them, no change.

Run this to check:
```bash
grep -n "razer_mouse_attr_read_dpi_profile\|razer_mouse_attr_write_dpi_profile" librazermacos/src/lib/razermouse_driver.h
```

If output is empty: no change needed. Otherwise, remove those lines.

- [ ] **Step 3: Delete N-API wrappers in addon.cc**

In `src/driver/addon.cc`, find and delete (around line 1049-1067):

```cpp
Napi::Value MouseGetDpiProfile(const Napi::CallbackInfo &info) {
    Napi::Env env = info.Env();
    RazerDevice device = getRazerDeviceFor(info);
    unsigned char profile = info[1].ToNumber().Uint32Value();
    unsigned short dpi_x = 0, dpi_y = 0;
    razer_mouse_attr_read_dpi_profile(device.usbDevice, profile, &dpi_x, &dpi_y);
    Napi::Object result = Napi::Object::New(env);
    result.Set("x", Napi::Number::New(env, dpi_x));
    result.Set("y", Napi::Number::New(env, dpi_y));
    return result;
}

void MouseSetDpiProfile(const Napi::CallbackInfo &info) {
    RazerDevice device = getRazerDeviceFor(info);
    unsigned char profile = info[1].ToNumber().Uint32Value();
    unsigned short dpi_x = info[2].ToNumber().Uint32Value();
    unsigned short dpi_y = info[3].ToNumber().Uint32Value();
    razer_mouse_attr_write_dpi_profile(device.usbDevice, profile, dpi_x, dpi_y);
}
```

- [ ] **Step 4: Delete the N-API exports**

In `src/driver/addon.cc`, find (around line 1117-1118):

```cpp
    exports.Set("mouseGetDpiProfile",     Napi::Function::New(env, MouseGetDpiProfile));
    exports.Set("mouseSetDpiProfile",     Napi::Function::New(env, MouseSetDpiProfile));
```

Delete both lines.

- [ ] **Step 5: Commit**

```bash
git add librazermacos/src/lib/razermouse_driver.c librazermacos/src/lib/razermouse_driver.h src/driver/addon.cc
git commit -m "refactor(driver): delete broken per-slot DPI functions (arg[0]=slot semantics are invalid on Naga V2 Pro)"
```

---

### Task 3: Rebuild native addon and verify driver fixes

**Files:**
- Generated: `build/Release/addon.node`
- Create (throwaway): `scripts/probes/verify-rewrite.js`

**Preconditions:** `yarn dev` is not running. If it is, ask the user to stop it before proceeding.

- [ ] **Step 1: Rebuild**

Run (from project root):

```bash
yarn rebuild
```

This triggers `node-gyp rebuild` which recompiles the C driver and N-API addon. Expected: exits 0, prints `gyp info ok` near the end. Build artifact: `build/Release/addon.node`.

If the build fails: read the error, fix the syntax issue in the edited files, and retry. Common errors:
- Missing semicolons after the deletions.
- Orphan references to deleted functions elsewhere in the C file. Run `grep -n "razer_mouse_attr_read_dpi_profile\|razer_mouse_attr_write_dpi_profile" librazermacos/` — should return no matches after the deletions.

- [ ] **Step 2: Create a throwaway verification script**

Create `scripts/probes/verify-rewrite.js`:

```javascript
#!/usr/bin/env node
/**
 * Verify driver changes post-rebuild. THROWAWAY — deleted in Task 13.
 * Answers the three open questions from Task 2.8 preflight consolidation:
 *   1. Does mouseGetActiveProfile return real slot after 0x82→0x02 fix?
 *   2. Does SET_PROFILE work for non-current slots (mouseGetActiveProfile reflects it)?
 *   3. Does VARSTORE DPI change when the active slot changes?
 */

const addon = require('../../build/Release/addon.node');

const devices = addon.getAllDevices();
const naga = devices.find(d => d.productId === 0x00a7 || d.productId === 0x00a8);
if (!naga) {
  console.error('Naga V2 Pro not found');
  process.exit(1);
}
const id = naga.internalDeviceId;

console.log('=== Rewrite verification ===');
console.log();

// Q1: GET_ACTIVE_PROFILE
console.log('Q1: mouseGetActiveProfile at rest:', addon.mouseGetActiveProfile(id));
console.log('     Expected: 1–5 (a real slot). Previously returned 0 (NAK sentinel).');
console.log();

// Q2+Q3: iterate across non-slot-2 slots. Read DPI after each SET_PROFILE.
// Slot 2 is the user's reserved slot — skip it.
console.log('Q2+Q3: iterate SET_PROFILE through [3, 4, 5, 1], report active profile + standard DPI after each.');
for (const target of [3, 4, 5, 1]) {
  addon.mouseSetActiveProfile(id, target);
  const active = addon.mouseGetActiveProfile(id);
  const dpi = addon.mouseGetDpi(id);
  console.log(`  SET_PROFILE(${target}) → getActiveProfile=${active} (match=${active === target ? 'yes' : 'no'})  standard DPI=${dpi}`);
}

console.log();
console.log('Park on slot 1 (safe home).');
addon.mouseSetActiveProfile(id, 1);
console.log('Final state: active=' + addon.mouseGetActiveProfile(id) + ', DPI=' + addon.mouseGetDpi(id));
```

- [ ] **Step 3: Run verification**

```bash
node scripts/probes/verify-rewrite.js 2>&1 | tee /tmp/verify-rewrite.txt
```

Expected outcomes:

1. **Q1 PASS**: `mouseGetActiveProfile at rest` returns a value in 1..5 (not 0, and no "Command failed" messages).
2. **Q2 PASS**: Each `SET_PROFILE(N)` → `getActiveProfile=N` with `match=yes`.
3. **Q3 informative**: standard DPI changes across iterations (each slot has its own VARSTORE value) OR stays constant (single global VARSTORE despite SET_PROFILE).

**If Q1 or Q2 fails (getActiveProfile still returns 0 or doesn't match):**
- STOP. The driver fix didn't work. Escalate to the controller with the full output.
- Possible cause: `0x05:0x02` might also need a different `data_size` or `arg[0]` than what's in the current code. Re-check the capture evidence in `docs/naga-v2-pro-protocol-notes.md` command-inventory table, where `data_size=0x01` and `arg[0]` is observed.

**If Q3 shows DPI stays constant regardless of SET_PROFILE:**
- That means DPI is truly global (Fork A in the strongest sense), NOT per-profile. Note this in the commit message and in the protocol notes — it means per-profile DPI is not achievable on this hardware via VARSTORE, and `saveToSlot` can't actually give profile N a distinct DPI via VARSTORE. This changes the `saveToSlot` semantics — see Task 7 for the contingency.

- [ ] **Step 4: Commit verification script and results**

```bash
git add scripts/probes/verify-rewrite.js
git commit -m "chore(probes): add post-rebuild verification script"
```

Also record the verification findings inline in `docs/naga-v2-pro-protocol-notes.md`, appending to the existing Phase 2 section. Add:

```markdown
### Verification: post-rewrite (Task 3 of rewrite plan)

Ran: `node scripts/probes/verify-rewrite.js` after commits [sha of task 1] + [sha of task 2] + rebuild.

Full output captured at `/tmp/verify-rewrite.txt`.

Q1 — GET_ACTIVE_PROFILE after 0x82→0x02 fix: <PASS / FAIL with returned value>
Q2 — SET_PROFILE + read round-trip: <PASS (all 4 match) / FAIL (which didn't match)>
Q3 — Standard DPI changes with active slot: <yes, DPI X/Y/Z/W for slots 3/4/5/1 / no, stays at X across all slots>

Implication for Task 7 (saveToSlot):
<Per-profile DPI is / is not achievable via VARSTORE>.
```

Commit the notes update too:

```bash
git add docs/naga-v2-pro-protocol-notes.md
git commit -m "docs: record post-rebuild verification findings"
```

---

### Task 4: Rewrite device-layer `setDPI` (use VARSTORE, no mirror)

**Files:**
- Modify: `src/main/device/razerdevicemouse.js:167-187`

- [ ] **Step 1: Replace the `setDPI` method**

Find in `src/main/device/razerdevicemouse.js` (around line 167):

```javascript
  setDPI(dpi, profile = null) {
    const p = profile !== null ? profile : this.activeProfile;
    this.dpi = dpi;
    console.log(`[DPI-DIAG] setDPI(dpi=${dpi}, profile=${profile}) → p=${p}, activeProfile=${this.activeProfile}`);
    this.addon.mouseSetDpiProfile(this.internalId, p, dpi, dpi);
    // Slot 1 mirroring
    if (this.activeProfile !== 1 && p === this.activeProfile) {
      console.log(`[DPI-DIAG]   mirror → slot 1 = ${dpi}`);
      this.addon.mouseSetDpiProfile(this.internalId, 1, dpi, dpi);
    }
    // Diagnostic: read back every slot to see what actually got written
    try {
      const readbacks = [1, 2, 3, 4, 5].map(s => {
        const r = this.addon.mouseGetDpiProfile(this.internalId, s);
        return `slot${s}=${r.x}`;
      });
      console.log(`[DPI-DIAG]   read-back after write: ${readbacks.join(', ')}`);
    } catch (e) {
      console.log(`[DPI-DIAG]   read-back failed: ${e.message}`);
    }
  }
```

Replace with:

```javascript
  setDPI(dpi, profile = null) {
    // DPI on Naga V2 Pro is Fork A: the device uses a single VARSTORE DPI register
    // that is scoped to whichever profile slot is currently active. To set DPI on
    // profile N, the hardware must be on slot N; the `profile` argument is
    // a targeting hint from callers (e.g. resetToState passing profile=1).
    const p = profile !== null ? profile : this.activeProfile;
    if (p !== this.activeProfile) {
      this.addon.mouseSetActiveProfile(this.internalId, p);
      this.activeProfile = p;
    }
    this.dpi = dpi;
    this.addon.mouseSetDpi(this.internalId, dpi);
  }
```

- [ ] **Step 2: Commit**

```bash
git add src/main/device/razerdevicemouse.js
git commit -m "refactor(device): rewrite setDPI to use VARSTORE (Fork A) and remove mirror-to-slot-1"
```

---

### Task 5: Rewrite device-layer `getDPI`

**Files:**
- Modify: `src/main/device/razerdevicemouse.js:162-166`

- [ ] **Step 1: Replace the `getDPI` method**

Find (around line 162):

```javascript
  getDPI(profile = null) {
    const p = profile !== null ? profile : this.activeProfile;
    const result = this.addon.mouseGetDpiProfile(this.internalId, p);
    return result.x;
  }
```

Replace with:

```javascript
  getDPI(profile = null) {
    // DPI is VARSTORE (Fork A) — always reads from the currently-active slot.
    // If a caller wants the DPI of a specific profile, SET_PROFILE(p) must be
    // sent first. Callers that currently pass `profile` are OK: they set it
    // first via setDPI/switchProfile, then read back, so this.activeProfile
    // is already correct.
    if (profile !== null && profile !== this.activeProfile) {
      this.addon.mouseSetActiveProfile(this.internalId, profile);
      this.activeProfile = profile;
    }
    return this.addon.mouseGetDpi(this.internalId);
  }
```

- [ ] **Step 2: Commit**

```bash
git add src/main/device/razerdevicemouse.js
git commit -m "refactor(device): rewrite getDPI to use VARSTORE"
```

---

### Task 6: Rewrite `switchProfile` — remove all mirror logic

**Files:**
- Modify: `src/main/device/razerdevicemouse.js:251-281`

- [ ] **Step 1: Replace the `switchProfile` method**

Find (around line 251):

```javascript
  switchProfile(slot) {
    if (!this.panelType) return;
    console.log(`[DPI-DIAG] switchProfile(${slot}) starting, activeProfile was ${this.activeProfile}`);
    const buttons = this.getButtonsForPanel(this.panelType);
    // Read all button mappings from target slot (both layers)
    // Write them all to slot 1 to ensure live dispatch is current
    [0x00, 0x01].forEach(layer => {
      buttons.forEach(btn => {
        const mapping = this.getButtonMapping(btn.id, layer, slot);
        this.addon.mouseSetButtonMapping(this.internalId, 1, btn.id, layer, mapping.actionType, mapping.params);
      });
    });
    // Mirror DPI to slot 1
    const dpiResult = this.addon.mouseGetDpiProfile(this.internalId, slot);
    console.log(`[DPI-DIAG]   read from slot ${slot}: x=${dpiResult.x}, y=${dpiResult.y}`);
    this.addon.mouseSetDpiProfile(this.internalId, 1, dpiResult.x, dpiResult.y);
    console.log(`[DPI-DIAG]   wrote x=${dpiResult.x} to slot 1`);
    this.dpi = dpiResult.x;
    // Update local tracking (no SET_PROFILE sent — see spec note)
    this.activeProfile = slot;
    // Diagnostic: read back every slot
    try {
      const readbacks = [1, 2, 3, 4, 5].map(s => {
        const r = this.addon.mouseGetDpiProfile(this.internalId, s);
        return `slot${s}=${r.x}`;
      });
      console.log(`[DPI-DIAG]   read-back after switch: ${readbacks.join(', ')}`);
    } catch (e) {
      console.log(`[DPI-DIAG]   read-back failed: ${e.message}`);
    }
  }
```

Replace with:

```javascript
  switchProfile(slot) {
    if (!this.panelType) return;
    this.addon.mouseSetActiveProfile(this.internalId, slot);
    this.activeProfile = slot;
    // Re-read live DPI from VARSTORE so the UI reflects the new slot's value.
    this.dpi = this.addon.mouseGetDpi(this.internalId);
  }
```

- [ ] **Step 2: Commit**

```bash
git add src/main/device/razerdevicemouse.js
git commit -m "refactor(device): rewrite switchProfile — SET_PROFILE + VARSTORE re-read, no mirror"
```

---

### Task 7: Rewrite `saveToSlot` — SET_PROFILE + VARSTORE DPI + per-slot button writes

**Files:**
- Modify: `src/main/device/razerdevicemouse.js:283-298`

**Rationale:** The original read button mappings from slot 1 (where the mirror put them) and used broken per-slot DPI commands. Now: button mappings are read from the currently-active slot (Fork B reads are honest), DPI is read from VARSTORE. We SET_PROFILE(targetSlot) first so the DPI write lands on the target.

- [ ] **Step 1: Replace the `saveToSlot` method**

Find (around line 283):

```javascript
  saveToSlot(targetSlot) {
    if (!this.panelType) return;
    const buttons = this.getButtonsForPanel(this.panelType);
    // Copy all button mappings from slot 1 to target slot (both layers)
    [0x00, 0x01].forEach(layer => {
      buttons.forEach(btn => {
        const mapping = this.getButtonMapping(btn.id, layer, 1);
        this.addon.mouseSetButtonMapping(this.internalId, targetSlot, btn.id, layer, mapping.actionType, mapping.params);
      });
    });
    // Copy DPI
    const dpiResult = this.addon.mouseGetDpiProfile(this.internalId, 1);
    this.addon.mouseSetDpiProfile(this.internalId, targetSlot, dpiResult.x, dpiResult.y);
    this.addon.mouseMacroClear(this.internalId);
    this.slotOccupied[targetSlot] = true;
  }
```

Replace with:

```javascript
  saveToSlot(targetSlot) {
    if (!this.panelType) return;
    if (targetSlot < 1 || targetSlot > 5) return;
    const sourceSlot = this.activeProfile;
    const buttons = this.getButtonsForPanel(this.panelType);
    // Snapshot current button mappings from the active slot (Fork B per-slot reads are honest).
    const snapshot = [];
    [0x00, 0x01].forEach(layer => {
      buttons.forEach(btn => {
        const mapping = this.getButtonMapping(btn.id, layer, sourceSlot);
        snapshot.push({ layer, buttonId: btn.id, actionType: mapping.actionType, params: mapping.params });
      });
    });
    // Snapshot current DPI from VARSTORE.
    const dpi = this.addon.mouseGetDpi(this.internalId);
    // Switch hardware to target slot so VARSTORE DPI write lands there.
    this.addon.mouseSetActiveProfile(this.internalId, targetSlot);
    this.activeProfile = targetSlot;
    // Write button mappings to target slot (Fork B — per-slot write is honest).
    snapshot.forEach(({ layer, buttonId, actionType, params }) => {
      this.addon.mouseSetButtonMapping(this.internalId, targetSlot, buttonId, layer, actionType, params);
    });
    // Write DPI to target slot via VARSTORE (now active).
    this.addon.mouseSetDpi(this.internalId, dpi);
    this.dpi = dpi;
    // MACRO_CLEAR observed in Synapse after profile operations — preserve that convention.
    this.addon.mouseMacroClear(this.internalId);
    this.slotOccupied[targetSlot] = true;
  }
```

- [ ] **Step 2: Commit**

```bash
git add src/main/device/razerdevicemouse.js
git commit -m "refactor(device): rewrite saveToSlot to use SET_PROFILE + VARSTORE + Fork B button writes"
```

---

### Task 8: Remove mirror-to-slot-1 in `setButtonMapping`

**Files:**
- Modify: `src/main/device/razerdevicemouse.js:342-350`

- [ ] **Step 1: Replace the `setButtonMapping` method**

Find (around line 342):

```javascript
  setButtonMapping(buttonId, layer, actionType, params, profile = null) {
    const p = profile !== null ? profile : this.activeProfile;
    this.addon.mouseSetButtonMapping(this.internalId, p, buttonId, layer, actionType, params);
    // Slot 1 mirroring: when active profile is not slot 1 and we're writing to the active profile,
    // also write to slot 1 so the live dispatch profile stays current
    if (this.activeProfile !== 1 && p === this.activeProfile) {
      this.addon.mouseSetButtonMapping(this.internalId, 1, buttonId, layer, actionType, params);
    }
  }
```

Replace with:

```javascript
  setButtonMapping(buttonId, layer, actionType, params, profile = null) {
    // Button mapping on Naga V2 Pro is Fork B: mouseSetButtonMapping(arg[0]=slot)
    // writes directly to the target slot independent of the currently-active
    // profile. No mirror-to-slot-1 needed.
    const p = profile !== null ? profile : this.activeProfile;
    this.addon.mouseSetButtonMapping(this.internalId, p, buttonId, layer, actionType, params);
  }
```

- [ ] **Step 2: Commit**

```bash
git add src/main/device/razerdevicemouse.js
git commit -m "refactor(device): remove mirror-to-slot-1 in setButtonMapping (Fork B)"
```

---

### Task 9: Trust `getActiveProfile` in startup and state management

**Files:**
- Modify: `src/main/device/razerdevicemouse.js:43-48` (init block for BUTTON_MAPPING feature)
- Modify: `src/main/device/razerdevicemouse.js:92-96` (resetToState — DPI restoration)

- [ ] **Step 1: Update init() — no structural change needed, but remove the mirror-dependent `slotOccupied` default**

Find in `async init()` (around line 43):

```javascript
    if(this.hasFeature(FeatureIdentifier.BUTTON_MAPPING)) {
      this.panelType = this.getSidePanelType();
      this.activeProfile = this.getActiveProfile();
      this.slotOccupied = { 1: true, 2: false, 3: false, 4: false, 5: false };
      this.probeSlotOccupancy();
    }
```

No change needed — `this.getActiveProfile()` now works after Task 1's driver fix, so the starting `activeProfile` is correct. `probeSlotOccupancy` uses `mouseGetButtonMapping` which is honest per Fork B, so it already works.

The only pre-existing oddity is the `slotOccupied = { 1: true, ... }` hard-coded default before the probe — with an honest probe, the initial defaults are unnecessary. Change it to:

```javascript
    if(this.hasFeature(FeatureIdentifier.BUTTON_MAPPING)) {
      this.panelType = this.getSidePanelType();
      this.activeProfile = this.getActiveProfile();
      this.slotOccupied = { 1: false, 2: false, 3: false, 4: false, 5: false };
      this.probeSlotOccupancy();
    }
```

(The probe will set each slot's occupancy to its real value. Slot 1's hard-coded `true` was a legacy from when slot 1 was "always occupied by the mirror"; now we honestly report what's there.)

- [ ] **Step 2: Update `resetToState` DPI call site to pass active profile**

Find (around line 92):

```javascript
  resetToState(state) {
    super.resetToState(state);
    if(this.hasFeature(FeatureIdentifier.MOUSE_DPI)) {
      this.setDPI(state.dpi, 1);
    }
```

The `1` second argument forces DPI to slot 1 (legacy mirror). Now: pass `null` so `setDPI` uses `this.activeProfile` — DPI is restored on the currently-active slot, not forced to slot 1.

Replace with:

```javascript
  resetToState(state) {
    super.resetToState(state);
    if(this.hasFeature(FeatureIdentifier.MOUSE_DPI)) {
      this.setDPI(state.dpi);  // pass default (null) → operates on active slot
    }
```

- [ ] **Step 3: Commit**

```bash
git add src/main/device/razerdevicemouse.js
git commit -m "refactor(device): trust live getActiveProfile at startup; drop slot-1 legacy defaults"
```

---

### Task 10: Smoke test — user-run, validates all failing scenarios

**Preconditions:** user is asked to stop `yarn dev` if running, then restart after the preceding commits. The native addon is already rebuilt (Task 3). Now start Electron dev.

- [ ] **Step 1: User restarts the app**

Ask the user:

> The driver and device-layer rewrite is complete. Please stop any running `yarn dev`, then run `yarn dev` to start the app with the new code. Let me know when the app window is open and shows at least one profile slot.

Wait for the user's confirmation before continuing. Do not attempt to start `yarn dev` yourself.

- [ ] **Step 2: Smoke test 1 — DPI per-profile persistence (the Session Finding 4 scenario)**

Instructions to relay to the user:

> **Test 1 (the original failing scenario):**
> 1. In the app, switch to profile 2.
> 2. Set DPI to 6400.
> 3. Switch to profile 3.
> 4. Switch back to profile 2.
> 5. Report: is DPI still 6400 on profile 2?

Expected: DPI is 6400 on profile 2 after round-trip. If yes: the DPI fork-A rewrite works.

- [ ] **Step 3: Smoke test 2 — Button-mapping per-profile persistence**

> **Test 2:** (Avoid button 0x01 — primary click. Use any side-panel button.)
> 1. On profile 3, remap any side-panel button (e.g., the "1" key on the 12-button panel) to a distinctive action.
> 2. Switch to profile 4.
> 3. Switch back to profile 3.
> 4. Report: is that button's mapping still the distinctive action you set?

Expected: mapping persists.

- [ ] **Step 4: Smoke test 3 — Startup behavior**

> **Test 3:**
> 1. Quit the app entirely.
> 2. Re-launch via `yarn dev`.
> 3. Open the profile section.
> 4. Report: which profile does the app show as active, and does the DPI slider reflect the real DPI for that slot?

Expected: the app shows the hardware-active profile (whichever the mouse was last parked on), and DPI is sensible.

- [ ] **Step 5: Smoke test 4 — Slot 1 DPI still works**

> **Test 4:**
> 1. Switch to profile 1.
> 2. Set DPI to 6400.
> 3. Switch to profile 3.
> 4. Switch back to profile 1.
> 5. Report: is DPI still 6400 on profile 1?

Expected: DPI persists on slot 1 too (verifies the removal of mirror didn't break the formerly-special-case slot 1).

- [ ] **Step 6: Record smoke test results**

Append to `docs/naga-v2-pro-protocol-notes.md`:

```markdown
## Smoke tests (Task 10 of rewrite plan)

All run by user on `feature/naga-v2-pro-side-buttons` at SHA <paste HEAD SHA>.

- Test 1 (DPI on profile 2 survives round-trip through 3): <PASS / FAIL, with reported DPI>
- Test 2 (button mapping on profile 3 survives round-trip): <PASS / FAIL, with description>
- Test 3 (startup shows hardware-active profile + real DPI): <PASS / FAIL>
- Test 4 (slot 1 DPI persists across round-trip): <PASS / FAIL>

<Notes on any UX surprises — e.g., brief LED flicker, slider refresh delay, etc.>
```

Replace `<...>` with actual reported results. No placeholders.

- [ ] **Step 7: Commit**

```bash
git add docs/naga-v2-pro-protocol-notes.md
git commit -m "docs: record Phase 3 smoke-test results"
```

**If any test fails**: STOP. Report to the user with specifics. Do not proceed to Phase 4. The fix is likely either (a) a residual mirror call we missed, or (b) one of the three preflight open questions turning out differently than assumed. Escalate for investigation.

---

## Phase 4 — Cleanup

### Task 11: Remove all `[DPI-DIAG]` logging residue

Tasks 4, 5, 6 already removed `[DPI-DIAG]` logging in-place as part of their rewrites. This task is a final sweep to catch any stragglers in other files.

**Files:**
- Sweep search: all of `src/` and `librazermacos/`

- [ ] **Step 1: Sweep for any remaining DPI-DIAG references**

Run:

```bash
grep -rn "DPI-DIAG\|dpi-diag" src/ librazermacos/ scripts/ docs/ 2>/dev/null
```

Expected: references only in `docs/naga-v2-pro-protocol-notes.md` (historical mention, fine) and possibly in commit messages. No source-code references remain.

If any source-code hits: remove those logging statements in-place and commit:

```bash
git add <touched files>
git commit -m "chore: sweep remaining [DPI-DIAG] logging residue"
```

If no hits: skip the commit — nothing to remove.

---

### Task 12: Delete probe scripts (one-offs)

**Files:**
- Delete: `scripts/probes/naga-v2-pro-probe.js`
- Delete: `scripts/probes/verify-rewrite.js`
- Keep: `captures/*.py` (capture-analysis scripts are durable research tooling — they'll help any future protocol investigation on this or other Razer devices)

- [ ] **Step 1: Delete the probe scripts**

```bash
rm scripts/probes/naga-v2-pro-probe.js
rm scripts/probes/verify-rewrite.js
# Check if scripts/probes/ is now empty and remove the dir if so:
rmdir scripts/probes 2>/dev/null || true
# Check if scripts/ is now empty and remove it if so (likely not — may have other scripts):
rmdir scripts 2>/dev/null || true
```

- [ ] **Step 2: Commit**

```bash
git add -A scripts/
git commit -m "chore(probes): delete one-off probe scripts (preflight work complete)"
```

---

### Task 13: Promote protocol notes to final reference

**Files:**
- Delete: `docs/naga-v2-pro-protocol-notes.md`
- Create: `docs/naga-v2-pro-protocol.md`

The notes doc is the working artifact with per-phase findings and open questions. The final doc is a cleaner, reference-shaped document with one section per command actually used by the driver, with what each arg means, confirmed via the preflight work.

- [ ] **Step 1: Create the final protocol reference**

Create `docs/naga-v2-pro-protocol.md` with this content:

```markdown
# Razer Naga V2 Pro — USB Protocol Reference

**Device:** Razer Naga V2 Pro (productId 0x00A7 wired, 0x00A8 wireless)
**Status:** Verified via USB capture analysis of Synapse traffic and live on-device probes.
**Scope:** Commands used by `librazermacos` for profile management, DPI, button mapping, and brightness. Not a complete inventory of every command the device speaks.
**Related:** Working notes with full evidence trail: git log for `docs/naga-v2-pro-protocol-notes.md` (file removed after promotion; see commit history for capture-analysis traces, probe outputs, and fork-determination reasoning).

## Razer report format

90 bytes, big-endian 16-bit fields:

| byte | field | notes |
|------|-------|-------|
| 0 | status | 0x00 = host→device, 0x02 = device→host response |
| 1 | transaction_id | Echo identifier; this driver uses 0x1f |
| 2-3 | remaining_packets | Multi-packet marker (big-endian u16) |
| 4 | protocol_type | Usually 0 |
| 5 | data_size | Number of meaningful bytes in arguments |
| 6 | command_class | Functional grouping |
| 7 | command_id | Operation within class; bit 7 (0x80) often distinguishes write vs. read variants |
| 8-87 | arguments | 80 bytes; first `data_size` are meaningful |
| 88 | crc | XOR of bytes 2..87 |
| 89 | reserved | 0 |

## Commands used by this driver

### Profile management (class 0x05)

**`0x05:0x03` — SET_ACTIVE_PROFILE.** Sets the hardware's currently-active profile slot.
- `data_size = 0x01`
- `arguments[0]` = target profile index (1–5; slots 2–5 are user-configurable, slot 1 is always present)
- Response: standard ACK. Hardware NAKs when `arguments[0]` equals the currently-active slot (setting same-to-same is rejected); this NAK is harmless and should not be propagated as an error.
- Observed side effects: no visible LED/animation changes reported by user during normal app-triggered switches.
- Driver function: `razer_mouse_attr_write_active_profile` in `librazermacos/src/lib/razermouse_driver.c`.

**`0x05:0x02` — GET_ACTIVE_PROFILE.** Reads the hardware's currently-active profile slot.
- `data_size = 0x01`
- Request `arguments[0]` = 0
- Response `arguments[0]` = active profile index (1–5)
- **Previously our driver used `0x05:0x82` which NAKs on this device.** The correct command has `bit 7 clear` on the command_id, not set. This is an exception to the usual Razer read-variant convention.
- Driver function: `razer_mouse_attr_read_active_profile`.

**`0x05:0x08` — PROFILE_METADATA (observed in Synapse, not used by this driver).** Multi-packet read of profile UUID + ASCII name. Kept in decoder's command-name table for capture analysis only.

### DPI (class 0x04)

**`0x04:0x05` — SET_DPI (VARSTORE).** Sets DPI for the currently-active profile slot.
- `data_size = 0x07`
- `arguments[0]` = `VARSTORE (0x01)` flag (NOT a slot number)
- `arguments[1..2]` = DPI X (big-endian u16)
- `arguments[3..4]` = DPI Y (big-endian u16)
- `arguments[5..6]` = 0
- **Critical**: `arguments[0]` is a storage flag, not a profile index. To write DPI on profile N, send SET_ACTIVE_PROFILE(N) first. The previous driver misused this field as a slot number; slot numbers ≥ 2 are silently ignored by the device.
- Driver function: `razer_attr_write_dpi` (in `razerchromacommon.c`, via thin wrapper).

**`0x04:0x85` — GET_DPI (VARSTORE).** Reads DPI for the currently-active profile slot.
- `data_size = 0x07`
- Request `arguments[0]` = `VARSTORE (0x01)`
- Response `arguments[1..4]` = DPI X and Y (big-endian u16 each)

**Per-slot DPI reads/writes do not exist on this device.** The previously-used `0x04:0x86` with `arguments[0] = profile` returned garbage (stage-table metadata); the corresponding write had the same broken arg semantics as `0x04:0x05`. Both functions have been removed from the driver.

### Button mapping (class 0x02)

**`0x02:0x0c` — SET_BUTTON_MAPPING.** Writes a button mapping for a specific profile slot.
- `data_size = 0x0a`
- `arguments[0]` = profile index (1–5) — **this IS a real slot number (Fork B)**
- `arguments[1]` = button_id (per device side-panel layout: 0x40–0x4b, 0x50–0x55, 0x04–0x05, plus main-body ids 0x01 etc.)
- `arguments[2]` = layer (0x00 = normal, 0x01 = hypershift)
- `arguments[3]` = action_type (0x01 = mouse button, 0x02 = keyboard, 0x0a = multimedia, 0x0c = hypershift)
- `arguments[4..9]` = action params (6 bytes, semantics depend on action_type)
- Works independent of the currently-active profile. No preamble needed.
- Driver function: `razer_mouse_attr_write_button_mapping`.

**`0x02:0x8c` — GET_BUTTON_MAPPING.** Reads a button mapping for a specific profile slot.
- Same argument layout as SET; response populates `arguments[3..9]`.
- Driver function: `razer_mouse_attr_read_button_mapping`.

### Macro clear (class 0x06)

**`0x06:0x8e` — MACRO_CLEAR.** Sent by Synapse at the end of profile-related operations.
- `data_size = 0x0e`
- All 14 argument bytes = 0
- Role: housekeeping, clears transient macro state. Observed in captures around SET_ACTIVE_PROFILE and after saveToSlot.
- Driver function: `razer_mouse_attr_write_macro_clear`.

## Key protocol quirks on the Naga V2 Pro (vs openrazer conventions)

1. **GET_ACTIVE_PROFILE uses `0x02`, not `0x82`.** The typical Razer convention is "write = X, read = X | 0x80"; SET_ACTIVE_PROFILE (`0x03`) paired with GET_ACTIVE_PROFILE (`0x83`) would match that convention, but this device responds only to `0x02`.
2. **DPI is VARSTORE-only (Fork A).** `arg[0]` on `0x04:0x05` / `0x04:0x85` is the VARSTORE flag, not a slot number. Any per-slot DPI work must use SET_ACTIVE_PROFILE + VARSTORE.
3. **Button mapping is per-slot (Fork B).** `arg[0]` on `0x02:0x0c` / `0x02:0x8c` is a real slot number; reads and writes are honest independent of active profile.
4. **SET_ACTIVE_PROFILE on the already-active slot NAKs.** Harmless; driver should not surface this as an error to callers.

## References in the code

- Driver: `librazermacos/src/lib/razermouse_driver.c` (profile & button functions)
- Common protocol: `librazermacos/src/lib/razerchromacommon.c` (DPI VARSTORE helpers)
- N-API bindings: `src/driver/addon.cc`
- Device layer: `src/main/device/razerdevicemouse.js`
- USB captures used for verification: `captures/razer-naga-pannel-swaps.pcapng` plus `captures/*.py` analyzers
```

- [ ] **Step 2: Delete the working notes**

```bash
rm docs/naga-v2-pro-protocol-notes.md
```

- [ ] **Step 3: Commit**

```bash
git add docs/naga-v2-pro-protocol.md
git add -A docs/naga-v2-pro-protocol-notes.md
git commit -m "docs: promote Naga V2 Pro protocol notes to final reference"
```

---

## Self-Review Summary

Spec coverage check (against `docs/superpowers/specs/2026-04-22-naga-v2-pro-per-profile-protocol-design.md`):

- Phase 3 Rewrite (DPI Fork A) → Tasks 1, 2, 3, 4, 5, 6, 7, 9 ✓
- Phase 3 Rewrite (Buttons Fork B) → Tasks 6 (switchProfile simplified), 7 (saveToSlot uses Fork B), 8 (setButtonMapping no mirror) ✓
- Phase 3 Rewrite (Active profile indexing) → Tasks 1, 3 (verification), 9 (trust at startup) ✓
- Phase 3 Rewrite (Mirror removal) → Tasks 4, 5, 6, 7, 8 ✓
- Phase 3 Validation (smoke tests) → Task 10 ✓
- Phase 4 Cleanup ([DPI-DIAG] removed) → Tasks 4, 5, 6 (inline) + Task 11 (sweep) ✓
- Phase 4 Cleanup (delete probe script) → Task 12 ✓
- Phase 4 Cleanup (delete dead driver code + bindings) → Task 2 ✓
- Phase 4 Cleanup (delete mirror branches) → Tasks 4, 5, 6, 7, 8 ✓
- Phase 4 Docs (promote protocol notes) → Task 13 ✓

All spec requirements mapped. No placeholders in any task step — every step has concrete code or commands.
