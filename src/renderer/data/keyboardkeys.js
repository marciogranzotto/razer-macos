// Complete HID Keyboard/Keypad page (0x07) key definitions.
// Each entry: { value: HID usage code, label: display string, category: string, code: KeyboardEvent.code string }
// The `code` field enables the keystroke recorder to look up HID values from DOM events.

export const KEYBOARD_KEYS = [
  // Letters
  { value: 0x04, label: 'A', category: 'Letters', code: 'KeyA' },
  { value: 0x05, label: 'B', category: 'Letters', code: 'KeyB' },
  { value: 0x06, label: 'C', category: 'Letters', code: 'KeyC' },
  { value: 0x07, label: 'D', category: 'Letters', code: 'KeyD' },
  { value: 0x08, label: 'E', category: 'Letters', code: 'KeyE' },
  { value: 0x09, label: 'F', category: 'Letters', code: 'KeyF' },
  { value: 0x0a, label: 'G', category: 'Letters', code: 'KeyG' },
  { value: 0x0b, label: 'H', category: 'Letters', code: 'KeyH' },
  { value: 0x0c, label: 'I', category: 'Letters', code: 'KeyI' },
  { value: 0x0d, label: 'J', category: 'Letters', code: 'KeyJ' },
  { value: 0x0e, label: 'K', category: 'Letters', code: 'KeyK' },
  { value: 0x0f, label: 'L', category: 'Letters', code: 'KeyL' },
  { value: 0x10, label: 'M', category: 'Letters', code: 'KeyM' },
  { value: 0x11, label: 'N', category: 'Letters', code: 'KeyN' },
  { value: 0x12, label: 'O', category: 'Letters', code: 'KeyO' },
  { value: 0x13, label: 'P', category: 'Letters', code: 'KeyP' },
  { value: 0x14, label: 'Q', category: 'Letters', code: 'KeyQ' },
  { value: 0x15, label: 'R', category: 'Letters', code: 'KeyR' },
  { value: 0x16, label: 'S', category: 'Letters', code: 'KeyS' },
  { value: 0x17, label: 'T', category: 'Letters', code: 'KeyT' },
  { value: 0x18, label: 'U', category: 'Letters', code: 'KeyU' },
  { value: 0x19, label: 'V', category: 'Letters', code: 'KeyV' },
  { value: 0x1a, label: 'W', category: 'Letters', code: 'KeyW' },
  { value: 0x1b, label: 'X', category: 'Letters', code: 'KeyX' },
  { value: 0x1c, label: 'Y', category: 'Letters', code: 'KeyY' },
  { value: 0x1d, label: 'Z', category: 'Letters', code: 'KeyZ' },

  // Numbers
  { value: 0x1e, label: '1', category: 'Numbers', code: 'Digit1' },
  { value: 0x1f, label: '2', category: 'Numbers', code: 'Digit2' },
  { value: 0x20, label: '3', category: 'Numbers', code: 'Digit3' },
  { value: 0x21, label: '4', category: 'Numbers', code: 'Digit4' },
  { value: 0x22, label: '5', category: 'Numbers', code: 'Digit5' },
  { value: 0x23, label: '6', category: 'Numbers', code: 'Digit6' },
  { value: 0x24, label: '7', category: 'Numbers', code: 'Digit7' },
  { value: 0x25, label: '8', category: 'Numbers', code: 'Digit8' },
  { value: 0x26, label: '9', category: 'Numbers', code: 'Digit9' },
  { value: 0x27, label: '0', category: 'Numbers', code: 'Digit0' },

  // System
  { value: 0x28, label: 'Enter', category: 'System', code: 'Enter' },
  { value: 0x29, label: 'Escape', category: 'System', code: 'Escape' },
  { value: 0x2a, label: 'Backspace', category: 'System', code: 'Backspace' },
  { value: 0x2b, label: 'Tab', category: 'System', code: 'Tab' },
  { value: 0x2c, label: 'Space', category: 'System', code: 'Space' },
  { value: 0x39, label: 'Caps Lock', category: 'System', code: 'CapsLock' },
  { value: 0x46, label: 'Print Screen', category: 'System', code: 'PrintScreen' },
  { value: 0x47, label: 'Scroll Lock', category: 'System', code: 'ScrollLock' },
  { value: 0x48, label: 'Pause', category: 'System', code: 'Pause' },
  { value: 0x65, label: 'Context Menu', category: 'System', code: 'ContextMenu' },

  // Punctuation
  { value: 0x2d, label: '-', category: 'Punctuation', code: 'Minus' },
  { value: 0x2e, label: '=', category: 'Punctuation', code: 'Equal' },
  { value: 0x2f, label: '[', category: 'Punctuation', code: 'BracketLeft' },
  { value: 0x30, label: ']', category: 'Punctuation', code: 'BracketRight' },
  { value: 0x31, label: '\\', category: 'Punctuation', code: 'Backslash' },
  { value: 0x33, label: ';', category: 'Punctuation', code: 'Semicolon' },
  { value: 0x34, label: "'", category: 'Punctuation', code: 'Quote' },
  { value: 0x35, label: '`', category: 'Punctuation', code: 'Backquote' },
  { value: 0x36, label: ',', category: 'Punctuation', code: 'Comma' },
  { value: 0x37, label: '.', category: 'Punctuation', code: 'Period' },
  { value: 0x38, label: '/', category: 'Punctuation', code: 'Slash' },

  // Navigation
  { value: 0x49, label: 'Insert', category: 'Navigation', code: 'Insert' },
  { value: 0x4a, label: 'Home', category: 'Navigation', code: 'Home' },
  { value: 0x4b, label: 'Page Up', category: 'Navigation', code: 'PageUp' },
  { value: 0x4c, label: 'Delete', category: 'Navigation', code: 'Delete' },
  { value: 0x4d, label: 'End', category: 'Navigation', code: 'End' },
  { value: 0x4e, label: 'Page Down', category: 'Navigation', code: 'PageDown' },
  { value: 0x4f, label: 'Right Arrow', category: 'Navigation', code: 'ArrowRight' },
  { value: 0x50, label: 'Left Arrow', category: 'Navigation', code: 'ArrowLeft' },
  { value: 0x51, label: 'Down Arrow', category: 'Navigation', code: 'ArrowDown' },
  { value: 0x52, label: 'Up Arrow', category: 'Navigation', code: 'ArrowUp' },

  // Function Keys
  { value: 0x3a, label: 'F1', category: 'Function', code: 'F1' },
  { value: 0x3b, label: 'F2', category: 'Function', code: 'F2' },
  { value: 0x3c, label: 'F3', category: 'Function', code: 'F3' },
  { value: 0x3d, label: 'F4', category: 'Function', code: 'F4' },
  { value: 0x3e, label: 'F5', category: 'Function', code: 'F5' },
  { value: 0x3f, label: 'F6', category: 'Function', code: 'F6' },
  { value: 0x40, label: 'F7', category: 'Function', code: 'F7' },
  { value: 0x41, label: 'F8', category: 'Function', code: 'F8' },
  { value: 0x42, label: 'F9', category: 'Function', code: 'F9' },
  { value: 0x43, label: 'F10', category: 'Function', code: 'F10' },
  { value: 0x44, label: 'F11', category: 'Function', code: 'F11' },
  { value: 0x45, label: 'F12', category: 'Function', code: 'F12' },
  { value: 0x68, label: 'F13', category: 'Function', code: 'F13' },
  { value: 0x69, label: 'F14', category: 'Function', code: 'F14' },
  { value: 0x6a, label: 'F15', category: 'Function', code: 'F15' },
  { value: 0x6b, label: 'F16', category: 'Function', code: 'F16' },
  { value: 0x6c, label: 'F17', category: 'Function', code: 'F17' },
  { value: 0x6d, label: 'F18', category: 'Function', code: 'F18' },
  { value: 0x6e, label: 'F19', category: 'Function', code: 'F19' },
  { value: 0x6f, label: 'F20', category: 'Function', code: 'F20' },
  { value: 0x70, label: 'F21', category: 'Function', code: 'F21' },
  { value: 0x71, label: 'F22', category: 'Function', code: 'F22' },
  { value: 0x72, label: 'F23', category: 'Function', code: 'F23' },
  { value: 0x73, label: 'F24', category: 'Function', code: 'F24' },

  // Keypad
  { value: 0x53, label: 'Num Lock', category: 'Keypad', code: 'NumLock' },
  { value: 0x54, label: 'Numpad /', category: 'Keypad', code: 'NumpadDivide' },
  { value: 0x55, label: 'Numpad *', category: 'Keypad', code: 'NumpadMultiply' },
  { value: 0x56, label: 'Numpad -', category: 'Keypad', code: 'NumpadSubtract' },
  { value: 0x57, label: 'Numpad +', category: 'Keypad', code: 'NumpadAdd' },
  { value: 0x58, label: 'Numpad Enter', category: 'Keypad', code: 'NumpadEnter' },
  { value: 0x59, label: 'Numpad 1', category: 'Keypad', code: 'Numpad1' },
  { value: 0x5a, label: 'Numpad 2', category: 'Keypad', code: 'Numpad2' },
  { value: 0x5b, label: 'Numpad 3', category: 'Keypad', code: 'Numpad3' },
  { value: 0x5c, label: 'Numpad 4', category: 'Keypad', code: 'Numpad4' },
  { value: 0x5d, label: 'Numpad 5', category: 'Keypad', code: 'Numpad5' },
  { value: 0x5e, label: 'Numpad 6', category: 'Keypad', code: 'Numpad6' },
  { value: 0x5f, label: 'Numpad 7', category: 'Keypad', code: 'Numpad7' },
  { value: 0x60, label: 'Numpad 8', category: 'Keypad', code: 'Numpad8' },
  { value: 0x61, label: 'Numpad 9', category: 'Keypad', code: 'Numpad9' },
  { value: 0x62, label: 'Numpad 0', category: 'Keypad', code: 'Numpad0' },
  { value: 0x63, label: 'Numpad .', category: 'Keypad', code: 'NumpadDecimal' },

  // Modifiers (as standalone keys)
  { value: 0xe0, label: 'Left Ctrl', category: 'Modifiers', code: 'ControlLeft' },
  { value: 0xe1, label: 'Left Shift', category: 'Modifiers', code: 'ShiftLeft' },
  { value: 0xe2, label: 'Left Alt', category: 'Modifiers', code: 'AltLeft' },
  { value: 0xe3, label: 'Left GUI', category: 'Modifiers', code: 'MetaLeft' },
  { value: 0xe4, label: 'Right Ctrl', category: 'Modifiers', code: 'ControlRight' },
  { value: 0xe5, label: 'Right Shift', category: 'Modifiers', code: 'ShiftRight' },
  { value: 0xe6, label: 'Right Alt', category: 'Modifiers', code: 'AltRight' },
  { value: 0xe7, label: 'Right GUI', category: 'Modifiers', code: 'MetaRight' },
];

// Fast lookup: KeyboardEvent.code string -> HID usage byte
// Built from KEYBOARD_KEYS so there's a single source of truth.
export const CODE_TO_HID = Object.fromEntries(
  KEYBOARD_KEYS.filter(k => k.code).map(k => [k.code, k.value])
);

// Set of KeyboardEvent.code values that are modifier keys.
// Used by the recorder to distinguish modifier-only vs combo keypresses.
export const MODIFIER_CODES = new Set([
  'ControlLeft', 'ControlRight',
  'ShiftLeft', 'ShiftRight',
  'AltLeft', 'AltRight',
  'MetaLeft', 'MetaRight',
]);

// Ordered list of unique categories for <optgroup> rendering.
export const KEY_CATEGORIES = [
  'Letters', 'Numbers', 'System', 'Punctuation',
  'Navigation', 'Function', 'Keypad', 'Modifiers',
];
