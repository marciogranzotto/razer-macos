# Razer Naga V2 Pro Support — Design

## Goal

Add support for the Razer Naga V2 Pro mouse (wired + wireless dongle) to razer-macos.

## Device Details

- **Product IDs**: Wired `0x00A7`, Wireless `0x00A8`
- **Max DPI**: 30,000
- **Transaction ID**: `0x1f` (differs from Naga Pro's default `0x3f`)
- **Connection modes**: USB wired, 2.4GHz wireless dongle (both supported)
- **OpenRazer reference**: v3.10.3 added support

## Supported Features

Matches the existing Naga Pro config with `featuresMissing: ["oldMouseEffects", "waveSimple"]`:

- Static, Spectrum, Reactive, Breath, None (lighting effects)
- Battery level and charging status
- DPI (up to 30,000)
- Poll rate
- Matrix brightness (logo/scroll/left/right brightness disabled)

## LED Mapping (per openrazer source)

The V2 Pro uses different LEDs per effect, unlike the Naga Pro which uses a uniform `side` LED:

| Effect | LED Target | Function Style |
|--------|-----------|----------------|
| Static | `ZERO_LED` (0x00) | `razer_chroma_extended_matrix_effect_static` |
| Spectrum | `BACKLIGHT_LED` (0x05) | `razer_chroma_mouse_extended_matrix_effect_spectrum` |
| Breath | `BACKLIGHT_LED` (0x05) | `razer_chroma_mouse_extended_matrix_effect_breathing_*` |
| None | standard | `razer_chroma_standard_matrix_effect_none` with txid `0xFF` |
| Brightness | `ZERO_LED` (0x00) | `razer_chroma_extended_matrix_brightness` |
| DPI/Poll/Battery | standard | With transaction ID `0x1f` |

## Changes Required

### 1. JSON Device Configs (2 new files)

- `src/devices/naga_v2_pro_wired.json` — productId `0x00A7`
- `src/devices/naga_v2_pro_wireless.json` — productId `0x00A8`

Both mirror the Naga Pro config with `dpi.max: 30000`.

### 2. C Driver (librazermacos submodule)

**`razermouse_driver.h`**: Add `USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED` (0x00A7) and `USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS` (0x00A8).

**`razerdevice.c`**: Add both IDs to device enumeration.

**`razermouse_driver.c`**: Add case entries in all effect/brightness/DPI/poll/battery functions. Each report sets `transaction_id.id = 0x1f`. Wireless receiver uses `RAZER_NEW_MOUSE_RECEIVER_WAIT_MIN_US` timing.

### 3. No Changes Needed

- `addon.cc` — existing mouse functions cover all needed operations
- JS/Electron layer — `RazerDeviceMouse` + feature system handles everything

## Testing

With the wireless dongle connected (confirmed at `0x00A8`):
1. `yarn rebuild` after C driver changes
2. `yarn dev` — device should appear in the tray menu
3. Test: static color, spectrum, breath, none, brightness slider, DPI, battery level

## Sources

- [OpenRazer v3.10.3 release](https://www.gamingonlinux.com/2025/05/openrazer-adds-support-for-razer-naga-v2-pro-and-razer-strider-chroma-plus-bug-fixes-and-new-kernel-support/)
- [OpenRazer Naga V2 Pro issue #1991](https://github.com/openrazer/openrazer/issues/1991)
- [OpenRazer razermouse_driver.c](https://github.com/openrazer/openrazer/blob/master/driver/razermouse_driver.c)
