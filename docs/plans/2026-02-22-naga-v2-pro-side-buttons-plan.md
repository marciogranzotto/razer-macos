# Naga V2 Pro Side Button Configuration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add on-device button remapping, per-panel profiles, and Hypershift layer support for the Razer Naga V2 Pro.

**Architecture:** USB protocol reverse engineering first, then bottom-up implementation: C driver functions in `librazermacos`, N-API bridge in `addon.cc`, device model methods in `RazerDeviceMouse`, new Feature classes, IPC handlers in `Application`, and finally React renderer components.

**Tech Stack:** C (IOKit USB HID), C++ (node-addon-api/N-API), JavaScript (Electron main process), React 16 (renderer)

**Design doc:** `docs/plans/2026-02-22-naga-v2-pro-side-buttons-design.md`

---

## Phase 1: USB Protocol Reverse Engineering

> This phase is manual work done outside the codebase. It produces a protocol specification that informs all subsequent phases.

### Task 1: Set Up USB Capture Environment

**Step 1: Install capture tools on Windows**

Install Wireshark + USBPcap on a Windows machine with Razer Synapse installed. Connect the Naga V2 Pro via USB (wired mode, PID `1532:00A7`).

**Step 2: Establish baseline capture**

Open Wireshark, filter to the Razer USB device. Capture idle traffic to identify the device's USB interface addresses. Note which interface handles HID reports (the control endpoint).

**Step 3: Capture button remapping commands**

In Synapse, remap side button 1 to keyboard key "A". Save. Filter Wireshark for `SET_REPORT` control transfers. Identify the 90-byte report structure matching `struct razer_report` from `librazermacos/src/include/razercommon.h:97-108`:

```
[status] [transaction_id] [remaining_packets (2B)] [protocol_type] [data_size] [command_class] [command_id] [arguments (80B)] [crc] [reserved]
```

**Step 4: Systematic capture matrix**

Remap buttons one at a time, capturing each change:
- Side buttons 1-12 (12-button panel)
- Action types: keyboard key, mouse button (left/right/middle/back/forward), multimedia key (play/pause/volume), disabled
- Swap to 6-button panel, remap buttons 1-6
- Swap to 2-button panel, remap buttons 1-2
- Enable Hypershift on a button, set Hypershift bindings
- Create/switch profiles (up to 5)

**Step 5: Document the protocol**

Create `docs/protocol/naga-v2-pro-button-mapping.md` with:
- Command class and command ID for button mapping
- Byte-level layout of the arguments field
- Button ID values for each panel (2/6/12)
- Action type codes and parameter formats
- Hypershift flag position and values
- Profile switching command details
- Panel detection mechanism (if any)

**Step 6: Commit the protocol doc**

```bash
git add docs/protocol/naga-v2-pro-button-mapping.md
git commit -m "docs: add Naga V2 Pro button mapping USB protocol specification"
```

---

## Phase 2: C Driver Layer

> All files in `librazermacos/` submodule. After this phase, run `yarn rebuild` to compile.

### Task 2: Add Button Mapping Report Builders to `razerchromacommon`

**Files:**
- Modify: `librazermacos/src/include/razerchromacommon.h`
- Modify: `librazermacos/src/lib/razerchromacommon.c`

> **Note:** The exact command class, command ID, and argument layout below are PLACEHOLDERS. Replace them with the actual values discovered in Phase 1. The structure follows the existing `get_razer_report()` pattern from `razercommon.h:114`.

**Step 1: Add function declarations to the header**

Add to `librazermacos/src/include/razerchromacommon.h` before the closing `#endif`:

```c
/*
 * Button Mapping Functions
 *
 * Command class and IDs are from USB protocol capture (Phase 1).
 * See docs/protocol/naga-v2-pro-button-mapping.md
 */
struct razer_report razer_chroma_misc_set_button_mapping(
    unsigned char profile_index,
    unsigned char button_id,
    unsigned char hypershift_flag,
    unsigned char action_type,
    unsigned char action_param_len,
    unsigned char *action_params);

struct razer_report razer_chroma_misc_get_button_mapping(
    unsigned char profile_index,
    unsigned char button_id,
    unsigned char hypershift_flag);

struct razer_report razer_chroma_misc_set_active_profile(unsigned char profile_index);
struct razer_report razer_chroma_misc_get_active_profile(void);
```

**Step 2: Implement the report builders in razerchromacommon.c**

Add to `librazermacos/src/lib/razerchromacommon.c`:

```c
/**
 * Set a button mapping on-device.
 *
 * profile_index: 0-4 (onboard profile slot)
 * button_id: device-specific button identifier (from protocol capture)
 * hypershift_flag: 0x00 = normal layer, 0x01 = Hypershift layer
 * action_type: 0x00=disabled, 0x01=mouse, 0x02=keyboard, 0x0A=multimedia
 * action_param_len: number of bytes in action_params
 * action_params: type-specific parameters (e.g., HID keycode)
 *
 * PLACEHOLDER: command_class and command_id must be updated from Phase 1 capture.
 */
struct razer_report razer_chroma_misc_set_button_mapping(
    unsigned char profile_index,
    unsigned char button_id,
    unsigned char hypershift_flag,
    unsigned char action_type,
    unsigned char action_param_len,
    unsigned char *action_params)
{
    // TODO: Replace 0x02 and 0x0D with actual values from USB capture
    struct razer_report report = get_razer_report(0x02, 0x0D, 0x50);

    report.arguments[0] = profile_index;
    report.arguments[1] = button_id;
    report.arguments[2] = hypershift_flag;
    report.arguments[3] = action_type;
    report.arguments[4] = action_param_len;

    if (action_param_len > 0 && action_params != NULL) {
        memcpy(&report.arguments[5], action_params, action_param_len);
    }

    return report;
}

/**
 * Get the current button mapping from device.
 * Response will contain action_type and action_params in the response report.
 */
struct razer_report razer_chroma_misc_get_button_mapping(
    unsigned char profile_index,
    unsigned char button_id,
    unsigned char hypershift_flag)
{
    // TODO: Replace with actual values. Get variant uses 0x80 | command_id
    struct razer_report report = get_razer_report(0x02, 0x8D, 0x50);

    report.arguments[0] = profile_index;
    report.arguments[1] = button_id;
    report.arguments[2] = hypershift_flag;

    return report;
}

/**
 * Set the active onboard profile.
 */
struct razer_report razer_chroma_misc_set_active_profile(unsigned char profile_index)
{
    // TODO: Replace with actual values from USB capture
    struct razer_report report = get_razer_report(0x05, 0x02, 0x01);
    report.arguments[0] = profile_index;
    return report;
}

/**
 * Get the active onboard profile.
 */
struct razer_report razer_chroma_misc_get_active_profile(void)
{
    // TODO: Replace with actual values from USB capture
    return get_razer_report(0x05, 0x82, 0x01);
}
```

**Step 3: Commit**

```bash
cd librazermacos
git add -A
git commit -m "feat: add button mapping and profile report builders"
cd ..
git add librazermacos
git commit -m "feat: update librazermacos with button mapping report builders"
```

### Task 3: Add Mouse Driver Functions for Button Mapping

**Files:**
- Modify: `librazermacos/src/include/razermouse_driver.h`
- Modify: `librazermacos/src/lib/razermouse_driver.c`

**Step 1: Add declarations to razermouse_driver.h**

Add before the closing `#endif` in `librazermacos/src/include/razermouse_driver.h`:

```c
// Button mapping
ssize_t razer_mouse_attr_write_button_mapping(IOUSBDeviceInterface **usb_dev,
    unsigned char profile_index, unsigned char button_id,
    unsigned char hypershift_flag, unsigned char action_type,
    unsigned char action_param_len, unsigned char *action_params);

ssize_t razer_mouse_attr_read_button_mapping(IOUSBDeviceInterface **usb_dev,
    unsigned char profile_index, unsigned char button_id,
    unsigned char hypershift_flag, char *buf);

// Profile management
ssize_t razer_mouse_attr_write_active_profile(IOUSBDeviceInterface **usb_dev,
    unsigned char profile_index);

ssize_t razer_mouse_attr_read_active_profile(IOUSBDeviceInterface **usb_dev,
    char *buf);
```

**Step 2: Implement in razermouse_driver.c**

Add to end of `librazermacos/src/lib/razermouse_driver.c`. Follow the existing pattern (see `razer_attr_write_dpi` at the same file for the send/receive pattern):

```c
/**
 * Write a button mapping to the device.
 */
ssize_t razer_mouse_attr_write_button_mapping(IOUSBDeviceInterface **usb_dev,
    unsigned char profile_index, unsigned char button_id,
    unsigned char hypershift_flag, unsigned char action_type,
    unsigned char action_param_len, unsigned char *action_params)
{
    struct razer_report report = razer_chroma_misc_set_button_mapping(
        profile_index, button_id, hypershift_flag,
        action_type, action_param_len, action_params);
    struct razer_report response = {0};

    razer_get_report(usb_dev, &report, &response);

    if (response.status != RAZER_CMD_SUCCESSFUL) {
        printf("razermouse: Failed to set button mapping for button %d\n", button_id);
        return -1;
    }
    return 0;
}

/**
 * Read a button mapping from the device.
 * Writes up to 80 bytes of response arguments into buf.
 */
ssize_t razer_mouse_attr_read_button_mapping(IOUSBDeviceInterface **usb_dev,
    unsigned char profile_index, unsigned char button_id,
    unsigned char hypershift_flag, char *buf)
{
    struct razer_report report = razer_chroma_misc_get_button_mapping(
        profile_index, button_id, hypershift_flag);
    struct razer_report response = {0};

    razer_get_report(usb_dev, &report, &response);

    if (response.status == RAZER_CMD_SUCCESSFUL) {
        memcpy(buf, response.arguments, response.data_size);
        return response.data_size;
    }
    printf("razermouse: Failed to get button mapping for button %d\n", button_id);
    return -1;
}

/**
 * Set the active onboard profile.
 */
ssize_t razer_mouse_attr_write_active_profile(IOUSBDeviceInterface **usb_dev,
    unsigned char profile_index)
{
    struct razer_report report = razer_chroma_misc_set_active_profile(profile_index);
    struct razer_report response = {0};

    razer_get_report(usb_dev, &report, &response);

    if (response.status != RAZER_CMD_SUCCESSFUL) {
        printf("razermouse: Failed to set active profile %d\n", profile_index);
        return -1;
    }
    return 0;
}

/**
 * Get the active onboard profile.
 * Returns profile index (0-4) in buf[0].
 */
ssize_t razer_mouse_attr_read_active_profile(IOUSBDeviceInterface **usb_dev,
    char *buf)
{
    struct razer_report report = razer_chroma_misc_get_active_profile();
    struct razer_report response = {0};

    razer_get_report(usb_dev, &report, &response);

    if (response.status == RAZER_CMD_SUCCESSFUL) {
        buf[0] = response.arguments[0];
        return 1;
    }
    printf("razermouse: Failed to get active profile\n");
    return -1;
}
```

**Step 3: Rebuild and commit**

```bash
yarn rebuild
cd librazermacos
git add -A
git commit -m "feat: add mouse driver button mapping and profile functions"
cd ..
git add librazermacos
git commit -m "feat: update librazermacos with mouse button mapping driver functions"
```

---

## Phase 3: N-API Bridge

### Task 4: Expose Button Mapping Functions in addon.cc

**Files:**
- Modify: `src/driver/addon.cc`

**Step 1: Add button mapping N-API wrapper functions**

Add these functions after the `MouseSetRightBrightness` function (around line 493) in `src/driver/addon.cc`:

```cpp
/**
 * Button mapping functions
 */
Napi::Number MouseSetButtonMapping(const Napi::CallbackInfo &info) {
    Napi::Env env = info.Env();
    RazerDevice device = getRazerDeviceFor(info);

    unsigned char profileIndex = info[1].ToNumber().Uint32Value();
    unsigned char buttonId = info[2].ToNumber().Uint32Value();
    unsigned char hypershiftFlag = info[3].ToNumber().Uint32Value();
    unsigned char actionType = info[4].ToNumber().Uint32Value();

    Napi::Uint8Array paramsArr = info[5].As<Napi::Uint8Array>();
    unsigned char actionParamLen = paramsArr.ElementLength();
    unsigned char *actionParams = paramsArr.Data();

    ssize_t result = razer_mouse_attr_write_button_mapping(
        device.usbDevice, profileIndex, buttonId, hypershiftFlag,
        actionType, actionParamLen, actionParams);

    return Napi::Number::New(env, result);
}

Napi::Object MouseGetButtonMapping(const Napi::CallbackInfo &info) {
    Napi::Env env = info.Env();
    RazerDevice device = getRazerDeviceFor(info);

    unsigned char profileIndex = info[1].ToNumber().Uint32Value();
    unsigned char buttonId = info[2].ToNumber().Uint32Value();
    unsigned char hypershiftFlag = info[3].ToNumber().Uint32Value();

    char buf[80] = {0};
    ssize_t len = razer_mouse_attr_read_button_mapping(
        device.usbDevice, profileIndex, buttonId, hypershiftFlag, buf);

    Napi::Object result = Napi::Object::New(env);
    if (len > 0) {
        result.Set("success", Napi::Boolean::New(env, true));
        result.Set("profileIndex", Napi::Number::New(env, (unsigned char)buf[0]));
        result.Set("buttonId", Napi::Number::New(env, (unsigned char)buf[1]));
        result.Set("hypershiftFlag", Napi::Number::New(env, (unsigned char)buf[2]));
        result.Set("actionType", Napi::Number::New(env, (unsigned char)buf[3]));
        result.Set("actionParamLen", Napi::Number::New(env, (unsigned char)buf[4]));

        Napi::Uint8Array params = Napi::Uint8Array::New(env, (unsigned char)buf[4]);
        for (int i = 0; i < (unsigned char)buf[4]; i++) {
            params[i] = (unsigned char)buf[5 + i];
        }
        result.Set("actionParams", params);
    } else {
        result.Set("success", Napi::Boolean::New(env, false));
    }
    return result;
}

Napi::Number MouseSetActiveProfile(const Napi::CallbackInfo &info) {
    Napi::Env env = info.Env();
    RazerDevice device = getRazerDeviceFor(info);

    unsigned char profileIndex = info[1].ToNumber().Uint32Value();
    ssize_t result = razer_mouse_attr_write_active_profile(device.usbDevice, profileIndex);

    return Napi::Number::New(env, result);
}

Napi::Number MouseGetActiveProfile(const Napi::CallbackInfo &info) {
    Napi::Env env = info.Env();
    RazerDevice device = getRazerDeviceFor(info);

    char buf[1] = {0};
    ssize_t result = razer_mouse_attr_read_active_profile(device.usbDevice, buf);

    if (result > 0) {
        return Napi::Number::New(env, (unsigned char)buf[0]);
    }
    return Napi::Number::New(env, -1);
}
```

**Step 2: Register the exports**

Add to the `Init` function's exports section (after `mouseSetRightBrightness` around line 939):

```cpp
    // Button mapping
    exports.Set("mouseSetButtonMapping", Napi::Function::New(env, MouseSetButtonMapping));
    exports.Set("mouseGetButtonMapping", Napi::Function::New(env, MouseGetButtonMapping));
    exports.Set("mouseSetActiveProfile", Napi::Function::New(env, MouseSetActiveProfile));
    exports.Set("mouseGetActiveProfile", Napi::Function::New(env, MouseGetActiveProfile));
```

**Step 3: Rebuild and commit**

```bash
yarn rebuild
git add src/driver/addon.cc
git commit -m "feat: expose button mapping functions via N-API bridge"
```

---

## Phase 4: Feature System and Device Model

### Task 5: Add Feature Identifiers and Feature Classes

**Files:**
- Modify: `src/main/feature/featureidentifier.js`
- Create: `src/main/feature/featurebuttonmapping.js`
- Create: `src/main/feature/featurehypershift.js`
- Modify: `src/main/feature/featurehelper.js`

**Step 1: Add new identifiers to featureidentifier.js**

Add at end of `src/main/feature/featureidentifier.js`:

```javascript
FeatureIdentifier.BUTTON_MAPPING = 'buttonMapping';
FeatureIdentifier.HYPERSHIFT = 'hypershift';
```

**Step 2: Create FeatureButtonMapping class**

Create `src/main/feature/featurebuttonmapping.js`:

```javascript
import { Feature } from './feature';
import { FeatureIdentifier } from './featureidentifier';

export class FeatureButtonMapping extends Feature {
  constructor(config) {
    super(FeatureIdentifier.BUTTON_MAPPING, config);
  }

  getDefaultConfiguration() {
    return {
      "panelTypes": [2, 6, 12],
      "maxProfiles": 5,
      "defaultPanelType": 12
    };
  }
}
```

**Step 3: Create FeatureHypershift class**

Create `src/main/feature/featurehypershift.js`:

```javascript
import { Feature } from './feature';
import { FeatureIdentifier } from './featureidentifier';

export class FeatureHypershift extends Feature {
  constructor(config) {
    super(FeatureIdentifier.HYPERSHIFT, config);
  }

  getDefaultConfiguration() {
    return {
      "triggerButton": null
    };
  }
}
```

**Step 4: Register in FeatureHelper**

In `src/main/feature/featurehelper.js`:

Add imports at top:
```javascript
import { FeatureButtonMapping } from './featurebuttonmapping';
import { FeatureHypershift } from './featurehypershift';
```

Add cases to `createFeatureFrom` switch:
```javascript
      case FeatureIdentifier.BUTTON_MAPPING: return new FeatureButtonMapping(configuration);
      case FeatureIdentifier.HYPERSHIFT: return new FeatureHypershift(configuration);
```

Note: Do NOT add these to `getDefaultFeaturesFor('mouse')` — they are opt-in per device via JSON config.

**Step 5: Commit**

```bash
git add src/main/feature/featureidentifier.js \
        src/main/feature/featurebuttonmapping.js \
        src/main/feature/featurehypershift.js \
        src/main/feature/featurehelper.js
git commit -m "feat: add FeatureButtonMapping and FeatureHypershift feature classes"
```

### Task 6: Update Device Configs

**Files:**
- Modify: `src/devices/naga_v2_pro_wired.json`
- Modify: `src/devices/naga_v2_pro_wireless.json`

**Step 1: Add button mapping features to wired config**

Update `src/devices/naga_v2_pro_wired.json` to include the new features in `featuresConfig`:

```json
{
  "name": "Razer Naga V2 Pro - Wired",
  "productId": "0x00A7",
  "mainType": "mouse",
  "image": "https://assets.razerzone.com/eeimages/support/products/1874/nagav2pro.png",
  "features": null,
  "featuresMissing": ["oldMouseEffects","waveSimple"],
  "featuresConfig": [
    {
      "mouseBrightness": {
        "enabledMatrix": true,
        "enabledLogo": false,
        "enabledScroll": false,
        "enabledLeft": false,
        "enabledRight": false
      }
    },
    {
      "dpi": {
        "max": 30000
      }
    },
    {
      "buttonMapping": {
        "panelTypes": [2, 6, 12],
        "maxProfiles": 5,
        "defaultPanelType": 12
      }
    },
    {
      "hypershift": {
        "triggerButton": null
      }
    }
  ]
}
```

**Step 2: Apply same changes to wireless config**

Same changes to `src/devices/naga_v2_pro_wireless.json` (productId `0x00A8`).

**Step 3: Commit**

```bash
git add src/devices/naga_v2_pro_wired.json src/devices/naga_v2_pro_wireless.json
git commit -m "feat: add buttonMapping and hypershift features to Naga V2 Pro configs"
```

### Task 7: Add Button Mapping Methods to RazerDeviceMouse

**Files:**
- Modify: `src/main/device/razerdevicemouse.js`

**Step 1: Add button mapping methods**

Add these methods to the `RazerDeviceMouse` class in `src/main/device/razerdevicemouse.js`:

```javascript
  // Button mapping
  getButtonMapping(profileIndex, buttonId, hypershiftFlag) {
    return this.addon.mouseGetButtonMapping(this.internalId, profileIndex, buttonId, hypershiftFlag);
  }

  setButtonMapping(profileIndex, buttonId, hypershiftFlag, actionType, actionParams) {
    return this.addon.mouseSetButtonMapping(
      this.internalId, profileIndex, buttonId, hypershiftFlag,
      actionType, new Uint8Array(actionParams));
  }

  getAllButtonMappings(profileIndex, buttonCount, hypershiftFlag) {
    const mappings = [];
    for (let i = 0; i < buttonCount; i++) {
      const mapping = this.getButtonMapping(profileIndex, i, hypershiftFlag);
      mappings.push(mapping);
    }
    return mappings;
  }

  // Profile management
  getActiveProfile() {
    return this.addon.mouseGetActiveProfile(this.internalId);
  }

  setActiveProfile(profileIndex) {
    return this.addon.mouseSetActiveProfile(this.internalId, profileIndex);
  }
```

**Step 2: Update init() to load button mapping state**

In the `init()` method, add after the brightness initialization:

```javascript
    if(this.hasFeature(FeatureIdentifier.BUTTON_MAPPING)) {
      this.activeProfile = this.addon.mouseGetActiveProfile(this.internalId);
    }
```

Add the import at top if not already present:
```javascript
import { FeatureIdentifier } from '../feature/featureidentifier';
```
(Already imported — just verify.)

**Step 3: Update getState() and resetToState()**

In `getState()`, add:
```javascript
    if(this.hasFeature(FeatureIdentifier.BUTTON_MAPPING)) {
      deviceState['activeProfile'] = this.activeProfile;
    }
```

In `resetToState()`, add:
```javascript
    if(this.hasFeature(FeatureIdentifier.BUTTON_MAPPING)) {
      if(typeof state.activeProfile !== 'undefined') {
        this.setActiveProfile(state.activeProfile);
      }
    }
```

**Step 4: Commit**

```bash
git add src/main/device/razerdevicemouse.js
git commit -m "feat: add button mapping and profile methods to RazerDeviceMouse"
```

---

## Phase 5: IPC Handlers

### Task 8: Add IPC Handlers in Application

**Files:**
- Modify: `src/main/application.js`

**Step 1: Add button mapping IPC handlers**

In the `initListeners()` method of `src/main/application.js`, add after the existing `ipcMain.on` registrations (around line 215):

```javascript
    ipcMain.on('get-button-mappings', (event, arg) => {
      const device = this.razerApplication.deviceManager.getByInternalId(arg.device.internalId);
      if (device && device.hasFeature(FeatureIdentifier.BUTTON_MAPPING)) {
        const mappings = device.getAllButtonMappings(
          arg.profileIndex, arg.buttonCount, arg.hypershiftFlag);
        event.reply('button-mappings-response', { mappings, deviceId: arg.device.internalId });
      }
    });

    ipcMain.on('set-button-mapping', (_, arg) => {
      const device = this.razerApplication.deviceManager.getByInternalId(arg.device.internalId);
      if (device) {
        device.setButtonMapping(
          arg.profileIndex, arg.buttonId, arg.hypershiftFlag,
          arg.actionType, arg.actionParams);
      }
    });

    ipcMain.on('get-active-profile', (event, arg) => {
      const device = this.razerApplication.deviceManager.getByInternalId(arg.device.internalId);
      if (device && device.hasFeature(FeatureIdentifier.BUTTON_MAPPING)) {
        const profile = device.getActiveProfile();
        event.reply('active-profile-response', { profile, deviceId: arg.device.internalId });
      }
    });

    ipcMain.on('set-active-profile', (_, arg) => {
      const device = this.razerApplication.deviceManager.getByInternalId(arg.device.internalId);
      if (device) {
        device.setActiveProfile(arg.profileIndex);
      }
    });
```

**Step 2: Add FeatureIdentifier import if needed**

Verify `FeatureIdentifier` is imported in application.js. If not, add:
```javascript
import { FeatureIdentifier } from './feature/featureidentifier';
```

**Step 3: Verify DeviceManager has getByInternalId**

Check if `RazerDeviceManager` has a `getByInternalId` method. If not, add to `src/main/razerdevicemanager.js`:

```javascript
  getByInternalId(internalId) {
    return this.devices.find(d => d.internalId === internalId);
  }
```

**Step 4: Commit**

```bash
git add src/main/application.js src/main/razerdevicemanager.js
git commit -m "feat: add IPC handlers for button mapping and profile management"
```

---

## Phase 6: Renderer UI

### Task 9: Create Button Grid Component

**Files:**
- Create: `src/renderer/components/ButtonGrid.jsx`

**Step 1: Create the ButtonGrid component**

This component renders the side panel button layout (2, 6, or 12 buttons) as a clickable grid.

```jsx
import React from 'react';

const PANEL_LAYOUTS = {
  2: { rows: 1, cols: 2, labels: ['1', '2'] },
  6: { rows: 3, cols: 2, labels: ['1', '2', '3', '4', '5', '6'] },
  12: { rows: 4, cols: 3, labels: ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'] },
};

export class ButtonGrid extends React.Component {
  render() {
    const { panelType, mappings, selectedButton, onButtonClick } = this.props;
    const layout = PANEL_LAYOUTS[panelType] || PANEL_LAYOUTS[12];

    return (
      <div className="button-grid" style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${layout.cols}, 1fr)`,
        gap: '4px',
        maxWidth: '200px',
        margin: '0 auto'
      }}>
        {layout.labels.map((label, index) => {
          const mapping = mappings && mappings[index];
          const isSelected = selectedButton === index;
          return (
            <button
              key={index}
              className={`grid-button ${isSelected ? 'selected' : ''}`}
              onClick={() => onButtonClick(index)}
              style={{
                padding: '8px 4px',
                fontSize: '11px',
                textAlign: 'center',
                cursor: 'pointer',
                border: isSelected ? '2px solid #44D62C' : '1px solid #555',
                borderRadius: '4px',
                background: isSelected ? '#2a3a2a' : '#1a1a1a',
                color: '#fff',
              }}
            >
              <div style={{ fontWeight: 'bold' }}>{label}</div>
              {mapping && mapping.success && (
                <div style={{ fontSize: '9px', color: '#aaa', marginTop: '2px' }}>
                  {getActionLabel(mapping.actionType, mapping.actionParams)}
                </div>
              )}
            </button>
          );
        })}
      </div>
    );
  }
}

function getActionLabel(actionType, actionParams) {
  switch (actionType) {
    case 0x00: return 'Off';
    case 0x01: return 'Mouse';
    case 0x02: return 'Key';
    case 0x0A: return 'Media';
    default: return '?';
  }
}
```

**Step 2: Commit**

```bash
git add src/renderer/components/ButtonGrid.jsx
git commit -m "feat: add ButtonGrid component for side panel visualization"
```

### Task 10: Create Button Binding Editor Component

**Files:**
- Create: `src/renderer/components/ButtonBindingEditor.jsx`

**Step 1: Create the editor component**

```jsx
import React from 'react';

const ACTION_TYPES = [
  { value: 0x02, label: 'Keyboard Key' },
  { value: 0x01, label: 'Mouse Button' },
  { value: 0x0A, label: 'Multimedia' },
  { value: 0x00, label: 'Disabled' },
];

const MOUSE_BUTTONS = [
  { value: 0x01, label: 'Left Click' },
  { value: 0x02, label: 'Right Click' },
  { value: 0x03, label: 'Middle Click' },
  { value: 0x04, label: 'Back' },
  { value: 0x05, label: 'Forward' },
];

const MEDIA_KEYS = [
  { value: 0xCD, label: 'Play/Pause' },
  { value: 0xB5, label: 'Next Track' },
  { value: 0xB6, label: 'Previous Track' },
  { value: 0xE9, label: 'Volume Up' },
  { value: 0xEA, label: 'Volume Down' },
  { value: 0xE2, label: 'Mute' },
];

export class ButtonBindingEditor extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      actionType: props.currentMapping ? props.currentMapping.actionType : 0x02,
      actionParam: 0,
      listeningForKey: false,
    };
  }

  handleActionTypeChange(e) {
    this.setState({ actionType: parseInt(e.target.value), actionParam: 0, listeningForKey: false });
  }

  handleKeyCapture(e) {
    if (this.state.listeningForKey) {
      e.preventDefault();
      this.setState({ actionParam: e.keyCode, listeningForKey: false });
    }
  }

  handleApply() {
    const { actionType, actionParam } = this.state;
    this.props.onApply(actionType, [actionParam]);
  }

  renderParamSelector() {
    const { actionType, actionParam, listeningForKey } = this.state;

    switch (actionType) {
      case 0x02: // Keyboard
        return (
          <div>
            <button
              onClick={() => this.setState({ listeningForKey: true })}
              onKeyDown={(e) => this.handleKeyCapture(e)}
              style={{
                padding: '8px 16px',
                background: listeningForKey ? '#44D62C' : '#333',
                color: listeningForKey ? '#000' : '#fff',
                border: '1px solid #555',
                borderRadius: '4px',
                cursor: 'pointer',
              }}
            >
              {listeningForKey ? 'Press a key...' : (actionParam ? `Key: ${actionParam}` : 'Click to set key')}
            </button>
          </div>
        );

      case 0x01: // Mouse
        return (
          <select
            value={actionParam}
            onChange={(e) => this.setState({ actionParam: parseInt(e.target.value) })}
            style={{ padding: '4px', background: '#333', color: '#fff', border: '1px solid #555' }}
          >
            <option value={0}>Select...</option>
            {MOUSE_BUTTONS.map(b => <option key={b.value} value={b.value}>{b.label}</option>)}
          </select>
        );

      case 0x0A: // Multimedia
        return (
          <select
            value={actionParam}
            onChange={(e) => this.setState({ actionParam: parseInt(e.target.value) })}
            style={{ padding: '4px', background: '#333', color: '#fff', border: '1px solid #555' }}
          >
            <option value={0}>Select...</option>
            {MEDIA_KEYS.map(k => <option key={k.value} value={k.value}>{k.label}</option>)}
          </select>
        );

      case 0x00: // Disabled
        return <div style={{ color: '#888' }}>Button will be disabled</div>;

      default:
        return null;
    }
  }

  render() {
    const { buttonIndex, onCancel } = this.props;

    return (
      <div style={{
        padding: '12px',
        background: '#222',
        borderRadius: '6px',
        border: '1px solid #444',
        marginTop: '8px',
      }}>
        <div style={{ marginBottom: '8px', fontWeight: 'bold' }}>
          Button {buttonIndex + 1}
        </div>

        <div style={{ marginBottom: '8px' }}>
          <select
            value={this.state.actionType}
            onChange={(e) => this.handleActionTypeChange(e)}
            style={{ padding: '4px', background: '#333', color: '#fff', border: '1px solid #555' }}
          >
            {ACTION_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>

        <div style={{ marginBottom: '12px' }}>
          {this.renderParamSelector()}
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => this.handleApply()}
            style={{
              padding: '6px 16px',
              background: '#44D62C',
              color: '#000',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 'bold',
            }}
          >
            Apply
          </button>
          <button
            onClick={onCancel}
            style={{
              padding: '6px 16px',
              background: '#555',
              color: '#fff',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
            }}
          >
            Cancel
          </button>
        </div>
      </div>
    );
  }
}
```

**Step 2: Commit**

```bash
git add src/renderer/components/ButtonBindingEditor.jsx
git commit -m "feat: add ButtonBindingEditor component for action assignment"
```

### Task 11: Create Section Setting for Button Mapping

**Files:**
- Create: `src/renderer/sections/sectionsettingbuttonmapping.jsx`
- Modify: `src/renderer/views/viewdevicesettings.jsx`

**Step 1: Create SectionSettingButtonMapping**

Create `src/renderer/sections/sectionsettingbuttonmapping.jsx`:

```jsx
import React from 'react';
import { SectionSettingBlock } from './sectionsettingblock';
import { ButtonGrid } from '../components/ButtonGrid';
import { ButtonBindingEditor } from '../components/ButtonBindingEditor';
import { ipcRenderer } from 'electron';
import { FeatureIdentifier } from '../../main/feature/featureidentifier';

const PANEL_BUTTON_COUNTS = { 2: 2, 6: 6, 12: 12 };

export class SectionSettingButtonMapping extends SectionSettingBlock {
  constructor(props) {
    super(props);
    this.buttonMappingFeature = this.deviceSelected.features.find(
      f => f.featureIdentifier === FeatureIdentifier.BUTTON_MAPPING
    );
    this.state = {
      selectedButton: null,
      hypershiftActive: false,
      activeProfile: 0,
      panelType: this.buttonMappingFeature
        ? this.buttonMappingFeature.configuration.defaultPanelType
        : 12,
      mappings: [],
    };
  }

  componentDidMount() {
    ipcRenderer.on('button-mappings-response', (_, data) => {
      if (data.deviceId === this.deviceSelected.internalId) {
        this.setState({ mappings: data.mappings });
      }
    });
    ipcRenderer.on('active-profile-response', (_, data) => {
      if (data.deviceId === this.deviceSelected.internalId) {
        this.setState({ activeProfile: data.profile });
      }
    });
    this.loadMappings();
    this.loadActiveProfile();
  }

  componentWillUnmount() {
    ipcRenderer.removeAllListeners('button-mappings-response');
    ipcRenderer.removeAllListeners('active-profile-response');
  }

  loadMappings() {
    const buttonCount = PANEL_BUTTON_COUNTS[this.state.panelType] || 12;
    ipcRenderer.send('get-button-mappings', {
      device: this.deviceSelected,
      profileIndex: this.state.activeProfile,
      buttonCount: buttonCount,
      hypershiftFlag: this.state.hypershiftActive ? 0x01 : 0x00,
    });
  }

  loadActiveProfile() {
    ipcRenderer.send('get-active-profile', { device: this.deviceSelected });
  }

  handleButtonClick(buttonIndex) {
    this.setState({ selectedButton: buttonIndex });
  }

  handleApplyBinding(actionType, actionParams) {
    ipcRenderer.send('set-button-mapping', {
      device: this.deviceSelected,
      profileIndex: this.state.activeProfile,
      buttonId: this.state.selectedButton,
      hypershiftFlag: this.state.hypershiftActive ? 0x01 : 0x00,
      actionType: actionType,
      actionParams: actionParams,
    });
    this.setState({ selectedButton: null });
    setTimeout(() => this.loadMappings(), 200);
  }

  handleLayerToggle() {
    this.setState(
      prev => ({ hypershiftActive: !prev.hypershiftActive, selectedButton: null }),
      () => this.loadMappings()
    );
  }

  handleProfileChange(e) {
    const profileIndex = parseInt(e.target.value);
    ipcRenderer.send('set-active-profile', {
      device: this.deviceSelected,
      profileIndex: profileIndex,
    });
    this.setState(
      { activeProfile: profileIndex, selectedButton: null },
      () => this.loadMappings()
    );
  }

  handlePanelChange(e) {
    this.setState(
      { panelType: parseInt(e.target.value), selectedButton: null },
      () => this.loadMappings()
    );
  }

  renderTitle() {
    return 'Side Buttons';
  }

  renderSettings() {
    if (!this.buttonMappingFeature) {
      return null;
    }

    const { selectedButton, hypershiftActive, activeProfile, panelType, mappings } = this.state;
    const maxProfiles = this.buttonMappingFeature.configuration.maxProfiles || 5;

    return (
      <div>
        <div style={{ display: 'flex', gap: '12px', marginBottom: '12px', alignItems: 'center' }}>
          <div>
            <label style={{ fontSize: '11px', color: '#aaa' }}>Profile</label>
            <select
              value={activeProfile}
              onChange={(e) => this.handleProfileChange(e)}
              style={{ display: 'block', padding: '4px', background: '#333', color: '#fff', border: '1px solid #555' }}
            >
              {Array.from({ length: maxProfiles }, (_, i) => (
                <option key={i} value={i}>Profile {i + 1}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ fontSize: '11px', color: '#aaa' }}>Panel</label>
            <select
              value={panelType}
              onChange={(e) => this.handlePanelChange(e)}
              style={{ display: 'block', padding: '4px', background: '#333', color: '#fff', border: '1px solid #555' }}
            >
              <option value={2}>2-Button</option>
              <option value={6}>6-Button</option>
              <option value={12}>12-Button</option>
            </select>
          </div>

          <div>
            <label style={{ fontSize: '11px', color: '#aaa' }}>Layer</label>
            <button
              onClick={() => this.handleLayerToggle()}
              style={{
                display: 'block',
                padding: '4px 12px',
                background: hypershiftActive ? '#44D62C' : '#333',
                color: hypershiftActive ? '#000' : '#fff',
                border: '1px solid #555',
                borderRadius: '4px',
                cursor: 'pointer',
                fontWeight: hypershiftActive ? 'bold' : 'normal',
              }}
            >
              {hypershiftActive ? 'Hypershift' : 'Normal'}
            </button>
          </div>
        </div>

        <ButtonGrid
          panelType={panelType}
          mappings={mappings}
          selectedButton={selectedButton}
          onButtonClick={(i) => this.handleButtonClick(i)}
        />

        {selectedButton !== null && (
          <ButtonBindingEditor
            buttonIndex={selectedButton}
            currentMapping={mappings[selectedButton]}
            onApply={(actionType, actionParams) => this.handleApplyBinding(actionType, actionParams)}
            onCancel={() => this.setState({ selectedButton: null })}
          />
        )}
      </div>
    );
  }
}
```

**Step 2: Add to ViewDeviceSettings**

Modify `src/renderer/views/viewdevicesettings.jsx`:

Add import:
```javascript
import { SectionSettingButtonMapping } from '../sections/sectionsettingbuttonmapping';
```

Add the component in the render JSX, after `SectionSettingBrightness`:
```jsx
          <SectionSettingButtonMapping deviceSelected={this.deviceSelected} />
```

**Step 3: Commit**

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx \
        src/renderer/components/ButtonGrid.jsx \
        src/renderer/components/ButtonBindingEditor.jsx \
        src/renderer/views/viewdevicesettings.jsx
git commit -m "feat: add side button configuration UI with grid, editor, profiles, and Hypershift"
```

---

## Phase 7: Integration Testing

### Task 12: End-to-End Validation

**Step 1: Rebuild native addon**

```bash
yarn clean && yarn rebuild
```

**Step 2: Run dev server**

```bash
yarn dev
```

**Step 3: Test with 12-button panel**

- Connect Naga V2 Pro with 12-button panel
- Open device settings in the browser window
- Verify the "Side Buttons" section appears
- Click button 1, set it to keyboard key "A", click Apply
- Verify the binding is sent to the device (check console for errors)
- Disconnect and reconnect — verify binding persists

**Step 4: Test profile switching**

- Switch to Profile 2
- Set different bindings
- Switch back to Profile 1 — verify original bindings are shown

**Step 5: Test Hypershift**

- Toggle to Hypershift layer
- Set different bindings for Hypershift
- Toggle back to Normal — verify Normal bindings shown

**Step 6: Test panel switching**

- Switch panel selector to 6-button
- Verify grid updates to 3x2 layout
- Switch to 2-button — verify 1x2 layout

**Step 7: Commit any fixes**

```bash
git add -A
git commit -m "fix: integration test fixes for side button configuration"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | USB Protocol RE | Manual (Wireshark captures) |
| 2 | Report builders in razerchromacommon | `librazermacos/src/{lib,include}/razerchromacommon.{c,h}` |
| 3 | Mouse driver functions | `librazermacos/src/{lib,include}/razermouse_driver.{c,h}` |
| 4 | N-API bridge | `src/driver/addon.cc` |
| 5 | Feature classes | `src/main/feature/feature{identifier,buttonmapping,hypershift,helper}.js` |
| 6 | Device configs | `src/devices/naga_v2_pro_{wired,wireless}.json` |
| 7 | Device model methods | `src/main/device/razerdevicemouse.js` |
| 8 | IPC handlers | `src/main/application.js`, `src/main/razerdevicemanager.js` |
| 9 | Button grid component | `src/renderer/components/ButtonGrid.jsx` |
| 10 | Binding editor component | `src/renderer/components/ButtonBindingEditor.jsx` |
| 11 | Section + view integration | `src/renderer/sections/sectionsettingbuttonmapping.jsx`, `viewdevicesettings.jsx` |
| 12 | End-to-end validation | All files |

**Critical dependency:** Tasks 2-12 all depend on Task 1 (USB Protocol RE). The command class, command ID, and argument layouts in Tasks 2-4 are placeholders that MUST be replaced with actual values from the USB capture.
