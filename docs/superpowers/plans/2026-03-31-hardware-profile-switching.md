# Hardware Profile Switching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable reading, switching, and editing of the 5 on-board hardware profile slots on the Razer Naga V2 Pro, with slot 1 mirroring for live dispatch.

**Architecture:** New C driver functions for profile get/set/clear and per-profile DPI are exposed via N-API to the device JS layer, which owns slot 1 mirroring logic. The renderer adds a profile slot selector with SD card icons matching Synapse's On-Board Memory UI.

**Tech Stack:** C (IOKit USB HID), C++ (node-addon-api/N-API), JavaScript (Node.js/Electron), React 16

**Spec:** `docs/superpowers/specs/2026-03-31-hardware-profile-switching-design.md`

**Testing note:** This project has no unit test suite. All testing is empirical — build the native addon, run the Electron app, and verify against the physical Razer Naga V2 Pro mouse. Each task includes manual verification steps.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `librazermacos/src/lib/razermouse_driver.c` | Modify | New C functions: get/set active profile, macro clear, per-profile DPI read/write |
| `librazermacos/src/include/razermouse_driver.h` | Modify | Declare new C functions |
| `src/driver/addon.cc` | Modify | N-API wrappers for new C functions, new exports |
| `src/main/device/razerdevicemouse.js` | Modify | Un-hardcode profile byte, add activeProfile state, slot 1 mirroring, new methods (switchProfile, saveToSlot, clearSlot, probeSlotOccupancy) |
| `src/main/application.js` | Modify | New IPC handlers, modify existing handlers to pass profile |
| `src/renderer/sections/sectionsettingbuttonmapping.jsx` | Modify | Profile slot selector UI, slot occupancy state, save/switch/clear interactions |
| `src/renderer/index.css` | Modify | Styles for profile slot selector |

---

### Task 1: C Driver — Profile and Macro Clear Functions

**Files:**
- Modify: `librazermacos/src/lib/razermouse_driver.c` (append after line ~2471)
- Modify: `librazermacos/src/include/razermouse_driver.h` (append after line ~228)

- [ ] **Step 1: Add `razer_mouse_attr_read_active_profile` to the C driver**

In `razermouse_driver.c`, append after the `razer_mouse_attr_read_side_panel_type` function (around line 2471):

```c
unsigned char razer_mouse_attr_read_active_profile(IOUSBDeviceInterface **usb_dev)
{
    struct razer_report report = get_razer_report(0x05, 0x82, 0x01);
    report.transaction_id.id = 0x1f;
    struct razer_report response_report = razer_send_payload(usb_dev, &report);
    return response_report.arguments[0];
}
```

Note: uses `0x82` (high bit set) as the command ID in the request, following the same pattern as `razer_mouse_attr_read_button_mapping` which uses `0x8c`. The `razer_send_payload` function checks that the response command ID matches the request, so the request must use the read variant of the command ID.

- [ ] **Step 2: Add `razer_mouse_attr_write_active_profile` to the C driver**

Append immediately after the previous function:

```c
void razer_mouse_attr_write_active_profile(IOUSBDeviceInterface **usb_dev, unsigned char profile)
{
    struct razer_report report = get_razer_report(0x05, 0x03, 0x01);
    report.transaction_id.id = 0x1f;
    report.arguments[0] = profile;
    razer_send_payload(usb_dev, &report);
}
```

- [ ] **Step 3: Add `razer_mouse_attr_write_macro_clear` to the C driver**

Append immediately after:

```c
void razer_mouse_attr_write_macro_clear(IOUSBDeviceInterface **usb_dev)
{
    struct razer_report report = get_razer_report(0x06, 0x8e, 0x0e);
    report.transaction_id.id = 0x1f;
    razer_send_payload(usb_dev, &report);
}
```

- [ ] **Step 4: Add declarations to the header file**

In `razermouse_driver.h`, append after the `razer_mouse_attr_read_side_panel_type` declaration (around line 228):

```c
unsigned char razer_mouse_attr_read_active_profile(IOUSBDeviceInterface **usb_dev);
void razer_mouse_attr_write_active_profile(IOUSBDeviceInterface **usb_dev, unsigned char profile);
void razer_mouse_attr_write_macro_clear(IOUSBDeviceInterface **usb_dev);
```

- [ ] **Step 5: Verify compilation**

Run: `yarn rebuild`
Expected: builds successfully with no errors related to the new functions.

- [ ] **Step 6: Commit**

```bash
git add librazermacos/src/lib/razermouse_driver.c librazermacos/src/include/razermouse_driver.h
git commit -m "feat: add C driver functions for profile get/set and macro clear"
```

---

### Task 2: C Driver — Per-Profile DPI Functions

**Files:**
- Modify: `librazermacos/src/lib/razermouse_driver.c` (append after macro clear function)
- Modify: `librazermacos/src/include/razermouse_driver.h` (append declarations)

The existing `razer_chroma_misc_get_dpi_xy` and `razer_chroma_misc_set_dpi_xy` in `razerchromacommon.c` hardcode `VARSTORE` (0x01) in `report.arguments[0]`, ignoring the `variable_storage` parameter. Rather than modifying those shared functions (which could affect other device types), we add new per-profile DPI functions in the mouse driver.

- [ ] **Step 1: Add `razer_mouse_attr_read_dpi_profile` to the C driver**

Append in `razermouse_driver.c` after the macro clear function:

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
```

Note: this uses command `0x04:0x86` as observed in the USB capture. If this command fails during empirical testing, change to `0x04:0x85` (the existing single-profile command) with the profile byte in `arguments[0]`.

- [ ] **Step 2: Add `razer_mouse_attr_write_dpi_profile` to the C driver**

Append immediately after:

```c
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

- [ ] **Step 3: Add declarations to the header file**

In `razermouse_driver.h`, append:

```c
int razer_mouse_attr_read_dpi_profile(IOUSBDeviceInterface **usb_dev, unsigned char profile,
    unsigned short *dpi_x, unsigned short *dpi_y);
void razer_mouse_attr_write_dpi_profile(IOUSBDeviceInterface **usb_dev, unsigned char profile,
    unsigned short dpi_x, unsigned short dpi_y);
```

- [ ] **Step 4: Verify compilation**

Run: `yarn rebuild`
Expected: builds successfully.

- [ ] **Step 5: Commit**

```bash
git add librazermacos/src/lib/razermouse_driver.c librazermacos/src/include/razermouse_driver.h
git commit -m "feat: add per-profile DPI read/write C driver functions"
```

---

### Task 3: N-API Addon — Export New Functions

**Files:**
- Modify: `src/driver/addon.cc` (add functions before exports section, add exports)

- [ ] **Step 1: Add `MouseGetActiveProfile` wrapper**

Add before the exports section (around line 1070):

```cpp
Napi::Value MouseGetActiveProfile(const Napi::CallbackInfo &info) {
    Napi::Env env = info.Env();
    RazerDevice device = getRazerDeviceFor(info);
    unsigned char profile = razer_mouse_attr_read_active_profile(device.usbDevice);
    return Napi::Number::New(env, profile);
}
```

- [ ] **Step 2: Add `MouseSetActiveProfile` wrapper**

```cpp
void MouseSetActiveProfile(const Napi::CallbackInfo &info) {
    RazerDevice device = getRazerDeviceFor(info);
    unsigned char profile = info[1].ToNumber().Uint32Value();
    razer_mouse_attr_write_active_profile(device.usbDevice, profile);
}
```

- [ ] **Step 3: Add `MouseMacroClear` wrapper**

```cpp
void MouseMacroClear(const Napi::CallbackInfo &info) {
    RazerDevice device = getRazerDeviceFor(info);
    razer_mouse_attr_write_macro_clear(device.usbDevice);
}
```

- [ ] **Step 4: Add `MouseGetDpiProfile` wrapper**

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
```

- [ ] **Step 5: Add `MouseSetDpiProfile` wrapper**

```cpp
void MouseSetDpiProfile(const Napi::CallbackInfo &info) {
    RazerDevice device = getRazerDeviceFor(info);
    unsigned char profile = info[1].ToNumber().Uint32Value();
    unsigned short dpi_x = info[2].ToNumber().Uint32Value();
    unsigned short dpi_y = info[3].ToNumber().Uint32Value();
    razer_mouse_attr_write_dpi_profile(device.usbDevice, profile, dpi_x, dpi_y);
}
```

- [ ] **Step 6: Register all new exports**

In the exports section (around line 1075), add alongside the existing mouse exports:

```cpp
exports.Set("mouseGetActiveProfile",  Napi::Function::New(env, MouseGetActiveProfile));
exports.Set("mouseSetActiveProfile",  Napi::Function::New(env, MouseSetActiveProfile));
exports.Set("mouseMacroClear",        Napi::Function::New(env, MouseMacroClear));
exports.Set("mouseGetDpiProfile",     Napi::Function::New(env, MouseGetDpiProfile));
exports.Set("mouseSetDpiProfile",     Napi::Function::New(env, MouseSetDpiProfile));
```

- [ ] **Step 7: Rebuild and verify**

Run: `yarn rebuild`
Expected: builds successfully. The new exports are available but not yet called from JS.

- [ ] **Step 8: Commit**

```bash
git add src/driver/addon.cc
git commit -m "feat: add N-API wrappers for profile, macro clear, and per-profile DPI"
```

---

### Task 4: Device Layer — Un-hardcode Profile and Add State

**Files:**
- Modify: `src/main/device/razerdevicemouse.js`

This task modifies existing methods to accept a profile parameter and adds the `activeProfile` + `slotOccupied` state.

- [ ] **Step 1: Add `activeProfile` and `slotOccupied` initialization in `init()`**

In `razerdevicemouse.js`, inside the `init()` method, after the existing `this.panelType = this.getSidePanelType()` line (around line 44 inside the `BUTTON_MAPPING` feature block), add:

```js
this.activeProfile = this.getActiveProfile();
this.slotOccupied = { 1: true, 2: false, 3: false, 4: false, 5: false };
this.probeSlotOccupancy();
```

- [ ] **Step 2: Add `getActiveProfile()` method**

Add after the existing `getSidePanelType()` method (around line 217):

```js
getActiveProfile() {
    return this.addon.mouseGetActiveProfile(this.internalId);
}
```

- [ ] **Step 3: Modify `getButtonMapping` to accept profile parameter**

Change the existing method (lines 219–228) from:

```js
getButtonMapping(buttonId, layer = 0x00) {
    const raw = this.addon.mouseGetButtonMapping(this.internalId, 0x01, buttonId, layer);
```

To:

```js
getButtonMapping(buttonId, layer = 0x00, profile = null) {
    const p = profile !== null ? profile : this.activeProfile;
    const raw = this.addon.mouseGetButtonMapping(this.internalId, p, buttonId, layer);
```

The rest of the method stays the same.

- [ ] **Step 4: Modify `setButtonMapping` to accept profile parameter with slot 1 mirroring**

Change the existing method (lines 230–233) from:

```js
setButtonMapping(buttonId, layer, actionType, params) {
    this.addon.mouseSetButtonMapping(this.internalId, 0x01, buttonId, layer, actionType, params);
}
```

To:

```js
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

- [ ] **Step 5: Modify `getAllButtonMappings` to accept profile parameter**

Change the existing method (lines 242–248) to pass profile through:

```js
getAllButtonMappings(panelId, layer = 0x00, profile = null) {
    const buttons = this.getButtonsForPanel(panelId);
    return buttons.map(btn => {
        return { ...btn, mapping: this.getButtonMapping(btn.id, layer, profile) };
    });
}
```

- [ ] **Step 6: Modify `setDPI` to accept profile parameter with slot 1 mirroring**

Change the existing `setDPI` method (lines 162–165) from:

```js
setDPI(dpi) {
    this.dpi = dpi;
    this.addon.mouseSetDpi(this.internalId, dpi);
}
```

To:

```js
setDPI(dpi, profile = null) {
    const p = profile !== null ? profile : this.activeProfile;
    this.dpi = dpi;
    this.addon.mouseSetDpiProfile(this.internalId, p, dpi, dpi);
    // Slot 1 mirroring
    if (this.activeProfile !== 1 && p === this.activeProfile) {
        this.addon.mouseSetDpiProfile(this.internalId, 1, dpi, dpi);
    }
}
```

- [ ] **Step 7: Modify `getDPI` to accept profile parameter**

Change the existing `getDPI` method (line 159) from:

```js
getDPI() {
    return this.dpi;
}
```

To:

```js
getDPI(profile = null) {
    const p = profile !== null ? profile : this.activeProfile;
    const result = this.addon.mouseGetDpiProfile(this.internalId, p);
    return result.x;
}
```

- [ ] **Step 8: Fix `resetToState` to target slot 1 explicitly**

In the `resetToState` method (around line 92), find the line that calls `this.setDPI(state.dpi)` inside the `if(this.hasFeature(FeatureIdentifier.MOUSE_DPI))` guard. Change only the `setDPI` call, preserving the feature guard:

```js
if(this.hasFeature(FeatureIdentifier.MOUSE_DPI)) {
    this.setDPI(state.dpi, 1);
}
```

The `1` parameter explicitly targets slot 1, bypassing mirroring. The `hasFeature` guard must be preserved.

- [ ] **Step 9: Rebuild and run dev to verify no regressions**

Run: `yarn rebuild && NODE_OPTIONS=--openssl-legacy-provider yarn dev`

Expected: app starts, tray icon appears, button mapping section loads for profile 1 as before. Existing behavior unchanged — profile defaults to `this.activeProfile` which is read from device on init.

- [ ] **Step 10: Commit**

```bash
git add src/main/device/razerdevicemouse.js
git commit -m "feat: un-hardcode profile byte in mouse device, add activeProfile state and slot 1 mirroring"
```

---

### Task 5: Device Layer — New Profile Operations

**Files:**
- Modify: `src/main/device/razerdevicemouse.js`

- [ ] **Step 1: Add `setActiveProfile` method**

Add after `getActiveProfile()`:

```js
setActiveProfile(slot) {
    this.addon.mouseSetActiveProfile(this.internalId, slot);
    this.addon.mouseMacroClear(this.internalId);
    this.activeProfile = slot;
}
```

- [ ] **Step 2: Add `switchProfile` method**

```js
switchProfile(slot) {
    if (!this.panelType) return;
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
    this.addon.mouseSetDpiProfile(this.internalId, 1, dpiResult.x, dpiResult.y);
    this.dpi = dpiResult.x;
    // Update local tracking (no SET_PROFILE sent — see spec note)
    this.activeProfile = slot;
}
```

- [ ] **Step 3: Add `saveToSlot` method**

```js
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

- [ ] **Step 4: Add `clearSlot` method**

```js
clearSlot(slot) {
    if (slot === 1) return; // Slot 1 cannot be cleared
    // Send SET_PROFILE + MACRO_CLEAR as observed in capture
    this.addon.mouseSetActiveProfile(this.internalId, slot);
    this.addon.mouseMacroClear(this.internalId);
    this.slotOccupied[slot] = false;
    if (slot === this.activeProfile) {
        this.activeProfile = 1;
    }
}
```

- [ ] **Step 5: Add `probeSlotOccupancy` method**

```js
probeSlotOccupancy() {
    if (!this.panelType) return;
    const buttons = this.getButtonsForPanel(this.panelType);
    if (buttons.length === 0) return;
    const testButtonId = buttons[0].id;
    for (let slot = 2; slot <= 5; slot++) {
        try {
            const raw = this.addon.mouseGetButtonMapping(this.internalId, slot, testButtonId, 0x00);
            // Check indices 3-9 (actionType + params). Indices 0-2 (profile, buttonId, layer)
            // always echo back the request args and will be non-zero, so they can't be used
            // to determine occupancy. This heuristic may need adjustment after empirical testing.
            const hasData = raw.some((byte, i) => i >= 3 && byte !== 0);
            this.slotOccupied[slot] = hasData;
        } catch (e) {
            this.slotOccupied[slot] = false;
        }
    }
}
```

- [ ] **Step 6: Verify compilation and basic function**

Run: `yarn rebuild && NODE_OPTIONS=--openssl-legacy-provider yarn dev`

Expected: app starts, no errors. New methods exist but are not yet called from IPC.

- [ ] **Step 7: Commit**

```bash
git add src/main/device/razerdevicemouse.js
git commit -m "feat: add switchProfile, saveToSlot, clearSlot, and probeSlotOccupancy methods"
```

---

### Task 6: IPC Handlers — Wire Up Profile Operations

**Files:**
- Modify: `src/main/application.js`

- [ ] **Step 1: Modify `get-button-mappings` handler to pass profile**

Change the existing handler (around line 177) from:

```js
ipcMain.on('get-button-mappings', (event, arg) => {
    const { device, panelId, layer } = arg;
    const currentDevice = this.razerApplication.deviceManager.getByInternalId(device.internalId);
    if (!currentDevice) return;
    const mappings = currentDevice.getAllButtonMappings(panelId, layer);
    event.reply('button-mappings-response', { mappings });
});
```

To:

```js
ipcMain.on('get-button-mappings', (event, arg) => {
    const { device, panelId, layer, profile } = arg;
    const currentDevice = this.razerApplication.deviceManager.getByInternalId(device.internalId);
    if (!currentDevice) return;
    const mappings = currentDevice.getAllButtonMappings(panelId, layer, profile || null);
    event.reply('button-mappings-response', { mappings });
});
```

- [ ] **Step 2: Modify `set-button-mapping` handler to pass profile**

Change the existing handler (around line 185). The hypershift dual-layer write stays, but profile is passed through. Slot 1 mirroring is handled by the device method, NOT here.

```js
ipcMain.on('set-button-mapping', (event, arg) => {
    const { device, buttonId, layer, actionType, params, profile } = arg;
    const currentDevice = this.razerApplication.deviceManager.getByInternalId(device.internalId);
    if (!currentDevice) return;

    if (actionType === 0x0c) {
        currentDevice.setButtonMapping(buttonId, 0x00, actionType, params, profile || null);
        currentDevice.setButtonMapping(buttonId, 0x01, actionType, params, profile || null);
    } else {
        currentDevice.setButtonMapping(buttonId, layer, actionType, params, profile || null);
    }

    event.reply('button-mapping-updated', { buttonId, layer, actionType, params });
});
```

- [ ] **Step 3: Add `get-active-profile` handler**

Add after the existing button mapping handlers:

```js
ipcMain.on('get-active-profile', (event, arg) => {
    const { device } = arg;
    const currentDevice = this.razerApplication.deviceManager.getByInternalId(device.internalId);
    if (!currentDevice) return;
    event.reply('active-profile-response', {
        profile: currentDevice.activeProfile,
        slotOccupied: currentDevice.slotOccupied,
    });
});
```

- [ ] **Step 4: Add `switch-profile` handler**

```js
ipcMain.on('switch-profile', (event, arg) => {
    const { device, profile } = arg;
    const currentDevice = this.razerApplication.deviceManager.getByInternalId(device.internalId);
    if (!currentDevice) return;
    try {
        currentDevice.switchProfile(profile);
        event.reply('profile-switched', { profile });
    } catch (e) {
        event.reply('profile-switched', { profile, error: e.message });
    }
});
```

- [ ] **Step 5: Add `save-to-slot` handler**

```js
ipcMain.on('save-to-slot', (event, arg) => {
    const { device, targetSlot } = arg;
    const currentDevice = this.razerApplication.deviceManager.getByInternalId(device.internalId);
    if (!currentDevice) return;
    try {
        currentDevice.saveToSlot(targetSlot);
        event.reply('slot-saved', { targetSlot, slotOccupied: currentDevice.slotOccupied });
    } catch (e) {
        event.reply('slot-saved', { targetSlot, error: e.message });
    }
});
```

- [ ] **Step 6: Add `clear-slot` handler**

```js
ipcMain.on('clear-slot', (event, arg) => {
    const { device, slot } = arg;
    const currentDevice = this.razerApplication.deviceManager.getByInternalId(device.internalId);
    if (!currentDevice) return;
    try {
        currentDevice.clearSlot(slot);
        event.reply('slot-cleared', {
            slot,
            slotOccupied: currentDevice.slotOccupied,
            activeProfile: currentDevice.activeProfile,
        });
    } catch (e) {
        event.reply('slot-cleared', { slot, error: e.message });
    }
});
```

- [ ] **Step 7: Add `get-all-profile-mappings` handler**

```js
ipcMain.on('get-all-profile-mappings', (event, arg) => {
    const { device, panelId, layer } = arg;
    const currentDevice = this.razerApplication.deviceManager.getByInternalId(device.internalId);
    if (!currentDevice) return;
    const profiles = {};
    for (let slot = 1; slot <= 5; slot++) {
        try {
            profiles[slot] = currentDevice.getAllButtonMappings(panelId, layer, slot);
        } catch (e) {
            profiles[slot] = [];
        }
    }
    event.reply('all-profile-mappings-response', { profiles });
});
```

- [ ] **Step 8: Verify no regressions**

Run: `NODE_OPTIONS=--openssl-legacy-provider yarn dev`

Expected: app starts, button mapping section works as before. New IPC channels exist but are not yet called from the renderer.

- [ ] **Step 9: Commit**

```bash
git add src/main/application.js
git commit -m "feat: add IPC handlers for profile switching, save-to-slot, and clear-slot"
```

---

### Task 7: Renderer — Profile Slot Selector UI

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`
- Modify: `src/renderer/index.css`

This is the largest task. The profile selector appears as a row of 5 SD card icons with colored dots above the layer toggle.

- [ ] **Step 1: Add profile state to constructor**

In the constructor (around line 158), add to the state object:

```js
activeProfile: 1,
slotOccupied: { 1: true, 2: false, 3: false, 4: false, 5: false },
profileSwitching: false,
```

- [ ] **Step 2: Register new IPC listeners in `componentDidMount`**

After the existing listener registrations (around line 188), add:

```js
ipcRenderer.on('active-profile-response', (event, arg) => {
    this.setState({
        activeProfile: arg.profile,
        slotOccupied: arg.slotOccupied,
    });
});

ipcRenderer.on('profile-switched', (event, arg) => {
    if (!arg.error) {
        this.setState({ activeProfile: arg.profile, profileSwitching: false }, () => {
            this.requestMappings();
        });
    } else {
        this.setState({ profileSwitching: false });
    }
});

ipcRenderer.on('slot-saved', (event, arg) => {
    if (!arg.error) {
        this.setState({ slotOccupied: arg.slotOccupied, profileSwitching: false });
    } else {
        this.setState({ profileSwitching: false });
    }
});

ipcRenderer.on('slot-cleared', (event, arg) => {
    if (!arg.error) {
        // Capture before setState overwrites activeProfile
        const needsRefetch = (arg.slot === this.state.activeProfile);
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

- [ ] **Step 3: Clean up IPC listeners in `componentWillUnmount`**

The existing `componentWillUnmount` (around line 190) uses `removeListener` with named references for existing listeners. Append removals for the new channels only — do NOT replace the existing cleanup or use `removeAllListeners` (which would break existing named listener cleanup):

```js
// Append these inside the existing componentWillUnmount method, after the existing removeListener calls:
ipcRenderer.removeAllListeners('active-profile-response');
ipcRenderer.removeAllListeners('profile-switched');
ipcRenderer.removeAllListeners('slot-saved');
ipcRenderer.removeAllListeners('slot-cleared');
```

- [ ] **Step 4: Request active profile on mount**

In `componentDidMount`, after the `this.refreshPanelType()` call, add:

```js
ipcRenderer.send('get-active-profile', { device: this.deviceSelected });
```

- [ ] **Step 5: Add slot action handlers**

Add these methods to the class:

```js
handleSlotClick(slot) {
    if (this.state.profileSwitching) return;
    const { activeProfile, slotOccupied } = this.state;

    if (!slotOccupied[slot]) {
        // Empty slot — offer to save current profile here
        if (window.confirm('Save current profile to this slot?')) {
            this.setState({ profileSwitching: true });
            ipcRenderer.send('save-to-slot', { device: this.deviceSelected, targetSlot: slot });
        }
    } else if (slot !== activeProfile) {
        // Occupied, not active — switch to it
        this.setState({ profileSwitching: true });
        ipcRenderer.send('switch-profile', { device: this.deviceSelected, profile: slot });
    }
}

handleSlotClear(e, slot) {
    e.stopPropagation();
    if (this.state.profileSwitching) return;
    if (slot === 1) return;
    if (window.confirm('Clear this profile slot?')) {
        this.setState({ profileSwitching: true });
        ipcRenderer.send('clear-slot', { device: this.deviceSelected, slot });
    }
}
```

- [ ] **Step 6: Add `renderProfileSelector` method**

Add this render method to the class. The SD card icon is rendered as an SVG inline element with a colored dot.

```jsx
renderProfileSelector() {
    const { activeProfile, slotOccupied, profileSwitching } = this.state;
    const slotColors = {
        1: '#ffffff',
        2: '#ff4444',
        3: '#44cc44',
        4: '#4488ff',
        5: '#44dddd',
    };

    return (
        <div style={{ display: 'flex', padding: '0 10px 10px', gap: '6px', alignItems: 'center' }}>
            <span style={{ fontSize: '11px', color: '#aaa', marginRight: '4px' }}>Profiles</span>
            {[1, 2, 3, 4, 5].map(slot => {
                const isActive = slot === activeProfile;
                const isOccupied = slotOccupied[slot];
                const color = slotColors[slot];

                return (
                    <div
                        key={slot}
                        onClick={() => this.handleSlotClick(slot)}
                        style={{
                            position: 'relative',
                            width: '32px',
                            height: '36px',
                            cursor: profileSwitching ? 'wait' : 'pointer',
                            opacity: isOccupied ? 1 : 0.35,
                            transition: 'opacity 0.15s',
                        }}
                        className={`profile-slot ${isActive ? 'profile-slot-active' : ''}`}
                    >
                        <svg width="32" height="36" viewBox="0 0 32 36" fill="none">
                            <rect x="1" y="4" width="30" height="28" rx="3"
                                stroke={isActive ? color : '#888'} strokeWidth={isActive ? '2' : '1'}
                                fill={isActive ? 'rgba(255,255,255,0.08)' : 'transparent'} />
                            <rect x="6" y="1" width="20" height="6" rx="1"
                                fill={isActive ? color : '#888'} opacity={isActive ? '0.8' : '0.4'} />
                            <circle cx="16" cy="20" r="4"
                                fill={color} opacity={isOccupied ? '1' : '0.3'} />
                        </svg>
                        <span style={{
                            position: 'absolute', bottom: '2px', left: '0', right: '0',
                            textAlign: 'center', fontSize: '9px',
                            color: isActive ? color : '#888',
                        }}>{slot}</span>
                        {isOccupied && slot !== 1 && (
                            <div
                                className="profile-slot-clear"
                                onClick={(e) => this.handleSlotClear(e, slot)}
                                style={{
                                    position: 'absolute', top: '-4px', right: '-4px',
                                    width: '16px', height: '16px', borderRadius: '50%',
                                    background: '#444', color: '#ccc', fontSize: '10px',
                                    lineHeight: '16px', textAlign: 'center',
                                    display: 'none', cursor: 'pointer',
                                }}
                            >&times;</div>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
```

- [ ] **Step 7: Insert profile selector into the render tree**

In the `renderSettings()` method (around line 679), insert `{this.renderProfileSelector()}` BEFORE the layer toggle row (the `<div>` with Normal/Hypershift buttons):

Find the layer toggle div and insert just above it:

```jsx
{this.renderProfileSelector()}
```

- [ ] **Step 8: Add CSS for profile slot hover effects**

In `src/renderer/index.css`, append:

```css
.profile-slot:hover .profile-slot-clear {
    display: block !important;
}
.profile-slot-clear:hover {
    background: #ff4444 !important;
    color: #fff !important;
}
```

- [ ] **Step 9: Rebuild and test**

Run: `NODE_OPTIONS=--openssl-legacy-provider yarn dev`

Expected: Profile selector appears above the Normal/Hypershift toggle with 5 SD card icons. Slot 1 should be highlighted as active. Slots 2–5 should appear dimmed.

- [ ] **Step 10: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx src/renderer/index.css
git commit -m "feat: add profile slot selector UI with SD card icons and save/switch/clear interactions"
```

---

### Task 8: Integration Testing and Empirical Verification

**Files:** None (testing only)

This task uses the actual Razer Naga V2 Pro mouse to verify the implementation.

- [ ] **Step 1: Verify reading active profile**

With mouse connected, open the button mapping settings.
Expected: Profile selector shows slot 1 active. Console should show no errors.

- [ ] **Step 2: Test save to slot**

Click an empty slot (e.g. slot 2).
Expected: Confirmation dialog appears. After confirming, slot 2 becomes occupied (full opacity with colored dot).

- [ ] **Step 3: Test profile switching**

Click occupied slot 2.
Expected: Slot 2 becomes highlighted as active. Button mappings re-load and should show the same mappings as slot 1 (since we just copied them).

- [ ] **Step 4: Test editing on non-default profile**

While on slot 2, edit a button mapping (e.g. change button 1 to a different key).
Expected: The edit is applied. Because of slot 1 mirroring, the physical button should immediately respond with the new mapping.

- [ ] **Step 5: Test switching back to slot 1**

Click slot 1.
Expected: Slot 1 becomes active. Button mappings should show the edit from step 4 (since it was mirrored to slot 1).

- [ ] **Step 6: Test clearing a slot**

Hover over slot 2, click the "x" button.
Expected: Confirmation dialog. After confirming, slot 2 becomes empty (dimmed). If slot 2 was active, UI switches to slot 1.

- [ ] **Step 7: Verify SET_PROFILE behavior**

If during step 3, the physical button mappings did NOT change after switching (buttons still use old profile's bindings), then `switchProfile` needs to also call `setActiveProfile`. Add this as step 4 in the `switchProfile` method:

```js
this.setActiveProfile(slot);
```

- [ ] **Step 8: Verify DPI per-profile read command**

If step 3 fails with a USB error during DPI read (the `0x04:0x86` command), change `razer_mouse_attr_read_dpi_profile` to use `0x04:0x85` instead:

```c
struct razer_report report = get_razer_report(0x04, 0x85, 0x07);
```

Rebuild with `yarn rebuild` and re-test.

- [ ] **Step 9: Verify slot occupancy probing**

Restart the app. If a slot that was saved via Synapse shows as empty, the probing heuristic needs adjustment. Check what `mouseGetButtonMapping` returns for an occupied slot — the `hasData` check in `probeSlotOccupancy` may need to be adjusted based on what the device actually returns for empty vs occupied slots.

- [ ] **Step 10: Build packaged app and verify**

```bash
yarn rebuild && NODE_OPTIONS=--openssl-legacy-provider yarn compile && npx electron-builder --dir -c.compression=store -c.mac.identity=null -c.nodeGypRebuild=false
```

Copy to Applications and verify profile switching works in the packaged app.
