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
      this.dpi = this.addon.mouseGetDpi(this.internalId);
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
      this.slotOccupied = { 1: true, 2: false, 3: false, 4: false, 5: false };
      this.probeSlotOccupancy();
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
      this.setDPI(state.dpi, 1);
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
    // DPI is VARSTORE (Fork A) — always reads from the currently-active slot.
    // If a caller wants the DPI of a specific profile, SET_PROFILE(p) must be
    // sent first. Callers that currently pass `profile` are OK: they set it
    // first via setDPI/switchProfile, then read back, so this.activeProfile
    // is already correct.
    if (profile !== null && profile !== this.activeProfile) {
      this.addon.mouseSetActiveProfile(this.internalId, profile);
      this.activeProfile = profile;
    }
    return this.addon.mouseGetDpi(this.internalId);
  }
  setDPI(dpi, profile = null) {
    // DPI on Naga V2 Pro is Fork A: the device uses a single VARSTORE DPI register
    // that is scoped to whichever profile slot is currently active. To set DPI on
    // profile N, the hardware must be on slot N; the `profile` argument is
    // a targeting hint from callers (e.g. resetToState passing profile=1).
    const p = profile !== null ? profile : this.activeProfile;
    if (p !== this.activeProfile) {
      this.addon.mouseSetActiveProfile(this.internalId, p);
      this.activeProfile = p;
    }
    this.dpi = dpi;
    this.addon.mouseSetDpi(this.internalId, dpi);
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
    this.addon.mouseSetActiveProfile(this.internalId, slot);
    this.addon.mouseMacroClear(this.internalId);
    this.activeProfile = slot;
  }

  switchProfile(slot) {
    if (!this.panelType) return;
    this.addon.mouseSetActiveProfile(this.internalId, slot);
    this.activeProfile = slot;
    // Re-read live DPI from VARSTORE so the UI reflects the new slot's value.
    this.dpi = this.addon.mouseGetDpi(this.internalId);
  }

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
    const p = profile !== null ? profile : this.activeProfile;
    this.addon.mouseSetButtonMapping(this.internalId, p, buttonId, layer, actionType, params);
    // Slot 1 mirroring: when active profile is not slot 1 and we're writing to the active profile,
    // also write to slot 1 so the live dispatch profile stays current
    if (this.activeProfile !== 1 && p === this.activeProfile) {
      this.addon.mouseSetButtonMapping(this.internalId, 1, buttonId, layer, actionType, params);
    }
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