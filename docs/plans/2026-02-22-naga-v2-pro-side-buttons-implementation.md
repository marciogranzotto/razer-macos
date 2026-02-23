# Naga V2 Pro Side Button Configuration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add side button remapping support for the Razer Naga V2 Pro to razer-macos, using the USB protocol decoded in Phase 1.

**Architecture:** Three-layer stack: C driver functions construct 90-byte Razer USB Feature Reports and send via IOKit, N-API bridge wraps them for Node.js, Electron app provides UI. Button mappings are stored in device firmware and take effect immediately.

**Tech Stack:** C (IOKit/USB), C++ (node-addon-api/N-API), JavaScript (Node.js/Electron/React 16)

**Protocol Spec:** `docs/specs/naga-v2-pro-button-mapping-protocol.md`

---

## Scope

**In scope (this plan):**
- Button mapping read/write for all 3 panels (2/6/12 buttons)
- Normal + Hypershift layer support
- Keyboard key, mouse button, multimedia key, disabled action types
- Panel detection
- Feature system integration + device config
- IPC handlers in main process
- Renderer UI for button configuration

**Deferred:**
- Macro support (requires macro upload protocol — cmd_class 0x06)
- Sensitivity clutch (needs more RE on flags byte)
- Scroll wheel actions (needs more RE on variants)
- Profile management (needs RE on 0x0f:0x02/0x0f:0x04)
- State save/restore on power events (can add after core works)

---

## Task 1: C Driver — Button Mapping Functions

**Files:**
- Modify: `librazermacos/src/lib/razermouse_driver.c`
- Modify: `librazermacos/src/include/razermouse_driver.h`

**Context:** Each driver function constructs a `struct razer_report` using `razer_new_report()`, sets `cmd_class`, `cmd_id`, and `data_size`, fills the `arguments` array, then calls `razer_send_payload()`. Existing examples: `razer_attr_write_dpi()`, `razer_attr_read_dpi()`.

The button mapping protocol uses:
- cmd_class=0x02, cmd_id=0x0c (write), cmd_id=0x8c (read)
- data_size=10
- arguments: [profile, button_id, layer, action_type, param1..param6]

**Step 1: Read existing driver code for reference patterns**

Read `razermouse_driver.c` and `razerchromacommon.c` to find the exact pattern for `razer_new_report()`, `razer_send_payload()`, and how `arguments[]` is populated. Also check the `razer_report` struct definition in headers.

**Step 2: Add button mapping write function**

In `razermouse_driver.c`:

```c
/**
 * Write button mapping to device.
 * profile: profile slot (0x01)
 * button_id: button ID (e.g. 0x40-0x4b for 12-btn panel)
 * layer: 0x00=normal, 0x01=hypershift
 * action_type: 0x00=disabled, 0x01=mouse, 0x02=keyboard, 0x0a=multimedia, 0x0c=hypershift
 * action_params: 6-byte array of action-specific parameters
 */
int razer_mouse_attr_write_button_mapping(
    struct usb_device *usb_dev,
    unsigned char profile,
    unsigned char button_id,
    unsigned char layer,
    unsigned char action_type,
    const unsigned char *action_params)
{
    struct razer_report report = razer_new_report(0x02, 0x0c, 0x0a);
    report.arguments[0] = profile;
    report.arguments[1] = button_id;
    report.arguments[2] = layer;
    report.arguments[3] = action_type;
    memcpy(&report.arguments[4], action_params, 6);
    return razer_send_payload(usb_dev, &report);
}
```

**Step 3: Add button mapping read function**

```c
/**
 * Read button mapping from device.
 * Returns the 10-byte payload in response_buf.
 */
int razer_mouse_attr_read_button_mapping(
    struct usb_device *usb_dev,
    unsigned char profile,
    unsigned char button_id,
    unsigned char layer,
    unsigned char *response_buf)
{
    struct razer_report report = razer_new_report(0x02, 0x8c, 0x0a);
    report.arguments[0] = profile;
    report.arguments[1] = button_id;
    report.arguments[2] = layer;
    struct razer_report response = razer_send_payload_and_wait(usb_dev, &report);
    memcpy(response_buf, response.arguments, 10);
    return 0;
}
```

**Step 4: Add panel detection function**

Panel ID can be read via the FW version command `0x00:0xb9` — response byte[0] contains the panel ID (0x00=none, 0x01=2-btn, 0x03=12-btn, 0x04=6-btn).

```c
/**
 * Read side panel type.
 * Returns: 0=none, 1=2-btn, 3=12-btn, 4=6-btn
 */
unsigned char razer_mouse_attr_read_side_panel_type(struct usb_device *usb_dev)
{
    struct razer_report report = razer_new_report(0x00, 0xb9, 0x01);
    struct razer_report response = razer_send_payload_and_wait(usb_dev, &report);
    return response.arguments[0];
}
```

**Step 5: Add function declarations to header**

In `razermouse_driver.h`, add declarations for all three functions.

**Step 6: Build and verify compilation**

Run: `yarn rebuild`
Expected: Clean compilation with no errors.

**Step 7: Commit**

```bash
git add librazermacos/
git commit -m "feat: add button mapping driver functions for Naga V2 Pro"
```

---

## Task 2: N-API Bridge — Expose Driver Functions to Node.js

**Files:**
- Modify: `src/driver/addon.cc`

**Context:** Each N-API function gets the device via `getRazerDeviceFor(info)` using `info[0]` as `internalDeviceId`, then calls the C driver function. Return values are wrapped as `Napi::Number` or `Napi::Array`. See existing `MouseSetDpi`, `MouseGetDpi` for the pattern.

**Step 1: Read addon.cc to confirm patterns**

Read the existing `MouseSetDpi` and `MouseGetDpi` implementations and the export table at the bottom.

**Step 2: Add MouseSetButtonMapping**

```cpp
void MouseSetButtonMapping(const Napi::CallbackInfo &info) {
    RazerDevice device = getRazerDeviceFor(info);
    unsigned char profile = info[1].ToNumber().Uint32Value();
    unsigned char button_id = info[2].ToNumber().Uint32Value();
    unsigned char layer = info[3].ToNumber().Uint32Value();
    unsigned char action_type = info[4].ToNumber().Uint32Value();
    Napi::Array params = info[5].As<Napi::Array>();
    unsigned char action_params[6] = {0};
    for (uint32_t i = 0; i < 6 && i < params.Length(); i++) {
        action_params[i] = params.Get(i).ToNumber().Uint32Value();
    }
    razer_mouse_attr_write_button_mapping(
        device.usbDevice, profile, button_id, layer, action_type, action_params);
}
```

**Step 3: Add MouseGetButtonMapping**

```cpp
Napi::Value MouseGetButtonMapping(const Napi::CallbackInfo &info) {
    Napi::Env env = info.Env();
    RazerDevice device = getRazerDeviceFor(info);
    unsigned char profile = info[1].ToNumber().Uint32Value();
    unsigned char button_id = info[2].ToNumber().Uint32Value();
    unsigned char layer = info[3].ToNumber().Uint32Value();
    unsigned char response[10] = {0};
    razer_mouse_attr_read_button_mapping(
        device.usbDevice, profile, button_id, layer, response);
    Napi::Array result = Napi::Array::New(env, 10);
    for (int i = 0; i < 10; i++) {
        result.Set(i, Napi::Number::New(env, response[i]));
    }
    return result;
}
```

**Step 4: Add MouseGetSidePanelType**

```cpp
Napi::Value MouseGetSidePanelType(const Napi::CallbackInfo &info) {
    Napi::Env env = info.Env();
    RazerDevice device = getRazerDeviceFor(info);
    unsigned char panel = razer_mouse_attr_read_side_panel_type(device.usbDevice);
    return Napi::Number::New(env, panel);
}
```

**Step 5: Register exports**

Add to the exports block (around line 985):
```cpp
exports.Set("mouseSetButtonMapping", Napi::Function::New(env, MouseSetButtonMapping));
exports.Set("mouseGetButtonMapping", Napi::Function::New(env, MouseGetButtonMapping));
exports.Set("mouseGetSidePanelType", Napi::Function::New(env, MouseGetSidePanelType));
```

**Step 6: Build and verify**

Run: `yarn rebuild`
Expected: Clean compilation.

**Step 7: Commit**

```bash
git add src/driver/addon.cc
git commit -m "feat: expose button mapping functions via N-API bridge"
```

---

## Task 3: Feature System — Button Mapping Feature

**Files:**
- Modify: `src/main/feature/featureidentifier.js`
- Create: `src/main/feature/featurebuttonmapping.js`
- Modify: `src/main/feature/featurehelper.js`

**Step 1: Add feature identifier**

In `featureidentifier.js`, add after the existing identifiers:

```javascript
FeatureIdentifier.BUTTON_MAPPING = 'buttonMapping';
```

**Step 2: Create FeatureButtonMapping class**

Create `src/main/feature/featurebuttonmapping.js`:

```javascript
const Feature = require('./feature');
const FeatureIdentifier = require('./featureidentifier');

class FeatureButtonMapping extends Feature {
  constructor(config) {
    super(FeatureIdentifier.BUTTON_MAPPING, config);
  }

  getDefaultConfiguration() {
    return {
      panels: {
        0x01: { // 2-button
          buttons: [
            { id: 0x05, label: 'Button 1', defaultAction: { type: 0x01, params: [0x01, 0x05, 0, 0, 0, 0] } },
            { id: 0x04, label: 'Button 2', defaultAction: { type: 0x01, params: [0x01, 0x04, 0, 0, 0, 0] } },
          ],
        },
        0x04: { // 6-button
          buttons: [
            { id: 0x50, label: 'Button 1', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x1e, 0, 0, 0] } },
            { id: 0x51, label: 'Button 2', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x1f, 0, 0, 0] } },
            { id: 0x52, label: 'Button 3', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x20, 0, 0, 0] } },
            { id: 0x53, label: 'Button 4', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x21, 0, 0, 0] } },
            { id: 0x54, label: 'Button 5', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x22, 0, 0, 0] } },
            { id: 0x55, label: 'Button 6', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x23, 0, 0, 0] } },
          ],
        },
        0x03: { // 12-button
          buttons: [
            { id: 0x40, label: 'Button 1',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x1e, 0, 0, 0] } },
            { id: 0x41, label: 'Button 2',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x1f, 0, 0, 0] } },
            { id: 0x42, label: 'Button 3',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x20, 0, 0, 0] } },
            { id: 0x43, label: 'Button 4',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x21, 0, 0, 0] } },
            { id: 0x44, label: 'Button 5',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x22, 0, 0, 0] } },
            { id: 0x45, label: 'Button 6',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x23, 0, 0, 0] } },
            { id: 0x46, label: 'Button 7',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x24, 0, 0, 0] } },
            { id: 0x47, label: 'Button 8',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x25, 0, 0, 0] } },
            { id: 0x48, label: 'Button 9',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x26, 0, 0, 0] } },
            { id: 0x49, label: 'Button 10', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x27, 0, 0, 0] } },
            { id: 0x4a, label: 'Button 11', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x2d, 0, 0, 0] } },
            { id: 0x4b, label: 'Button 12', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x2e, 0, 0, 0] } },
          ],
        },
      },
    };
  }
}

module.exports = FeatureButtonMapping;
```

**Step 3: Register in FeatureHelper**

In `featurehelper.js`:
- Import `FeatureButtonMapping` at the top
- Add `case 'buttonMapping':` in `createFeatureFrom()` returning `new FeatureButtonMapping(config)`
- Do NOT add to default mouse features (it's Naga-specific, enabled via device JSON config)

**Step 4: Commit**

```bash
git add src/main/feature/
git commit -m "feat: add buttonMapping feature for Naga V2 Pro"
```

---

## Task 4: Device Config — Enable Feature for Naga V2 Pro

**Files:**
- Modify: `src/devices/naga_v2_pro_wired.json`
- Modify: `src/devices/naga_v2_pro_wireless.json`

**Step 1: Add buttonMapping to featuresConfig**

Add to the `featuresConfig` array in both files:

```json
{
  "buttonMapping": {}
}
```

An empty config object will use the default configuration from `FeatureButtonMapping.getDefaultConfiguration()`.

**Step 2: Commit**

```bash
git add src/devices/naga_v2_pro_wired.json src/devices/naga_v2_pro_wireless.json
git commit -m "feat: enable buttonMapping feature for Naga V2 Pro"
```

---

## Task 5: Device Model — Button Mapping Methods on RazerDeviceMouse

**Files:**
- Modify: `src/main/device/razerdevicemouse.js`

**Context:** `RazerDeviceMouse` extends `RazerDevice`. It calls addon functions via `this.addon.xxx(this.internalId, ...)`. The `init()` method reads device state on startup.

**Step 1: Add button mapping methods**

```javascript
getSidePanelType() {
  return this.addon.mouseGetSidePanelType(this.internalId);
}

getButtonMapping(buttonId, layer = 0x00) {
  const raw = this.addon.mouseGetButtonMapping(this.internalId, 0x01, buttonId, layer);
  return {
    profile: raw[0],
    buttonId: raw[1],
    layer: raw[2],
    actionType: raw[3],
    params: [raw[4], raw[5], raw[6], raw[7], raw[8], raw[9]],
  };
}

setButtonMapping(buttonId, layer, actionType, params) {
  this.addon.mouseSetButtonMapping(
    this.internalId, 0x01, buttonId, layer, actionType, params);
}

getButtonsForPanel(panelId) {
  const feature = this.getFeature(FeatureIdentifier.BUTTON_MAPPING);
  if (!feature) return [];
  const panelConfig = feature.configuration.panels[panelId];
  return panelConfig ? panelConfig.buttons : [];
}

getAllButtonMappings(panelId, layer = 0x00) {
  const buttons = this.getButtonsForPanel(panelId);
  return buttons.map(btn => ({
    ...btn,
    mapping: this.getButtonMapping(btn.id, layer),
  }));
}
```

**Step 2: Add panel detection to init()**

In the `init()` method, after existing feature reads, add:

```javascript
if (this.hasFeature(FeatureIdentifier.BUTTON_MAPPING)) {
  this.panelType = this.getSidePanelType();
}
```

Import `FeatureIdentifier` at the top if not already imported.

**Step 3: Include panel type in serialization**

The device is serialized and sent to the renderer. Ensure `panelType` is included. Check how the existing `serialize()` or equivalent method works — it may already include all own properties, or may need explicit addition.

**Step 4: Commit**

```bash
git add src/main/device/razerdevicemouse.js
git commit -m "feat: add button mapping methods to RazerDeviceMouse"
```

---

## Task 6: IPC Handlers — Main Process Button Mapping API

**Files:**
- Modify: `src/main/application.js`

**Context:** IPC handlers follow the pattern: receive event with `{ device, ... }`, look up real device via `deviceManager.getByInternalId(device.internalId)`, call device method, optionally reply or refresh tray.

**Step 1: Add get-side-panel-type handler**

```javascript
ipcMain.on('get-side-panel-type', (event, arg) => {
  const { device } = arg;
  const currentDevice = this.razerApplication.deviceManager.getByInternalId(device.internalId);
  const panelType = currentDevice.getSidePanelType();
  event.reply('side-panel-type-response', { panelType });
});
```

**Step 2: Add get-button-mappings handler**

```javascript
ipcMain.on('get-button-mappings', (event, arg) => {
  const { device, panelId, layer } = arg;
  const currentDevice = this.razerApplication.deviceManager.getByInternalId(device.internalId);
  const mappings = currentDevice.getAllButtonMappings(panelId, layer);
  event.reply('button-mappings-response', { mappings });
});
```

**Step 3: Add set-button-mapping handler**

```javascript
ipcMain.on('set-button-mapping', (event, arg) => {
  const { device, buttonId, layer, actionType, params } = arg;
  const currentDevice = this.razerApplication.deviceManager.getByInternalId(device.internalId);
  currentDevice.setButtonMapping(buttonId, layer, actionType, params);
  event.reply('button-mapping-updated', { buttonId, layer, actionType, params });
});
```

**Step 4: Commit**

```bash
git add src/main/application.js
git commit -m "feat: add IPC handlers for button mapping"
```

---

## Task 7: Renderer UI — Button Mapping Section

**Files:**
- Create: `src/renderer/sections/sectionsettingbuttonmapping.jsx`
- Modify: `src/renderer/views/viewdevicesettings.jsx`

**Context:** Settings sections extend `SectionSettingBlock` (renders title + body). They communicate with main process via `ipcRenderer.send()` and `ipcRenderer.on()`. See `SectionSettingSensitivity` and `SectionSettingPollRate` for patterns.

**Step 1: Create SectionSettingButtonMapping**

```jsx
const React = require('react');
const { ipcRenderer } = require('electron');
const SectionSettingBlock = require('./sectionsettingblock');
const FeatureIdentifier = require('../../main/feature/featureidentifier');

const ACTION_TYPE_LABELS = {
  0x00: 'Disabled',
  0x01: 'Mouse Button',
  0x02: 'Keyboard Key',
  0x0a: 'Multimedia',
  0x0c: 'Hypershift',
};

const MOUSE_BUTTON_LABELS = {
  0x01: 'Left Click', 0x02: 'Right Click', 0x03: 'Middle Click',
  0x04: 'Back', 0x05: 'Forward',
};

const KEY_LABELS = {
  0x04: 'A', 0x05: 'B', 0x06: 'C', 0x07: 'D', 0x08: 'E', 0x09: 'F',
  0x0a: 'G', 0x0b: 'H', 0x0c: 'I', 0x0d: 'J', 0x0e: 'K', 0x0f: 'L',
  0x10: 'M', 0x11: 'N', 0x12: 'O', 0x13: 'P', 0x14: 'Q', 0x15: 'R',
  0x16: 'S', 0x17: 'T', 0x18: 'U', 0x19: 'V', 0x1a: 'W', 0x1b: 'X',
  0x1c: 'Y', 0x1d: 'Z',
  0x1e: '1', 0x1f: '2', 0x20: '3', 0x21: '4', 0x22: '5',
  0x23: '6', 0x24: '7', 0x25: '8', 0x26: '9', 0x27: '0',
  0x2d: '-', 0x2e: '=',
  0x3a: 'F1', 0x3b: 'F2', 0x3c: 'F3', 0x3d: 'F4',
  0x3e: 'F5', 0x3f: 'F6', 0x40: 'F7', 0x41: 'F8',
  0x42: 'F9', 0x43: 'F10', 0x44: 'F11', 0x45: 'F12',
};

const MEDIA_LABELS = {
  0x00b5: 'Next Track', 0x00b6: 'Previous Track', 0x00cd: 'Play/Pause',
  0x00e2: 'Mute', 0x00e9: 'Volume Up', 0x00ea: 'Volume Down',
};

function describeMapping(mapping) {
  if (!mapping) return 'Unknown';
  const { actionType, params } = mapping;
  switch (actionType) {
    case 0x00: return 'Disabled';
    case 0x01: return MOUSE_BUTTON_LABELS[params[1]] || `Mouse Btn ${params[1]}`;
    case 0x02: return KEY_LABELS[params[2]] || `Key 0x${params[2].toString(16)}`;
    case 0x0a: {
      const code = (params[1] << 8) | params[2];
      return MEDIA_LABELS[code] || `Media 0x${code.toString(16)}`;
    }
    case 0x0c: return 'Hypershift';
    default: return `Type 0x${actionType.toString(16)}`;
  }
}

class SectionSettingButtonMapping extends SectionSettingBlock {
  constructor(props) {
    super(props);
    this.feature = this.deviceSelected.features.find(
      f => f.featureIdentifier === FeatureIdentifier.BUTTON_MAPPING
    );
    this.state = {
      panelType: this.deviceSelected.panelType || 0,
      mappings: [],
      layer: 0x00,
      editingButton: null,
    };
  }

  componentDidMount() {
    ipcRenderer.on('button-mappings-response', (_, data) => {
      this.setState({ mappings: data.mappings });
    });
    ipcRenderer.on('button-mapping-updated', () => {
      this.requestMappings();
    });
    this.requestMappings();
  }

  componentWillUnmount() {
    ipcRenderer.removeAllListeners('button-mappings-response');
    ipcRenderer.removeAllListeners('button-mapping-updated');
  }

  requestMappings() {
    ipcRenderer.send('get-button-mappings', {
      device: this.deviceSelected,
      panelId: this.state.panelType,
      layer: this.state.layer,
    });
  }

  switchLayer(layer) {
    this.setState({ layer }, () => this.requestMappings());
  }

  setDisabled(buttonId) {
    ipcRenderer.send('set-button-mapping', {
      device: this.deviceSelected,
      buttonId,
      layer: this.state.layer,
      actionType: 0x00,
      params: [0, 0, 0, 0, 0, 0],
    });
  }

  restoreDefault(buttonId) {
    const panelConfig = this.feature.configuration.panels[this.state.panelType];
    if (!panelConfig) return;
    const btnConfig = panelConfig.buttons.find(b => b.id === buttonId);
    if (!btnConfig) return;
    const def = btnConfig.defaultAction;
    ipcRenderer.send('set-button-mapping', {
      device: this.deviceSelected,
      buttonId,
      layer: this.state.layer,
      actionType: def.type,
      params: def.params,
    });
  }

  renderTitle() { return 'Side Buttons'; }

  renderSettings() {
    if (!this.feature) return null;
    if (this.state.panelType === 0) {
      return <div className='no-panel'>No side panel detected</div>;
    }

    const PANEL_NAMES = { 0x01: '2-Button', 0x03: '12-Button', 0x04: '6-Button' };

    return (
      <div className='button-mapping'>
        <div className='panel-info'>
          Panel: {PANEL_NAMES[this.state.panelType] || 'Unknown'}
        </div>
        <div className='layer-toggle'>
          <button
            className={this.state.layer === 0x00 ? 'active' : ''}
            onClick={() => this.switchLayer(0x00)}>Normal</button>
          <button
            className={this.state.layer === 0x01 ? 'active' : ''}
            onClick={() => this.switchLayer(0x01)}>Hypershift</button>
        </div>
        <div className='button-list'>
          {this.state.mappings.map(btn => (
            <div key={btn.id} className='button-row'>
              <span className='button-label'>{btn.label}</span>
              <span className='button-binding'>{describeMapping(btn.mapping)}</span>
              <button onClick={() => this.restoreDefault(btn.id)}>Default</button>
              <button onClick={() => this.setDisabled(btn.id)}>Disable</button>
            </div>
          ))}
        </div>
      </div>
    );
  }
}

module.exports = SectionSettingButtonMapping;
```

**Step 2: Add to ViewDeviceSettings**

In `viewdevicesettings.jsx`, import and add the new section:

```jsx
const SectionSettingButtonMapping = require('../sections/sectionsettingbuttonmapping');
```

Add in the render method alongside the other sections:

```jsx
<SectionSettingButtonMapping deviceSelected={this.deviceSelected} />
```

**Step 3: Commit**

```bash
git add src/renderer/
git commit -m "feat: add button mapping UI section"
```

---

## Task 8: Integration Test — Manual Verification

**This task requires a Mac with the Razer Naga V2 Pro connected.**

**Step 1: Build the native addon**

Run: `yarn rebuild`
Expected: Clean compilation.

**Step 2: Start dev server**

Run: `yarn dev`
Expected: Electron app starts with tray icon.

**Step 3: Verify panel detection**

Open device settings for the Naga V2 Pro. The Side Buttons section should show the detected panel type (2/6/12-button).

**Step 4: Verify button mapping read**

The button list should show current bindings read from the device.

**Step 5: Verify button mapping write**

Click "Disable" on a button, then verify on the device that the button no longer does anything. Click "Default" to restore it.

**Step 6: Verify Hypershift layer**

Switch to Hypershift layer tab and verify bindings can be read/written independently.

**Step 7: Commit any fixes**

```bash
git commit -m "fix: integration test fixes for button mapping"
```

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `librazermacos/src/lib/razermouse_driver.c` | Modify | Add 3 functions: write/read button mapping, read panel type |
| `librazermacos/src/include/razermouse_driver.h` | Modify | Add function declarations |
| `src/driver/addon.cc` | Modify | Add 3 N-API wrappers + 3 exports |
| `src/main/feature/featureidentifier.js` | Modify | Add `BUTTON_MAPPING` constant |
| `src/main/feature/featurebuttonmapping.js` | Create | Feature class with panel configs and default bindings |
| `src/main/feature/featurehelper.js` | Modify | Register `buttonMapping` in `createFeatureFrom()` |
| `src/devices/naga_v2_pro_wired.json` | Modify | Add `buttonMapping` to `featuresConfig` |
| `src/devices/naga_v2_pro_wireless.json` | Modify | Add `buttonMapping` to `featuresConfig` |
| `src/main/device/razerdevicemouse.js` | Modify | Add button mapping methods + panel detection in init |
| `src/main/application.js` | Modify | Add 3 IPC handlers |
| `src/renderer/sections/sectionsettingbuttonmapping.jsx` | Create | Button mapping UI section |
| `src/renderer/views/viewdevicesettings.jsx` | Modify | Add SectionSettingButtonMapping component |
