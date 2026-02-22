# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Razer macOS is an open-source Electron menu bar app that manages color effects for Razer peripherals on macOS. It combines C USB drivers (ported from the Linux [openrazer](https://github.com/openrazer/openrazer) project) with a Node.js/React UI, bridged via node-addon-api (N-API).

## Build & Development Commands

```bash
# Clone with submodules (librazermacos + iohook)
git clone --recursive https://github.com/1kc/razer-macos.git

# Install dependencies
yarn

# Run development server (Electron + webpack dev server)
yarn dev

# Rebuild native addon (required after any C/C++ driver code changes)
yarn rebuild

# Clean native build artifacts
yarn clean

# Build distributable app + DMG
yarn dist

# Format JS/JSX
yarn prettier:js

# Full release build (clean, install, build, sign)
./release.sh
```

After modifying any file under `src/driver/` or `librazermacos/`, you must run `yarn rebuild` before `yarn dev` will pick up the changes.

## Architecture

### Three-Layer Stack

1. **C Driver Layer** (`librazermacos/` submodule) — USB HID communication with Razer devices via IOKit/CoreFoundation. Per-device-type driver files: `razerkbd_driver.c`, `razermouse_driver.c`, `razermousemat_driver.c`, `razeregpu_driver.c`, `razerheadphone_driver.c`, `razermousedock_driver.c`, `razeraccessory_driver.c`. Common protocol logic in `razerchromacommon.c`. Device enumeration in `razerdevice.c`.

2. **N-API Bridge** (`src/driver/addon.cc`) — C++ wrapper exposing C driver functions to Node.js. Manages a global `RazerDevices` struct. Each exported function takes an `internalDeviceId` as first arg to look up the target device. Compiled via `binding.gyp` with node-gyp (universal binary: x86_64 + arm64). Loaded at runtime via `src/driver/index.js` → `build/Release/addon.node`.

3. **Electron App** (`src/main/` + `src/renderer/`) — Menu bar tray app with optional BrowserWindow for color picker and settings.

### Main Process Key Classes (`src/main/`)

- **`Application`** (`application.js`) — Electron lifecycle (Tray, BrowserWindow, ipcMain handlers for DPI/brightness/color/state). Entry point: `index.js` → `new Application()`.
- **`RazerApplication`** (`razerapplication.js`) — Core app logic. Owns `DeviceManager`, `SettingsManager`, `StateManager`, and animation instances.
- **`RazerDeviceManager`** (`razerdevicemanager.js`) — Calls `addon.getAllDevices()`, matches USB productIds against JSON config files in `src/devices/`, creates typed `RazerDevice` subclass instances with features.
- **`StateManager`** (`statemanager.js`) — Saves/restores device states on power events (suspend, resume, AC, battery, lock, etc.).
- **`SettingsManager`** (`settingsmanager.js`) — Persists per-device settings (custom colors, DPI) via `electron-json-storage`.

### Device Type Hierarchy (`src/main/device/`)

Base class `RazerDevice` with subclasses per device type: `RazerDeviceKeyboard`, `RazerDeviceMouse`, `RazerDeviceMouseDock`, `RazerDeviceMouseMat`, `RazerDeviceEgpu`, `RazerDeviceHeadphone`, `RazerDeviceAccessory`. Each subclass delegates to the appropriate addon functions (e.g., `KbdSetModeStatic` vs `MouseSetLogoModeStatic`).

Device types are string constants in `RazerDeviceType`: `keyboard`, `mouse`, `mousedock`, `mousemat`, `egpu`, `headphone`, `accessory`.

### Feature System (`src/main/feature/`)

Features are composable capabilities attached to devices. `FeatureHelper.getDefaultFeaturesFor(mainType)` provides defaults per device type. JSON device configs can override via `features` (explicit list), `featuresMissing` (subtract from defaults), or `featuresConfig` (override config like keyboard matrix dimensions).

Feature identifiers: `none`, `static`, `wave_simple`, `wave_extended`, `spectrum`, `reactive`, `breathe`, `starlight`, `brightness`, `ripple`, `wheel`, `old_mouse_effects`, `mouse_brightness`, `poll_rate`, `mouse_dpi`, `battery`.

### Device Configuration (`src/devices/*.json`)

Each JSON file maps a USB product ID (hex string like `"0x024e"`) to a device name, `mainType`, image URL, and optional feature overrides. The `RazerDeviceManager` loads all JSON files via webpack's `require.context`.

### Renderer (`src/renderer/`)

React 16 app with views for color picker (`viewcolorpicker.jsx`), device settings (`viewdevicesettings.jsx`), and state settings (`viewstatesettings.jsx`). Communicates with main process via `ipcRenderer`/`ipcMain`.

### Menu System (`src/main/menu/`)

`menubuilder.js` constructs the tray context menu: global controls (all devices), per-device submenus via `menubuilderdevice.js`. All menu click handlers stop running animations before executing.

### Animations (`src/main/animation/`)

Software-driven animations that run across all devices simultaneously: `animationcyclespectrum.js` (spectrum color cycling), `animationcyclecustom.js` (user-defined color cycling), `animationripple.js`, `animationwheel.js`. Base class `animation.js` manages frame timing.

## Adding a New Device

1. Create a JSON file in `src/devices/` with the device's USB product ID, name, `mainType`, and optional feature overrides.
2. If the device type requires new driver functions, add them to the appropriate driver file in `librazermacos/src/lib/`, expose via `src/driver/addon.cc`, and run `yarn rebuild`.
3. See the [wiki](https://github.com/1kc/razer-macos/wiki) for porting from openrazer.

## Git Submodules

- `librazermacos/` — C driver library (USB HID communication)
- `iohook/` — keyboard/mouse event hooking (used for reactive effects)
