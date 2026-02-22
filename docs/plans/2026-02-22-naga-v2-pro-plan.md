# Razer Naga V2 Pro — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Razer Naga V2 Pro support (wired 0x00A7 + wireless 0x00A8) with lighting effects, DPI, poll rate, battery, and brightness.

**Architecture:** Two JSON device configs + C driver changes in librazermacos submodule. No JS/addon.cc changes needed — the existing mouse device class and feature system handle everything once the C driver recognizes the product IDs.

**Tech Stack:** C (IOKit USB HID drivers), node-gyp native addon, JSON device configs

**Design doc:** `docs/plans/2026-02-22-naga-v2-pro-design.md`

---

### Task 1: Create feature branch

**Step 1: Create and switch to a new branch**

Run: `git checkout -b feature/naga-v2-pro`

**Step 2: Verify branch**

Run: `git branch --show-current`
Expected: `feature/naga-v2-pro`

---

### Task 2: Add JSON device configs

**Files:**
- Create: `src/devices/naga_v2_pro_wired.json`
- Create: `src/devices/naga_v2_pro_wireless.json`
- Reference: `src/devices/naga_pro_wired.json` (template)

**Step 1: Create wired config**

Create `src/devices/naga_v2_pro_wired.json`:

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
    }
  ]
}
```

**Step 2: Create wireless config**

Create `src/devices/naga_v2_pro_wireless.json`:

```json
{
  "name": "Razer Naga V2 Pro - Wireless",
  "productId": "0x00A8",
  "mainType": "mouse",
  "image": "https://assets.razerzone.com/eeimages/support/products/1874/nagav2pro.png",
  "features": null,
  "featuresMissing": ["oldMouseEffects","waveSimple"],
  "featuresConfig": [
    {
      "mouseBrightness": {
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
    }
  ]
}
```

**Step 3: Commit**

```bash
git add src/devices/naga_v2_pro_wired.json src/devices/naga_v2_pro_wireless.json
git commit -m "feat: add Naga V2 Pro device configs (wired + wireless)"
```

---

### Task 3: Add USB product ID defines

**Files:**
- Modify: `librazermacos/src/include/razermouse_driver.h:56` (after NAGA_PRO_WIRED define)

**Step 1: Add defines after the existing Naga Pro defines (line 56)**

Add these two lines after `#define USB_DEVICE_ID_RAZER_NAGA_PRO_WIRED 0x008F`:

```c
#define USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED    0x00A7
#define USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS  0x00A8
```

**Step 2: Commit**

```bash
git add librazermacos/src/include/razermouse_driver.h
git commit -m "feat: add Naga V2 Pro USB product ID defines"
```

---

### Task 4: Add device enumeration

**Files:**
- Modify: `librazermacos/src/lib/razerdevice.c:118` (after NAGA_PRO_WIRED case)

**Step 1: Add case entries in `is_mouse_device()` (after line 118)**

Add these two lines after `case USB_DEVICE_ID_RAZER_NAGA_PRO_WIRED:`:

```c
	case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
	case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
```

**Step 2: Commit**

```bash
git add librazermacos/src/lib/razerdevice.c
git commit -m "feat: add Naga V2 Pro to device enumeration"
```

---

### Task 5: Add USB response timing

**Files:**
- Modify: `librazermacos/src/lib/razermouse_driver.c:60` (in `razer_get_report()`)

**Step 1: Add V2 Pro to the wireless receiver timing group**

In the `razer_get_report()` function, after `case USB_DEVICE_ID_RAZER_NAGA_PRO_WIRED:` (line 60), add:

```c
    case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
    case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
```

This groups V2 Pro with the Naga Pro in the `RAZER_NEW_MOUSE_RECEIVER_WAIT_MIN_US` (31ms) timing block.

**Step 2: Commit**

```bash
git add librazermacos/src/lib/razermouse_driver.c
git commit -m "feat: add Naga V2 Pro USB response timing"
```

---

### Task 6: Add lighting effect support in razermouse_driver.c

This is the largest task. The V2 Pro needs its own case blocks (not grouped with Naga Pro) because it uses different LED targets and transaction ID `0x1f`.

**Files:**
- Modify: `librazermacos/src/lib/razermouse_driver.c` (multiple functions)

**Overview of all functions to modify:**

For each function below, add a NEW case block for V2 Pro (wired + wireless) with the specified LED and transaction ID. Place it AFTER the existing Mamba Elite / Basilisk V2 block (which also uses `0x1f`) in each function.

#### 6a: `razer_attr_write_side_mode_static()` — around line 207

After the Mamba Elite/Basilisk V2 block (which ends ~line 213), add:

```c
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
                report = razer_chroma_extended_matrix_effect_static(VARSTORE, ZERO_LED, (struct razer_rgb*)&buf[0]);
                report.transaction_id.id = 0x1f;
                break;
```

#### 6b: `razer_attr_write_side_mode_static_no_store()` — around line 278

After the Mamba Elite/Basilisk V2 block, add:

```c
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
                report = razer_chroma_extended_matrix_effect_static(NOSTORE, ZERO_LED, (struct razer_rgb*)&buf[0]);
                report.transaction_id.id = 0x1f;
                break;
```

#### 6c: `razer_attr_write_side_mode_spectrum()` — around line 342

After the Mamba Elite/Basilisk V2 block, add:

```c
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
                report = razer_chroma_extended_matrix_effect_spectrum(VARSTORE, ZERO_LED);
                report.transaction_id.id = 0x1f;
                break;
```

#### 6d: `razer_attr_write_side_mode_breath()` — around line 434

In the transaction_id override switch inside this function (after Mamba Elite/Basilisk V2 `0x1f` block), add:

```c
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
                report.transaction_id.id = 0x1f;
                break;
```

Also add V2 Pro to the outer effect switch (alongside the Naga Pro cases that use `razer_chroma_extended_matrix_effect_breathing_*`).

#### 6e: `razer_attr_write_side_mode_none()` — around line 480

After the Mamba Elite/Basilisk V2 block, add:

```c
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
                report = razer_chroma_extended_matrix_effect_none(VARSTORE, ZERO_LED);
                report.transaction_id.id = 0x1f;
                break;
```

#### 6f: `razer_attr_write_logo_mode_static()` — around line 662

After the Mamba Elite/Basilisk V2 block, add:

```c
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
                report = razer_chroma_extended_matrix_effect_static(VARSTORE, ZERO_LED, (struct razer_rgb*)&buf[0]);
                report.transaction_id.id = 0x1f;
                break;
```

#### 6g: `razer_attr_write_scroll_mode_static()` — around line 734

After the Mamba Elite/Basilisk V2 block, add the same pattern (ZERO_LED + 0x1f).

#### 6h: `razer_attr_write_logo_mode_static_no_store()` — around line 832

After the Mamba Elite/Basilisk V2 block, add with `NOSTORE` + `ZERO_LED` + `0x1f`.

#### 6i: `razer_attr_write_scroll_mode_static_no_store()` — around line 907

Same pattern as 6h with `NOSTORE`.

#### 6j: `razer_attr_write_logo_mode_spectrum()` — around line 998

After the Mamba Elite/Basilisk V2 block, add:

```c
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
            report = razer_chroma_extended_matrix_effect_spectrum(VARSTORE, ZERO_LED);
            report.transaction_id.id = 0x1f;
            break;
```

#### 6k: `razer_attr_write_scroll_mode_spectrum()` — around line 1059

Same pattern as 6j.

#### 6l: `razer_attr_write_logo_mode_breath()` — around line 1174

Add V2 Pro to the transaction_id override switch with `0x1f` (same as Mamba Elite/Basilisk V2).

Also add V2 Pro to the outer effect switch (alongside the Naga Pro cases).

#### 6m: `razer_attr_write_scroll_mode_breath()` — around line 1264

Same pattern as 6l.

#### 6n: `razer_attr_write_logo_mode_none()` — around line 1348

After the Mamba Elite/Basilisk V2 block, add:

```c
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
            report = razer_chroma_extended_matrix_effect_none(VARSTORE, ZERO_LED);
            report.transaction_id.id = 0x1f;
            break;
```

#### 6o: `razer_attr_write_scroll_mode_none()` — around line 1413

Same pattern as 6n.

#### 6p: `razer_attr_write_logo_mode_reactive()` — around line 1545

After the Mamba Elite/Basilisk V2 block, add:

```c
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
            case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
                report = razer_chroma_extended_matrix_effect_reactive(VARSTORE, ZERO_LED, speed, (struct razer_rgb*)&buf[1]);
                report.transaction_id.id = 0x1f;
                break;
```

**Step 2: Commit**

```bash
git add librazermacos/src/lib/razermouse_driver.c
git commit -m "feat: add Naga V2 Pro lighting effects support"
```

---

### Task 7: Add DPI, battery, poll rate, and brightness support

**Files:**
- Modify: `librazermacos/src/lib/razermouse_driver.c` (4 functions)

#### 7a: `razer_attr_read_dpi()` — line 1676

This function currently has NO product switch. Add one after line 1679 (`report = razer_chroma_misc_get_dpi_xy(0x01);`):

```c
    UInt16 product = -1;
    (*usb_dev)->GetDeviceProduct(usb_dev, &product);
    switch(product) {
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
            report.transaction_id.id = 0x1f;
            break;
    }
```

#### 7b: `razer_attr_write_dpi()` — line 1686

Same pattern. Add after line 1688 (`report = razer_chroma_misc_set_dpi_xy(...)`):

```c
    UInt16 product = -1;
    (*usb_dev)->GetDeviceProduct(usb_dev, &product);
    switch(product) {
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
            report.transaction_id.id = 0x1f;
            break;
    }
```

#### 7c: `razer_attr_read_get_battery()` — line 1692

Add V2 Pro to the existing `0x1f` block (around line 1716, after OROCHI_V2_BLUETOOTH):

```c
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
```

#### 7d: `razer_attr_read_is_charging()` — line 1728

Add V2 Pro to the `0x1f` block (around line 1756, after LANCEHEAD_WIRELESS_WIRED):

```c
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
```

#### 7e: `razer_attr_read_poll_rate()` — line 1769

Add V2 Pro to the `0x1f` block (around line 1817, after OROCHI_V2_BLUETOOTH):

```c
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
```

#### 7f: `razer_attr_write_poll_rate()` — line 1867

Add V2 Pro to the `0x1f` block (around line 1910, after OROCHI_V2_BLUETOOTH):

```c
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
```

#### 7g: `razer_attr_write_matrix_brightness()` — line 1947

V2 Pro should be added to the EXISTING `0x1f` block (around line 1950, alongside NAGA_LEFT_HANDED_2020, NAGA_PRO, MAMBA_ELITE, BASILISK_V3):

```c
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
```

#### 7h: `razer_attr_read_matrix_brightness()` — line 1999

Same — add V2 Pro to the existing `0x1f` block:

```c
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRELESS:
        case USB_DEVICE_ID_RAZER_NAGA_V2_PRO_WIRED:
```

**Step 2: Commit**

```bash
git add librazermacos/src/lib/razermouse_driver.c
git commit -m "feat: add Naga V2 Pro DPI, battery, poll rate, brightness"
```

---

### Task 8: Build and hardware test

**Step 1: Rebuild native addon**

Run: `yarn rebuild`
Expected: Compiles with 0 errors. Warnings are OK.

**Step 2: Start development server**

Run: `yarn dev`
Expected: Electron app launches, tray icon appears. "Razer Naga V2 Pro - Wireless" should appear in the device list.

**Step 3: Test each feature manually**

With the physical device connected via wireless dongle:

1. **Device detection** — Device name appears in tray menu
2. **Static color** — Set static red/green/blue/custom; verify LEDs change
3. **Spectrum** — Activate spectrum mode; verify cycling colors
4. **Breath** — Activate breathing mode; verify pulsing effect
5. **None** — Activate none mode; verify LEDs turn off
6. **Brightness** — Adjust brightness slider; verify LED intensity changes
7. **DPI** — Change DPI in device settings; verify mouse sensitivity changes
8. **Battery** — Battery level should display (check tray menu or device settings)
9. **Reactive** — Set reactive mode with a color; verify LED reacts to clicks

**Step 4: If any effect doesn't work**

The most likely issue is the LED target. If an effect doesn't work with `ZERO_LED`, try changing it to `BACKLIGHT_LED` (0x05) for that specific function. The openrazer source indicates spectrum/breath use `BACKLIGHT_LED` while static uses `ZERO_LED`.

**Step 5: Final commit after testing**

If any adjustments were needed, commit them:

```bash
git add -A
git commit -m "fix: adjust Naga V2 Pro LED targets after hardware testing"
```

---

### Task 9: Final commit and summary

**Step 1: Verify all changes**

Run: `git log --oneline feature/naga-v2-pro --not master`
Expected: 4-6 commits for the feature

**Step 2: Verify build is clean**

Run: `yarn rebuild 2>&1 | tail -5`
Expected: `gyp info ok` at the end

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `src/devices/naga_v2_pro_wired.json` | Create | Device config for wired mode (0x00A7) |
| `src/devices/naga_v2_pro_wireless.json` | Create | Device config for wireless mode (0x00A8) |
| `librazermacos/src/include/razermouse_driver.h` | Modify | Add 2 `#define` lines |
| `librazermacos/src/lib/razerdevice.c` | Modify | Add 2 `case` lines to enumeration |
| `librazermacos/src/lib/razermouse_driver.c` | Modify | Add case blocks in ~20 functions |
