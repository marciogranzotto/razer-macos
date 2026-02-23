# Panel Change Interrupt Detection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Auto-detect Naga V2 Pro side panel swaps via USB interrupt events instead of polling.

**Architecture:** The Razer Naga V2 Pro sends an unsolicited 16-byte HID report on endpoint 0x82 (interface 1, keyboard protocol) when the magnetic side panel is swapped. We add an IOKit async interrupt pipe reader in the C driver, bridge it to Node.js via N-API `ThreadSafeFunction`, emit IPC events from the main process, and update the renderer UI reactively.

**Tech Stack:** C (IOKit USB interrupt pipes, CFRunLoop), C++ (node-addon-api ThreadSafeFunction), JavaScript (Electron IPC)

---

## Background

### USB Protocol for Panel Change Events

From the protocol spec (`docs/specs/naga-v2-pro-button-mapping-protocol.md` lines 359-386):

The wireless dongle (PID 0x00A8) has 3 HID interfaces:
- Interface 0: Mouse (endpoint 0x81 IN)
- Interface 1: Keyboard (endpoint 0x82 IN) — **panel change events arrive here**
- Interface 2: Keyboard (endpoint 0x83 IN)

Panel change report format (16 bytes on endpoint 0x82):
```
05 0e [panel_id] 00 00 00 00 00 00 00 00 00 00 00 00 00
```

Panel IDs: `0x00` = removed, `0x01` = 2-button, `0x03` = 12-button, `0x04` = 6-button.

### Current Architecture Constraints

- All USB communication is synchronous control transfers via `IOUSBDeviceInterface->DeviceRequest()`
- The C driver opens devices via `USBDeviceOpen()` but never opens specific interfaces or claims them
- N-API bridge has zero async patterns — all functions are synchronous
- The addon stores devices in a global `RazerDevices devices` struct

### Required IOKit Pattern for Interrupt Reads

To read from an interrupt endpoint, IOKit requires:
1. Open the USB device
2. Find and open the specific interface (interface 1)
3. Get the pipe reference for the interrupt IN endpoint
4. Set up an async event source with `CreateInterfaceAsyncEventSource()`
5. Add it to a CFRunLoop
6. Call `ReadPipeAsync()` with a callback
7. Run the loop on a background thread

---

## Task 1: C Driver — Interrupt Listener Infrastructure

**Files:**
- Create: `librazermacos/src/include/razerinterrupt.h`
- Create: `librazermacos/src/lib/razerinterrupt.c`
- Modify: `binding.gyp` (add new source file)

### Step 1: Create the interrupt header

Create `librazermacos/src/include/razerinterrupt.h`:

```c
#ifndef DRIVER_RAZERINTERRUPT_H_
#define DRIVER_RAZERINTERRUPT_H_

#include <IOKit/usb/IOUSBLib.h>
#include <IOKit/IOCFPlugIn.h>
#include <CoreFoundation/CFRunLoop.h>
#include <pthread.h>

// Callback type for panel change events
// panel_id: 0x00=removed, 0x01=2-btn, 0x03=12-btn, 0x04=6-btn
typedef void (*panel_change_callback_t)(UInt16 product_id, unsigned char panel_id, void *context);

// Opaque handle for an active interrupt listener
typedef struct razer_interrupt_listener {
    IOUSBDeviceInterface **usb_device;
    IOUSBInterfaceInterface **usb_interface;
    CFRunLoopRef run_loop;
    CFRunLoopSourceRef event_source;
    pthread_t thread;
    int running;
    UInt16 product_id;
    panel_change_callback_t callback;
    void *callback_context;
    unsigned char read_buffer[16];
} razer_interrupt_listener;

// Start listening for interrupt events on the given USB device.
// Finds interface 1 (keyboard), opens it, sets up async reads on the interrupt endpoint.
// Calls callback on a background thread when a panel change report arrives.
// Returns NULL on failure.
razer_interrupt_listener *razer_start_interrupt_listener(
    IOUSBDeviceInterface **usb_dev,
    UInt16 product_id,
    panel_change_callback_t callback,
    void *context);

// Stop and clean up the interrupt listener.
void razer_stop_interrupt_listener(razer_interrupt_listener *listener);

#endif
```

### Step 2: Create the interrupt implementation

Create `librazermacos/src/lib/razerinterrupt.c`:

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "razerinterrupt.h"

// Async read completion callback — called by IOKit when data arrives on the interrupt pipe.
static void interrupt_read_callback(void *refCon, IOReturn result, void *arg0)
{
    razer_interrupt_listener *listener = (razer_interrupt_listener *)refCon;

    if (result != kIOReturnSuccess || !listener->running) {
        return;
    }

    // Check for panel change report: first two bytes are 0x05, 0x0e
    if (listener->read_buffer[0] == 0x05 && listener->read_buffer[1] == 0x0e) {
        unsigned char panel_id = listener->read_buffer[2];
        if (listener->callback) {
            listener->callback(listener->product_id, panel_id, listener->callback_context);
        }
    }

    // Re-arm the async read for the next event
    if (listener->running && listener->usb_interface) {
        UInt32 buf_size = sizeof(listener->read_buffer);
        (*listener->usb_interface)->ReadPipeAsync(
            listener->usb_interface,
            1, // pipe reference (first IN pipe on this interface)
            listener->read_buffer,
            buf_size,
            interrupt_read_callback,
            listener);
    }
}

// Background thread function — runs the CFRunLoop for async I/O.
static void *interrupt_thread_func(void *arg)
{
    razer_interrupt_listener *listener = (razer_interrupt_listener *)arg;
    listener->run_loop = CFRunLoopGetCurrent();

    CFRunLoopAddSource(listener->run_loop, listener->event_source, kCFRunLoopDefaultMode);

    // Kick off the first async read
    UInt32 buf_size = sizeof(listener->read_buffer);
    IOReturn kr = (*listener->usb_interface)->ReadPipeAsync(
        listener->usb_interface,
        1, // pipe reference
        listener->read_buffer,
        buf_size,
        interrupt_read_callback,
        listener);

    if (kr != kIOReturnSuccess) {
        printf("razer_interrupt: ReadPipeAsync failed: %08x\n", kr);
        return NULL;
    }

    // Run the loop until stopped
    while (listener->running) {
        CFRunLoopRunInMode(kCFRunLoopDefaultMode, 1.0, false);
    }

    CFRunLoopRemoveSource(listener->run_loop, listener->event_source, kCFRunLoopDefaultMode);
    return NULL;
}

// Find and open interface 1 (keyboard HID interface with endpoint 0x82).
static IOUSBInterfaceInterface **find_and_open_interface(IOUSBDeviceInterface **usb_dev, int interface_num)
{
    IOUSBFindInterfaceRequest request;
    request.bInterfaceClass = kIOUSBFindInterfaceDontCare;
    request.bInterfaceSubClass = kIOUSBFindInterfaceDontCare;
    request.bInterfaceProtocol = kIOUSBFindInterfaceDontCare;
    request.bAlternateSetting = kIOUSBFindInterfaceDontCare;

    io_iterator_t iter;
    kern_return_t kr = (*usb_dev)->CreateInterfaceIterator(usb_dev, &request, &iter);
    if (kr != kIOReturnSuccess) {
        printf("razer_interrupt: CreateInterfaceIterator failed: %08x\n", kr);
        return NULL;
    }

    io_service_t usb_iface;
    int current_iface = 0;
    IOUSBInterfaceInterface **iface = NULL;

    while ((usb_iface = IOIteratorNext(iter))) {
        if (current_iface == interface_num) {
            IOCFPlugInInterface **plugInInterface = NULL;
            SInt32 score;

            kr = IOCreatePlugInInterfaceForService(
                usb_iface, kIOUSBInterfaceUserClientTypeID,
                kIOCFPlugInInterfaceID, &plugInInterface, &score);

            IOObjectRelease(usb_iface);
            if (kr != kIOReturnSuccess || !plugInInterface) {
                IOObjectRelease(iter);
                return NULL;
            }

            HRESULT hr = (*plugInInterface)->QueryInterface(
                plugInInterface,
                CFUUIDGetUUIDBytes(kIOUSBInterfaceInterfaceID197),
                (LPVOID *)&iface);
            (*plugInInterface)->Release(plugInInterface);

            if (hr || !iface) {
                IOObjectRelease(iter);
                return NULL;
            }

            kr = (*iface)->USBInterfaceOpen(iface);
            if (kr != kIOReturnSuccess) {
                printf("razer_interrupt: USBInterfaceOpen failed: %08x\n", kr);
                (*iface)->Release(iface);
                IOObjectRelease(iter);
                return NULL;
            }

            IOObjectRelease(iter);
            return iface;
        }

        IOObjectRelease(usb_iface);
        current_iface++;
    }

    IOObjectRelease(iter);
    printf("razer_interrupt: Interface %d not found\n", interface_num);
    return NULL;
}

razer_interrupt_listener *razer_start_interrupt_listener(
    IOUSBDeviceInterface **usb_dev,
    UInt16 product_id,
    panel_change_callback_t callback,
    void *context)
{
    if (!usb_dev || !callback) return NULL;

    // Only start for Naga V2 Pro devices
    if (product_id != 0x00A7 && product_id != 0x00A8) {
        return NULL;
    }

    razer_interrupt_listener *listener = calloc(1, sizeof(razer_interrupt_listener));
    if (!listener) return NULL;

    listener->usb_device = usb_dev;
    listener->product_id = product_id;
    listener->callback = callback;
    listener->callback_context = context;
    listener->running = 1;

    // Open interface 1 (keyboard interface with panel change events)
    listener->usb_interface = find_and_open_interface(usb_dev, 1);
    if (!listener->usb_interface) {
        printf("razer_interrupt: Failed to open interface 1\n");
        free(listener);
        return NULL;
    }

    // Create async event source
    IOReturn kr = (*listener->usb_interface)->CreateInterfaceAsyncEventSource(
        listener->usb_interface, &listener->event_source);
    if (kr != kIOReturnSuccess) {
        printf("razer_interrupt: CreateInterfaceAsyncEventSource failed: %08x\n", kr);
        (*listener->usb_interface)->USBInterfaceClose(listener->usb_interface);
        (*listener->usb_interface)->Release(listener->usb_interface);
        free(listener);
        return NULL;
    }

    // Start background thread
    if (pthread_create(&listener->thread, NULL, interrupt_thread_func, listener) != 0) {
        printf("razer_interrupt: pthread_create failed\n");
        (*listener->usb_interface)->USBInterfaceClose(listener->usb_interface);
        (*listener->usb_interface)->Release(listener->usb_interface);
        free(listener);
        return NULL;
    }

    printf("razer_interrupt: Listening for panel changes on PID 0x%04X\n", product_id);
    return listener;
}

void razer_stop_interrupt_listener(razer_interrupt_listener *listener)
{
    if (!listener) return;

    listener->running = 0;

    // Stop the run loop to unblock the thread
    if (listener->run_loop) {
        CFRunLoopStop(listener->run_loop);
    }

    pthread_join(listener->thread, NULL);

    if (listener->usb_interface) {
        (*listener->usb_interface)->AbortPipe(listener->usb_interface, 1);
        (*listener->usb_interface)->USBInterfaceClose(listener->usb_interface);
        (*listener->usb_interface)->Release(listener->usb_interface);
    }

    free(listener);
    printf("razer_interrupt: Listener stopped\n");
}
```

### Step 3: Add new source file to binding.gyp

The `binding.gyp` uses `<!@(ls -1 librazermacos/src/lib/*.c)` glob pattern, so the new `.c` file will be automatically included. No change needed.

### Step 4: Rebuild to verify compilation

Run: `source ~/.nvm/nvm.sh && nvm use 16 && yarn rebuild`
Expected: Build succeeds with no errors related to razerinterrupt.c

### Step 5: Commit

```bash
git add librazermacos/src/include/razerinterrupt.h librazermacos/src/lib/razerinterrupt.c
git commit -m "feat: add IOKit interrupt listener for panel change detection"
```

---

## Task 2: N-API Bridge — ThreadSafeFunction for Async Events

**Files:**
- Modify: `src/driver/addon.cc`

### Step 1: Add interrupt listener integration to addon.cc

Add the following at the top of `addon.cc` (after existing includes around line 10):

```cpp
#include "razerinterrupt.h"

// Thread-safe function for panel change callbacks from C thread to JS
static Napi::ThreadSafeFunction panelChangeTsfn;
static razer_interrupt_listener **activeListeners = nullptr;
static int activeListenerCount = 0;
```

Add the C callback that bridges to N-API (before existing functions, around line 20):

```cpp
// Called from the C interrupt thread — must use ThreadSafeFunction to cross into JS
static void on_panel_change(UInt16 product_id, unsigned char panel_id, void *context) {
    if (panelChangeTsfn) {
        // Pack product_id and panel_id into a single uint32
        uint32_t data = ((uint32_t)product_id << 8) | panel_id;
        uint32_t *heapData = new uint32_t(data);
        panelChangeTsfn.NonBlockingCall(heapData, [](Napi::Env env, Napi::Function jsCallback, uint32_t *data) {
            uint32_t packed = *data;
            uint16_t productId = (packed >> 8) & 0xFFFF;
            uint8_t panelId = packed & 0xFF;
            jsCallback.Call({
                Napi::Number::New(env, productId),
                Napi::Number::New(env, panelId)
            });
            delete data;
        });
    }
}
```

Add the start/stop listener functions (before the `Init` function):

```cpp
void StartInterruptListeners(const Napi::CallbackInfo &info) {
    Napi::Env env = info.Env();

    // Clean up any existing listeners
    if (activeListeners) {
        for (int i = 0; i < activeListenerCount; i++) {
            razer_stop_interrupt_listener(activeListeners[i]);
        }
        free(activeListeners);
        activeListeners = nullptr;
        activeListenerCount = 0;
    }

    if (!info[0].IsFunction()) {
        Napi::TypeError::New(env, "Callback function required").ThrowAsJavaScriptException();
        return;
    }

    // Create thread-safe function
    panelChangeTsfn = Napi::ThreadSafeFunction::New(
        env,
        info[0].As<Napi::Function>(),
        "panelChangeCallback",
        0,  // unlimited queue
        1   // initial thread count
    );

    // Start a listener for each open device that supports it
    activeListeners = (razer_interrupt_listener **)malloc(devices.size * sizeof(razer_interrupt_listener *));
    activeListenerCount = 0;

    for (int i = 0; i < devices.size; i++) {
        razer_interrupt_listener *listener = razer_start_interrupt_listener(
            devices.devices[i].usbDevice,
            devices.devices[i].productId,
            on_panel_change,
            nullptr);
        if (listener) {
            activeListeners[activeListenerCount++] = listener;
        }
    }
}

void StopInterruptListeners(const Napi::CallbackInfo &info) {
    if (activeListeners) {
        for (int i = 0; i < activeListenerCount; i++) {
            razer_stop_interrupt_listener(activeListeners[i]);
        }
        free(activeListeners);
        activeListeners = nullptr;
        activeListenerCount = 0;
    }
    if (panelChangeTsfn) {
        panelChangeTsfn.Release();
        panelChangeTsfn = Napi::ThreadSafeFunction();
    }
}
```

Add exports in the `Init` function (near the other exports, around line 985):

```cpp
exports.Set("startInterruptListeners", Napi::Function::New(env, StartInterruptListeners));
exports.Set("stopInterruptListeners", Napi::Function::New(env, StopInterruptListeners));
```

### Step 2: Rebuild to verify compilation

Run: `source ~/.nvm/nvm.sh && nvm use 16 && yarn rebuild`
Expected: Build succeeds

### Step 3: Commit

```bash
git add src/driver/addon.cc
git commit -m "feat: add N-API ThreadSafeFunction bridge for interrupt events"
```

---

## Task 3: Main Process — Start Listeners and Forward Events via IPC

**Files:**
- Modify: `src/main/device/razerdevicemouse.js`
- Modify: `src/main/application.js`

### Step 1: Start interrupt listeners after device initialization

In `src/main/application.js`, after the device manager refresh in the `createApplication()` or wherever devices are initialized, add interrupt listener startup.

Find the section where `razerApplication` is set up. Add to the `registerIpcListeners()` method (after the existing button mapping IPC handlers around line 189):

```javascript
    // Start interrupt listeners for panel change detection
    this.razerApplication.startInterruptListeners();
```

In `src/main/razerapplication.js`, add a method:

```javascript
  startInterruptListeners() {
    const addon = this.deviceManager.addon;
    addon.startInterruptListeners((productId, panelId) => {
      // Find the device by product ID and update its panel type
      const device = this.deviceManager.activeRazerDevices.find(
        d => d.productId === productId
      );
      if (device) {
        device.panelType = panelId || null;
      }
      // Broadcast to renderer
      if (this.application && this.application.browserWindow) {
        this.application.browserWindow.webContents.send('panel-type-changed', {
          productId,
          panelId,
        });
      }
    });
  }

  stopInterruptListeners() {
    const addon = this.deviceManager.addon;
    addon.stopInterruptListeners();
  }
```

### Step 2: Wire up startup and cleanup

In `src/main/application.js`, in `createApplication()` after `await this.razerApplication.refresh()`:

```javascript
this.razerApplication.startInterruptListeners();
```

In the app quit handler or `closeAllDevices`, call:

```javascript
this.razerApplication.stopInterruptListeners();
```

### Step 3: Rebuild and test

Run: `source ~/.nvm/nvm.sh && nvm use 16 && yarn rebuild && yarn dev`
Expected: Console prints "razer_interrupt: Listening for panel changes on PID 0x00A8"

### Step 4: Commit

```bash
git add src/main/application.js src/main/razerapplication.js
git commit -m "feat: start interrupt listeners and forward panel changes via IPC"
```

---

## Task 4: Renderer — Listen for Panel Change Events

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx`

### Step 1: Subscribe to panel-type-changed IPC event

In `componentDidMount()`, add a listener for the push-based panel change event:

```javascript
ipcRenderer.on('panel-type-changed', this.handlePanelChanged);
```

Add the handler:

```javascript
  handlePanelChanged(event, data) {
    // Only react if this event is for our device
    if (data.productId !== this.deviceSelected.productId) return;
    const newPanel = data.panelId || null;
    this.setState({ panelType: newPanel, mappings: [], editingButton: null }, () => {
      this.requestMappings();
    });
  }
```

Bind in constructor:
```javascript
this.handlePanelChanged = this.handlePanelChanged.bind(this);
```

Clean up in `componentWillUnmount()`:
```javascript
ipcRenderer.removeListener('panel-type-changed', this.handlePanelChanged);
```

### Step 2: Test end-to-end

Run: `yarn dev`
1. Open the mouse settings window
2. With the 12-button panel installed, verify "12-Button Side Panel" shows
3. Swap to the 2-button panel
4. Verify the UI updates automatically within ~1 second to "2-Button Side Panel"
5. Swap back — verify it updates again

### Step 3: Commit

```bash
git add src/renderer/sections/sectionsettingbuttonmapping.jsx
git commit -m "feat: auto-update UI on panel change via interrupt events"
```

---

## Task 5: Cleanup and Edge Cases

**Files:**
- Modify: `src/renderer/sections/sectionsettingbuttonmapping.jsx` (remove Refresh button)
- Modify: `src/main/application.js` (remove `get-side-panel-type` IPC handler if no longer needed, or keep as fallback)

### Step 1: Keep the Refresh button as fallback but make it secondary

The Refresh button is still useful if the interrupt listener fails to start (e.g., interface already claimed by another driver). Keep it but make it less prominent — only show it next to "No side panel detected" as a fallback.

### Step 2: Handle listener cleanup on device disconnect

In `src/main/razerapplication.js`, ensure `stopInterruptListeners()` is called before device re-enumeration in the refresh cycle to avoid stale listeners.

### Step 3: Final commit

```bash
git add -u
git commit -m "feat: complete interrupt-based panel detection with fallback"
```
