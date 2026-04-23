import { RazerDevice } from './razerdevice';
import { FeatureIdentifier } from '../feature/featureidentifier';

export class RazerDeviceMouse extends RazerDevice {
  constructor(addon, settingsManager, stateManager, razerProperties) {
    super(addon, settingsManager, stateManager, razerProperties);
  }

  async init() {
    if(this.hasFeature(FeatureIdentifier.BATTERY)) {
      this.batteryLevel = this.addon.getBatteryLevel(this.internalId);
      this.chargingStatus = this.addon.getChargingStatus(this.internalId);
    }

    if(this.hasFeature(FeatureIdentifier.MOUSE_DPI)) {
      // On Naga V2 Pro the VARSTORE DPI register is global and doesn't reflect
      // per-profile stage DPI. Populated from hardware after panelType init below.
      this.slotDpi = { 1: null, 2: null, 3: null, 4: null, 5: null };
      this.dpi = this.addon.mouseGetDpi(this.internalId);  // best-effort initial value; overwritten below
    }

    if(this.hasFeature(FeatureIdentifier.POLL_RATE)) {
      this.pollRate = this.addon.mouseGetPollRate(this.internalId);
    }

    const featureMouseBrightness = this.getFeature(FeatureIdentifier.MOUSE_BRIGHTNESS);

    if(typeof featureMouseBrightness !== 'undefined') {
      if(featureMouseBrightness.configuration.enabledMatrix) {
        this.brightness = this.addon.mouseGetBrightness(this.internalId);
      }
      if(featureMouseBrightness.configuration.enabledLogo) {
        this.brightnessLogo = this.addon.mouseGetLogoBrightness(this.internalId);
      }
      if(featureMouseBrightness.configuration.enabledScroll) {
        this.brightnessScroll = this.addon.mouseGetScrollBrightness(this.internalId);
      }
      if(featureMouseBrightness.configuration.enabledLeft) {
        this.brightnessLeft = this.addon.mouseGetLeftBrightness(this.internalId);
      }
      if(featureMouseBrightness.configuration.enabledRight) {
        this.brightnessRight = this.addon.mouseGetRightBrightness(this.internalId);
      }
    }

    if(this.hasFeature(FeatureIdentifier.BUTTON_MAPPING)) {
      this.panelType = this.getSidePanelType();
      this.activeProfile = this.getActiveProfile();
      this.slotOccupied = { 1: false, 2: false, 3: false, 4: false, 5: false };
      this.probeSlotOccupancy();
      // Read each slot's active-stage DPI from hardware into the cache so
      // switchProfile can display the correct value immediately (before the
      // user has written DPI via the app UI this session).
      if (this.slotDpi) {
        for (let slot = 1; slot <= 5; slot++) {
          try {
            const r = this.addon.mouseGetDpiForProfile(this.internalId, slot);
            if (r && r.ok) this.slotDpi[slot] = r.x;
          } catch (e) {
            // leave null — switchProfile falls back to mouseGetDpi
          }
        }
        // Also seed this.dpi from the currently-active slot's cached value, so
        // the initial UI shows the right number before the user does anything.
        if (this.activeProfile >= 1 && this.activeProfile <= 5 && this.slotDpi[this.activeProfile] !== null) {
          this.dpi = this.slotDpi[this.activeProfile];
        }
      }
    }

    return super.init();
  }

  refresh() {
    super.refresh();
    if(this.hasFeature(FeatureIdentifier.BATTERY)) {
      this.batteryLevel = this.addon.getBatteryLevel(this.internalId);
      this.chargingStatus = this.addon.getChargingStatus(this.internalId);
    }
  }

  getState() {
    const deviceState = super.getState();
    if(this.hasFeature(FeatureIdentifier.MOUSE_DPI)) {
      deviceState['dpi'] = this.dpi;
    }

    if(this.hasFeature(FeatureIdentifier.POLL_RATE)) {
      deviceState['pollRate'] = this.pollRate;
    }

    const featureMouseBrightness = this.getFeature(FeatureIdentifier.MOUSE_BRIGHTNESS);
    if(typeof featureMouseBrightness !== 'undefined') {
      if(featureMouseBrightness.configuration.enabledMatrix) {
        deviceState['brightness'] = this.brightness;
      }
      if(featureMouseBrightness.configuration.enabledLogo) {
        deviceState['brightnessLogo'] = this.brightnessLogo;
      }
      if(featureMouseBrightness.configuration.enabledScroll) {
        deviceState['brightnessScroll'] = this.brightnessScroll;
      }
      if(featureMouseBrightness.configuration.enabledLeft) {
        deviceState['brightnessLeft'] = this.brightnessLeft;
      }
      if(featureMouseBrightness.configuration.enabledRight) {
        deviceState['brightnessRight'] = this.brightnessRight;
      }
    }
    return deviceState;
  }

  resetToState(state) {
    super.resetToState(state);
    if(this.hasFeature(FeatureIdentifier.MOUSE_DPI)) {
      this.setDPI(state.dpi);  // pass default (null) → operates on active slot
    }
    if(this.hasFeature(FeatureIdentifier.POLL_RATE)) {
      this.setPollRate(state.pollRate);
    }

    const featureMouseBrightness = this.getFeature(FeatureIdentifier.MOUSE_BRIGHTNESS);
    if(typeof featureMouseBrightness !== 'undefined') {
      if(featureMouseBrightness.configuration.enabledMatrix) {
        if(typeof state.brightness !== 'undefined') {
          this.setBrightnessMatrix(state.brightness);
        }
      }
      if(featureMouseBrightness.configuration.enabledLogo) {
        this.setBrightnessLogo(state.brightnessLogo);
      }
      if(featureMouseBrightness.configuration.enabledScroll) {
        this.setBrightnessScroll(state.brightnessScroll);
      }
      if(featureMouseBrightness.configuration.enabledLeft) {
        this.setBrightnessLeft(state.brightnessLeft);
      }
      if(featureMouseBrightness.configuration.enabledRight) {
        this.setBrightnessRight(state.brightnessRight);
      }
    }
  }

  setModeNone() {
    super.setModeNone();
    this.addon.mouseSetLogoModeNone(this.internalId);
  }

  setModeStaticNoStore(color) {
    super.setModeStaticNoStore(color);
    this.addon.mouseSetLogoModeStaticNoStore(this.internalId, new Uint8Array(color));
  }

  setModeStatic(color) {
    super.setModeStatic(color);
    this.addon.mouseSetLogoModeStatic(this.internalId, new Uint8Array(color));
  }

  setSpectrum() {
    super.setSpectrum();
    this.addon.mouseSetLogoModeSpectrum(this.internalId);
  }

  setBreathe(color) {
    super.setBreathe(color);
    this.addon.mouseSetLogoModeBreathe(this.internalId, new Uint8Array(color));
  }

  // device specific
  setWaveSimple(direction) {
    this.setModeState('waveSimple', direction);
    this.addon.mouseSetLogoModeWave(this.internalId, direction);
  }
  setReactive(colorMode) {
    this.setModeState('reactive', colorMode);
    this.addon.mouseSetLogoModeReactive(this.internalId, new Uint8Array(colorMode));
  }
  setLogoLEDEffect(effect) {
    this.setModeState('ledEffect', effect);
    this.addon.mouseSetLogoLEDEffect(this.internalId, effect);
  }

  getDPI(profile = null) {
    const p = profile !== null ? profile : this.activeProfile;
    if (p !== this.activeProfile) {
      this.addon.mouseActivateProfile(this.internalId, p);
      this.activeProfile = p;
    }
    if (this.slotDpi && this.slotDpi[p] !== null) {
      return this.slotDpi[p];
    }
    return this.addon.mouseGetDpi(this.internalId);
  }
  setDPI(dpi, profile = null) {
    // DPI on Naga V2 Pro is stored per-profile via SET_DPI_STAGES (0x04:0x06),
    // NOT via VARSTORE (which is a single global register). To persist DPI on
    // profile N, we write a 5-stage table targeting that profile with the user's
    // DPI as the active stage. Other stages are fractions/multiples so the
    // hardware's DPI-cycle button has usable alternatives.
    const p = profile !== null ? profile : this.activeProfile;
    this.dpi = dpi;
    if (this.slotDpi) this.slotDpi[p] = dpi;
    const stages = [
      { x: Math.max(200, Math.floor(dpi / 4)), y: Math.max(200, Math.floor(dpi / 4)) },
      { x: Math.max(400, Math.floor(dpi / 2)), y: Math.max(400, Math.floor(dpi / 2)) },
      { x: dpi, y: dpi },
      { x: Math.min(30000, dpi * 2), y: Math.min(30000, dpi * 2) },
      { x: Math.min(30000, dpi * 4), y: Math.min(30000, dpi * 4) },
    ];
    // Guard against all-identical stages (device rejects): if dpi is tiny or huge,
    // the clamps could collide. Add +i bumps to guarantee uniqueness.
    const seen = new Set();
    for (let i = 0; i < stages.length; i++) {
      while (seen.has(stages[i].x)) {
        stages[i].x++;
        stages[i].y++;
      }
      seen.add(stages[i].x);
    }
    // active_stage is 1-indexed; stage 3 is the user-chosen DPI (middle).
    this.addon.mouseSetDpiStages(this.internalId, p, 3, stages);
  }

  getBrightnessMatrix() {
    return this.brightness;
  }
  setBrightnessMatrix(brightness) {
    this.brightness = brightness;
    this.addon.mouseSetBrightness(this.internalId, this.brightness);
  }

  getBrightnessLogo() {
    return this.brightnessLogo;
  }
  setBrightnessLogo(brightness) {
    this.brightnessLogo = brightness;
    this.addon.mouseSetLogoBrightness(this.internalId, this.brightnessLogo);
  }

  getBrightnessScroll() {
    return this.brightnessScroll;
  }
  setBrightnessScroll(brightness) {
    this.brightnessScroll = brightness;
    this.addon.mouseSetScrollBrightness(this.internalId, this.brightnessScroll);
  }

  getBrightnessLeft() {
    return this.brightnessLeft;
  }
  setBrightnessLeft(brightness) {
    this.brightnessLeft = brightness;
    this.addon.mouseSetLeftBrightness(this.internalId, this.brightnessLeft);
  }

  getBrightnessRight() {
    return this.brightnessRight;
  }
  setBrightnessRight(brightness) {
    this.brightnessRight = brightness;
    this.addon.mouseSetRightBrightness(this.internalId, this.brightnessRight);
  }

  getPollRate() {
    return this.pollRate;
  }
  setPollRate(pollRate) {
    this.pollRate = pollRate;
    this.addon.mouseSetPollRate(this.internalId, this.pollRate);
  }

  getSidePanelType() {
    return this.addon.mouseGetSidePanelType(this.internalId);
  }

  getActiveProfile() {
    return this.addon.mouseGetActiveProfile(this.internalId);
  }

  setActiveProfile(slot) {
    this.addon.mouseActivateProfile(this.internalId, slot);
    this.addon.mouseMacroClear(this.internalId);
    this.activeProfile = slot;
  }

  switchProfile(slot) {
    if (!this.panelType) return;
    // 0x05:0x04 is the real SET_ACTIVE_PROFILE in PC mode on this device.
    // The older 0x05:0x03 (mouseSetActiveProfile) does something else.
    this.addon.mouseActivateProfile(this.internalId, slot);
    this.activeProfile = slot;
    // Use cached per-slot DPI if we've set one this session; otherwise fall
    // back to VARSTORE read (which is stale but better than nothing for slots
    // we haven't written in this session).
    if (this.slotDpi && this.slotDpi[slot] !== null) {
      this.dpi = this.slotDpi[slot];
    } else {
      this.dpi = this.addon.mouseGetDpi(this.internalId);
    }
  }

  saveToSlot(targetSlot) {
    if (!this.panelType) return;
    if (targetSlot < 1 || targetSlot > 5) return;
    const sourceSlot = this.activeProfile;
    const buttons = this.getButtonsForPanel(this.panelType);
    const snapshot = [];
    [0x00, 0x01].forEach(layer => {
      buttons.forEach(btn => {
        const mapping = this.getButtonMapping(btn.id, layer, sourceSlot);
        snapshot.push({ layer, buttonId: btn.id, actionType: mapping.actionType, params: mapping.params });
      });
    });
    const currentDpi = this.dpi;
    // Switch hardware to target slot.
    this.addon.mouseActivateProfile(this.internalId, targetSlot);
    this.activeProfile = targetSlot;
    // Write button mappings to the target slot (Fork B — direct per-slot write).
    snapshot.forEach(({ layer, buttonId, actionType, params }) => {
      this.addon.mouseSetButtonMapping(this.internalId, targetSlot, buttonId, layer, actionType, params);
    });
    // Write per-profile DPI stages to the target slot.
    this.setDPI(currentDpi, targetSlot);
    this.addon.mouseMacroClear(this.internalId);
    this.slotOccupied[targetSlot] = true;
  }

  clearSlot(slot) {
    if (slot === 1) return; // Slot 1 cannot be cleared
    // Send ACTIVATE_PROFILE + MACRO_CLEAR as observed in capture
    this.addon.mouseActivateProfile(this.internalId, slot);
    this.addon.mouseMacroClear(this.internalId);
    this.slotOccupied[slot] = false;
    if (slot === this.activeProfile) {
      this.activeProfile = 1;
    }
  }

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

  getButtonMapping(buttonId, layer = 0x00, profile = null) {
    const p = profile !== null ? profile : this.activeProfile;
    const raw = this.addon.mouseGetButtonMapping(this.internalId, p, buttonId, layer);
    return {
      profile: raw[0],
      buttonId: raw[1],
      layer: raw[2],
      actionType: raw[3],
      params: [raw[4], raw[5], raw[6], raw[7], raw[8], raw[9]],
    };
  }

  setButtonMapping(buttonId, layer, actionType, params, profile = null) {
    // Button mapping on Naga V2 Pro is Fork B: mouseSetButtonMapping(arg[0]=slot)
    // writes directly to the target slot independent of the currently-active
    // profile. No mirror-to-slot-1 needed.
    const p = profile !== null ? profile : this.activeProfile;
    this.addon.mouseSetButtonMapping(this.internalId, p, buttonId, layer, actionType, params);
  }

  getButtonsForPanel(panelId) {
    const feature = this.getFeature(FeatureIdentifier.BUTTON_MAPPING);
    if (!feature) return [];
    const panelConfig = feature.configuration.panels[panelId];
    return panelConfig ? panelConfig.buttons : [];
  }

  getAllButtonMappings(panelId, layer = 0x00, profile = null) {
    const buttons = this.getButtonsForPanel(panelId);
    return buttons.map(btn => ({
      ...btn,
      mapping: this.getButtonMapping(btn.id, layer, profile),
    }));
  }
}