-- Razer Naga V2 Pro protocol dissector for USBPcap / Wireshark
-- Based on openrazer's razer.lua by Terri Cain, extended with deep
-- decoding of button-mapping commands per the Naga V2 Pro protocol spec.
--
-- Install: copy to ~/.wireshark/plugins/ or load with
--   wireshark -X lua_script:razer_usbpcap.lua

razer_proto = Proto("razer", "Razer Protocol")

-- ── Lookup tables ──────────────────────────────────────────────────

local req_types = {
    [0x00] = "REQUEST",
    [0x02] = "RESPONSE_BUSY",
    [0x03] = "RESPONSE_OK",
    [0x04] = "RESPONSE_FAIL",
    [0x05] = "RESPONSE_TIMEOUT",
}

local cmd_class_names = {
    [0x00] = "General",
    [0x01] = "Device Mode",
    [0x02] = "Button Mapping",
    [0x03] = "Lighting/LED",
    [0x04] = "Keyboard Layout",
    [0x05] = "Mouse Config",
    [0x06] = "Keypad/Macro",
    [0x07] = "Custom Effects",
    [0x08] = "Profile",
    [0x09] = "DPI",
    [0x0b] = "Wireless/Dongle",
    [0x0d] = "Extended Btn Map",
    [0x0f] = "LED Matrix / Profile",
    [0x15] = "Extended Config",
}

local cmd_id_names = {
    -- General (0x00)
    ["00:82"] = "Get Device Mode",
    ["00:85"] = "Get Serial",
    ["00:b9"] = "Get FW Version",
    -- Button Mapping (0x02)
    ["02:0c"] = "Set Button Mapping",
    ["02:8c"] = "Get Button Mapping",
    -- Keypad / Macro (0x06)
    ["06:08"] = "Macro Init",
    ["06:0c"] = "Macro Data Upload",
    ["06:8e"] = "Macro Clear",
    -- Custom Effects (0x07)
    ["07:80"] = "FX Read",
    ["07:84"] = "FX Config",
    -- LED Matrix (0x0f)
    ["0f:02"] = "Profile Switch",
    ["0f:03"] = "LED Matrix Color",
    ["0f:04"] = "Profile Config",
}

local action_type_names = {
    [0x00] = "Disabled / Macro Queue",
    [0x01] = "Mouse Button",
    [0x02] = "Keyboard Key",
    [0x03] = "Macro (Play Once)",
    [0x06] = "Sensitivity Clutch",
    [0x0a] = "Multimedia Key",
    [0x0c] = "Hypershift Modifier",
    [0x12] = "Scroll Wheel Control",
}

local layer_names = {
    [0x00] = "Normal",
    [0x01] = "Hypershift",
}

local mouse_btn_names = {
    [0x01] = "Left Click",
    [0x02] = "Right Click",
    [0x03] = "Middle Click",
    [0x04] = "Back (Button 4)",
    [0x05] = "Forward (Button 5)",
}

local button_id_names = {
    -- Standard mouse buttons
    [0x01] = "Left Click",
    [0x02] = "Right Click",
    [0x03] = "Middle Click",
    [0x04] = "Mouse Back",
    [0x05] = "Mouse Forward",
    -- 12-button side panel
    [0x40] = "12-Panel Btn 1",
    [0x41] = "12-Panel Btn 2",
    [0x42] = "12-Panel Btn 3",
    [0x43] = "12-Panel Btn 4",
    [0x44] = "12-Panel Btn 5",
    [0x45] = "12-Panel Btn 6",
    [0x46] = "12-Panel Btn 7",
    [0x47] = "12-Panel Btn 8",
    [0x48] = "12-Panel Btn 9",
    [0x49] = "12-Panel Btn 10",
    [0x4a] = "12-Panel Btn 11",
    [0x4b] = "12-Panel Btn 12",
    -- 6-button side panel
    [0x50] = "6-Panel Btn 1",
    [0x51] = "6-Panel Btn 2",
    [0x52] = "6-Panel Btn 3",
    [0x53] = "6-Panel Btn 4",
    [0x54] = "6-Panel Btn 5",
    [0x55] = "6-Panel Btn 6",
}

local consumer_usage_names = {
    [0x00b5] = "Next Track",
    [0x00b6] = "Previous Track",
    [0x00cd] = "Play/Pause",
    [0x00e2] = "Mute",
    [0x00e9] = "Volume Up",
    [0x00ea] = "Volume Down",
}

local scroll_action_names = {
    [0x04] = "Cycle Up Scroll Stages",
}

local macro_play_mode_names = {
    [0x00] = "Queue / Toggle",
    [0x01] = "Play Once",
}

-- HID keyboard usage codes (common keys)
local hid_key_names = {
    [0x04] = "a", [0x05] = "b", [0x06] = "c", [0x07] = "d",
    [0x08] = "e", [0x09] = "f", [0x0a] = "g", [0x0b] = "h",
    [0x0c] = "i", [0x0d] = "j", [0x0e] = "k", [0x0f] = "l",
    [0x10] = "m", [0x11] = "n", [0x12] = "o", [0x13] = "p",
    [0x14] = "q", [0x15] = "r", [0x16] = "s", [0x17] = "t",
    [0x18] = "u", [0x19] = "v", [0x1a] = "w", [0x1b] = "x",
    [0x1c] = "y", [0x1d] = "z",
    [0x1e] = "1", [0x1f] = "2", [0x20] = "3", [0x21] = "4",
    [0x22] = "5", [0x23] = "6", [0x24] = "7", [0x25] = "8",
    [0x26] = "9", [0x27] = "0",
    [0x28] = "Enter", [0x29] = "Escape", [0x2a] = "Backspace",
    [0x2b] = "Tab", [0x2c] = "Space",
    [0x2d] = "-", [0x2e] = "=", [0x2f] = "[", [0x30] = "]",
    [0x31] = "\\", [0x33] = ";", [0x34] = "'", [0x35] = "`",
    [0x36] = ",", [0x37] = ".", [0x38] = "/",
    [0x39] = "CapsLock",
    [0x3a] = "F1",  [0x3b] = "F2",  [0x3c] = "F3",  [0x3d] = "F4",
    [0x3e] = "F5",  [0x3f] = "F6",  [0x40] = "F7",  [0x41] = "F8",
    [0x42] = "F9",  [0x43] = "F10", [0x44] = "F11", [0x45] = "F12",
    [0x46] = "PrintScreen", [0x47] = "ScrollLock", [0x48] = "Pause",
    [0x49] = "Insert", [0x4a] = "Home", [0x4b] = "PageUp",
    [0x4c] = "Delete", [0x4d] = "End",  [0x4e] = "PageDown",
    [0x4f] = "Right",  [0x50] = "Left", [0x51] = "Down", [0x52] = "Up",
}

-- ── Proto fields ───────────────────────────────────────────────────

local f = razer_proto.fields

-- Frame header
f.f_status           = ProtoField.uint8 ("razer.status",          "Status",            base.HEX, req_types)
f.f_id               = ProtoField.uint8 ("razer.id",              "Transaction ID",    base.HEX)
f.f_remaining        = ProtoField.uint16("razer.remaining",       "Remaining Packets", base.DEC)
f.f_proto_type       = ProtoField.uint8 ("razer.proto_type",      "Protocol Type",     base.HEX)
f.f_data_size        = ProtoField.uint8 ("razer.data_size",       "Data Size",         base.DEC)
f.f_cmd_class        = ProtoField.uint8 ("razer.cmd_class",       "Command Class",     base.HEX, cmd_class_names)
f.f_cmd_id           = ProtoField.uint8 ("razer.cmd_id",          "Command ID",        base.HEX)
f.f_params           = ProtoField.bytes ("razer.params",          "Parameters",        base.SPACE)
f.f_crc              = ProtoField.uint8 ("razer.crc",             "CRC",               base.HEX)
f.f_end              = ProtoField.uint8 ("razer.end",             "End Marker",        base.HEX)

-- Button mapping fields
f.f_profile          = ProtoField.uint8 ("razer.btn.profile",     "Profile Slot",      base.DEC)
f.f_button_id        = ProtoField.uint8 ("razer.btn.id",          "Button ID",         base.HEX, button_id_names)
f.f_layer            = ProtoField.uint8 ("razer.btn.layer",       "Layer",             base.HEX, layer_names)
f.f_action_type      = ProtoField.uint8 ("razer.btn.action_type", "Action Type",       base.HEX, action_type_names)
f.f_action_subtype   = ProtoField.uint8 ("razer.btn.sub_type",    "Action Sub-type",   base.HEX)
f.f_action_data      = ProtoField.bytes ("razer.btn.action_data", "Action Data",       base.SPACE)

-- Mouse button action
f.f_mouse_btn        = ProtoField.uint8 ("razer.btn.mouse_btn",   "Mouse Button",      base.HEX, mouse_btn_names)

-- Keyboard action
f.f_kb_modifier      = ProtoField.uint8 ("razer.btn.kb_mod",      "Modifier Mask",     base.HEX)
f.f_kb_keycode       = ProtoField.uint8 ("razer.btn.kb_key",      "HID Keycode",       base.HEX)

-- Multimedia action
f.f_consumer_usage   = ProtoField.uint16("razer.btn.consumer",    "Consumer Usage",    base.HEX, consumer_usage_names)

-- Macro action
f.f_macro_id         = ProtoField.uint16("razer.btn.macro_id",    "Macro ID",          base.HEX)
f.f_macro_play_mode  = ProtoField.uint8 ("razer.btn.macro_mode",  "Play Mode",         base.HEX, macro_play_mode_names)

-- Sensitivity clutch
f.f_clutch_flags     = ProtoField.uint8 ("razer.btn.clutch_flags","Flags",             base.HEX)
f.f_clutch_x_dpi     = ProtoField.uint16("razer.btn.x_dpi",      "X DPI",             base.DEC)
f.f_clutch_y_dpi     = ProtoField.uint16("razer.btn.y_dpi",      "Y DPI",             base.DEC)

-- Scroll wheel
f.f_scroll_action    = ProtoField.uint8 ("razer.btn.scroll_act",  "Scroll Action",     base.HEX, scroll_action_names)

-- Macro upload fields (cmd_class 0x06)
f.f_macro_up_id      = ProtoField.uint16("razer.macro.id",        "Macro ID",          base.HEX)
f.f_macro_up_offset  = ProtoField.uint16("razer.macro.offset",    "Chunk Offset",      base.DEC)
f.f_macro_up_size    = ProtoField.uint8 ("razer.macro.chunk_size","Chunk Size",         base.DEC)
f.f_macro_up_data    = ProtoField.bytes ("razer.macro.data",      "Keystroke Data",    base.SPACE)

-- LED matrix fields (cmd 0x0f:0x03)
f.f_led_row          = ProtoField.uint8 ("razer.led.row",         "Row",               base.DEC)
f.f_led_col          = ProtoField.uint8 ("razer.led.col",         "Column",            base.DEC)
f.f_led_flag         = ProtoField.uint8 ("razer.led.flag",        "Flag",              base.HEX)
f.f_led_color1       = ProtoField.bytes ("razer.led.color1",      "Color 1 (RGB)",     base.SPACE)
f.f_led_color2       = ProtoField.bytes ("razer.led.color2",      "Color 2 (RGB)",     base.SPACE)

-- ── Wireshark field extractors ─────────────────────────────────────

local f_usb_ep_dir  = Field.new("usb.endpoint_address.direction")
local f_data_len    = Field.new("usb.data_len")
local f_urb_type    = Field.new("usb.urb_type")
local f_xfer_type   = Field.new("usb.transfer_type")

-- ── Helper: format modifier bitmask ────────────────────────────────

local function modifier_string(mod)
    if mod == 0 then return "None" end
    local parts = {}
    if bit.band(mod, 0x01) ~= 0 then parts[#parts+1] = "LCtrl"  end
    if bit.band(mod, 0x02) ~= 0 then parts[#parts+1] = "LShift" end
    if bit.band(mod, 0x04) ~= 0 then parts[#parts+1] = "LAlt"   end
    if bit.band(mod, 0x08) ~= 0 then parts[#parts+1] = "LGui"   end
    if bit.band(mod, 0x10) ~= 0 then parts[#parts+1] = "RCtrl"  end
    if bit.band(mod, 0x20) ~= 0 then parts[#parts+1] = "RShift" end
    if bit.band(mod, 0x40) ~= 0 then parts[#parts+1] = "RAlt"   end
    if bit.band(mod, 0x80) ~= 0 then parts[#parts+1] = "RGui"   end
    return table.concat(parts, "+")
end

-- ── Helper: human-readable info column summary ─────────────────────

local function btn_mapping_info(params_offset, buffer)
    local profile   = buffer(params_offset,     1):uint()
    local button_id = buffer(params_offset + 1, 1):uint()
    local layer     = buffer(params_offset + 2, 1):uint()
    local act_type  = buffer(params_offset + 3, 1):uint()

    local btn_name   = button_id_names[button_id] or string.format("0x%02x", button_id)
    local layer_name = layer_names[layer] or string.format("0x%02x", layer)
    local act_name   = action_type_names[act_type] or string.format("0x%02x", act_type)

    local detail = ""

    if act_type == 0x01 then -- Mouse
        local mb = buffer(params_offset + 5, 1):uint()
        detail = mouse_btn_names[mb] or string.format("btn 0x%02x", mb)
    elseif act_type == 0x02 then -- Keyboard
        local mod = buffer(params_offset + 5, 1):uint()
        local kc  = buffer(params_offset + 6, 1):uint()
        local key = hid_key_names[kc] or string.format("0x%02x", kc)
        if mod ~= 0 then
            detail = modifier_string(mod) .. "+" .. key
        else
            detail = key
        end
    elseif act_type == 0x0a then -- Multimedia
        local usage = buffer(params_offset + 5, 2):uint()
        detail = consumer_usage_names[usage] or string.format("0x%04x", usage)
    elseif act_type == 0x03 then -- Macro play-once
        local mid = buffer(params_offset + 5, 2):uint()
        detail = string.format("Macro 0x%04x", mid)
    elseif act_type == 0x00 then -- Disabled or macro queue
        local p5 = buffer(params_offset + 5, 1):uint()
        local p6 = buffer(params_offset + 6, 1):uint()
        if p5 == 0 and p6 == 0 then
            detail = "Disabled"
        else
            detail = string.format("Macro Queue 0x%04x", buffer(params_offset + 5, 2):uint())
        end
    elseif act_type == 0x06 then -- Sensitivity
        local xdpi = buffer(params_offset + 6, 2):uint()
        local ydpi = buffer(params_offset + 8, 2):uint()
        detail = string.format("X=%d Y=%d DPI", xdpi, ydpi)
    elseif act_type == 0x0c then -- Hypershift
        detail = "Hypershift"
    elseif act_type == 0x12 then -- Scroll
        local sa = buffer(params_offset + 5, 1):uint()
        detail = scroll_action_names[sa] or string.format("0x%02x", sa)
    end

    return string.format("[%s] %s → %s: %s", layer_name, btn_name, act_name, detail)
end

-- ── Sub-dissector: button mapping (0x02:0x0c / 0x02:0x8c) ─────────

local function dissect_button_mapping(params_buf, subtree)
    local t = subtree:add(razer_proto, params_buf, "Button Mapping")
    local off = 0

    t:add(f.f_profile,     params_buf(off, 1)); off = off + 1
    t:add(f.f_button_id,   params_buf(off, 1)); off = off + 1
    t:add(f.f_layer,       params_buf(off, 1)); off = off + 1

    local act_type = params_buf(off, 1):uint()
    t:add(f.f_action_type, params_buf(off, 1)); off = off + 1
    t:add(f.f_action_subtype, params_buf(off, 1)); off = off + 1

    if act_type == 0x01 then -- Mouse Button
        t:add(f.f_mouse_btn, params_buf(off, 1))

    elseif act_type == 0x02 then -- Keyboard Key
        local mod = params_buf(off, 1):uint()
        local mod_item = t:add(f.f_kb_modifier, params_buf(off, 1))
        mod_item:append_text(" (" .. modifier_string(mod) .. ")")
        off = off + 1
        local kc = params_buf(off, 1):uint()
        local key_item = t:add(f.f_kb_keycode, params_buf(off, 1))
        local key_name = hid_key_names[kc]
        if key_name then key_item:append_text(" (" .. key_name .. ")") end

    elseif act_type == 0x0a then -- Multimedia / Consumer
        t:add(f.f_consumer_usage, params_buf(off, 2))

    elseif act_type == 0x03 then -- Macro (Play Once)
        t:add(f.f_macro_id,        params_buf(off, 2))
        t:add(f.f_macro_play_mode, params_buf(off + 2, 1))

    elseif act_type == 0x00 then -- Disabled / Macro Queue
        local p1 = params_buf(off, 1):uint()
        local p2 = params_buf(off + 1, 1):uint()
        if p1 ~= 0 or p2 ~= 0 then
            t:add(f.f_macro_id, params_buf(off, 2)):append_text(" (Queue Mode)")
        else
            t:add_expert_info(PI_COMMENTS, PI_COMMENT, "Button disabled / default")
        end

    elseif act_type == 0x06 then -- Sensitivity Clutch
        t:add(f.f_clutch_flags, params_buf(off, 1)); off = off + 1
        t:add(f.f_clutch_x_dpi, params_buf(off, 2)); off = off + 2
        t:add(f.f_clutch_y_dpi, params_buf(off, 2))

    elseif act_type == 0x0c then -- Hypershift Modifier
        t:add(f.f_action_data, params_buf(off, 2)):append_text(" (Hypershift toggle)")

    elseif act_type == 0x12 then -- Scroll Wheel Control
        t:add(f.f_scroll_action, params_buf(off, 1))

    else
        t:add(f.f_action_data, params_buf(off, 5))
    end

    return t
end

-- ── Sub-dissector: macro upload (0x06) ─────────────────────────────

local function dissect_macro_upload(cmd_id, num_params, params_buf, subtree)
    if cmd_id == 0x08 then -- Macro Init
        local t = subtree:add(razer_proto, params_buf(0, num_params), "Macro Init")
        t:add(f.f_macro_up_id, params_buf(0, 2))

    elseif cmd_id == 0x0c then -- Macro Data
        local t = subtree:add(razer_proto, params_buf(0, num_params), "Macro Data Upload")
        t:add(f.f_macro_up_id,     params_buf(0, 2))
        -- bytes 2 is 0x00 padding
        t:add(f.f_macro_up_offset, params_buf(3, 2)) -- offset_hi, offset_lo (byte 3-4 approx)
        -- byte 4 is 0x00 padding
        local chunk_size = params_buf(5, 1):uint()
        t:add(f.f_macro_up_size,   params_buf(5, 1))
        if chunk_size > 0 and (6 + chunk_size) <= num_params then
            t:add(f.f_macro_up_data, params_buf(6, chunk_size))
        end

    elseif cmd_id == 0x8e or cmd_id == 0x0e then -- Macro Clear
        local t = subtree:add(razer_proto, params_buf(0, num_params), "Macro Clear")
        t:add(f.f_params, params_buf(0, num_params))
    end
end

-- ── Sub-dissector: LED matrix color (0x0f:0x03) ────────────────────

local function dissect_led_matrix(params_buf, subtree)
    local t = subtree:add(razer_proto, params_buf(0, 11), "LED Matrix Color")
    t:add(f.f_led_row,    params_buf(0, 1))
    t:add(f.f_led_col,    params_buf(1, 1))
    -- bytes 2-3 are 0x00
    t:add(f.f_led_flag,   params_buf(4, 1))
    local r1 = params_buf(5, 1):uint()
    local g1 = params_buf(6, 1):uint()
    local b1 = params_buf(7, 1):uint()
    local c1 = t:add(f.f_led_color1, params_buf(5, 3))
    c1:append_text(string.format(" (#%02x%02x%02x)", r1, g1, b1))
    local r2 = params_buf(8,  1):uint()
    local g2 = params_buf(9,  1):uint()
    local b2 = params_buf(10, 1):uint()
    local c2 = t:add(f.f_led_color2, params_buf(8, 3))
    c2:append_text(string.format(" (#%02x%02x%02x)", r2, g2, b2))
end

-- ── Main dissector ─────────────────────────────────────────────────

local function razer_dissect(buffer, pinfo, tree)
    local data_length = f_data_len()
    local data_direction = f_usb_ep_dir()

    if data_length == nil then return end

    -- USBPcap: 98 = 8 setup + 90 payload, or 90 for response
    local dl = data_length.value
    if dl ~= 90 and dl ~= 98 then return end

    -- Must be a control transfer (type 2)
    local xfer = f_xfer_type()
    if xfer == nil or xfer.value ~= 2 then return end

    -- Locate the 90-byte Razer payload
    local base_off = buffer:len() - 90
    if base_off < 0 then return end

    -- Sanity: end marker should be 0x00
    if buffer(base_off + 89, 1):uint() ~= 0x00 then return end

    pinfo.cols["protocol"] = "Razer"

    local t_razer = tree:add(razer_proto, buffer(base_off, 90))
    local off = base_off

    -- Direction label
    local is_request = (data_direction and data_direction.value == 0)
    local dir_label = is_request and "Request" or "Response"

    -- Header fields
    local status_val = buffer(off, 1):uint()
    t_razer:add(f.f_status,     buffer(off, 1)); off = off + 1
    t_razer:add(f.f_id,         buffer(off, 1)); off = off + 1
    t_razer:add(f.f_remaining,  buffer(off, 2)); off = off + 2
    t_razer:add(f.f_proto_type, buffer(off, 1)); off = off + 1

    local num_params = buffer(off, 1):uint()
    t_razer:add(f.f_data_size,  buffer(off, 1)); off = off + 1

    local cmd_class = buffer(off, 1):uint()
    t_razer:add(f.f_cmd_class,  buffer(off, 1)); off = off + 1

    local cmd_id = buffer(off, 1):uint()
    local cmd_id_item = t_razer:add(f.f_cmd_id, buffer(off, 1))
    off = off + 1

    -- Annotate command ID with friendly name
    local cmd_key = string.format("%02x:%02x", cmd_class, cmd_id)
    local cmd_name = cmd_id_names[cmd_key]
    if cmd_name then
        cmd_id_item:append_text(" (" .. cmd_name .. ")")
    end

    -- Parameters start at off, 80 bytes total
    local params_off = off

    -- Show raw params
    if num_params > 0 and num_params <= 80 then
        t_razer:add(f.f_params, buffer(params_off, num_params))
    end

    -- Deep decode based on command
    local is_btn_map = (cmd_class == 0x02 and (cmd_id == 0x0c or cmd_id == 0x8c) and num_params >= 10)
    local is_macro   = (cmd_class == 0x06 and num_params > 0)
    local is_led     = (cmd_class == 0x0f and cmd_id == 0x03 and num_params >= 11)

    if is_btn_map then
        dissect_button_mapping(buffer(params_off, num_params), t_razer)
    elseif is_macro then
        dissect_macro_upload(cmd_id, num_params, buffer(params_off, num_params), t_razer)
    elseif is_led then
        dissect_led_matrix(buffer(params_off, num_params), t_razer)
    end

    -- Skip to CRC + end
    off = params_off + 80
    t_razer:add(f.f_crc, buffer(off, 1)); off = off + 1
    t_razer:add(f.f_end, buffer(off, 1))

    -- ── Build info column ──────────────────────────────────────────

    local status_label = req_types[status_val] or string.format("0x%02x", status_val)

    local info
    if is_btn_map then
        local rw = (cmd_id == 0x0c) and "SET" or "GET"
        info = string.format("Razer %s %s BtnMap %s",
            dir_label, rw, btn_mapping_info(params_off, buffer))
    elseif cmd_name then
        info = string.format("Razer %s %s", dir_label, cmd_name)
    else
        local cls_name = cmd_class_names[cmd_class] or string.format("0x%02x", cmd_class)
        info = string.format("Razer %s %s cmd 0x%02x", dir_label, cls_name, cmd_id)
    end

    if not is_request and status_val ~= 0x00 then
        info = info .. " [" .. status_label .. "]"
    end

    pinfo.cols["info"] = info
end

-- ── Register as post-dissector ──────────────────────────────────────
-- USBPcap + USBHID claims control transfers before usb.control table
-- entries run, so we use a post-dissector to layer on top.

function razer_proto.dissector(buffer, pinfo, tree)
    razer_dissect(buffer, pinfo, tree)
end

register_postdissector(razer_proto)
