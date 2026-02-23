import React from 'react';
import { SectionSettingBlock } from './sectionsettingblock';
import { ipcRenderer } from 'electron';
import { FeatureIdentifier } from '../../main/feature/featureidentifier';

const PANEL_NAMES = {
  0x01: '2-Button Side Panel',
  0x03: '12-Button Side Panel',
  0x04: '6-Button Side Panel',
};

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

export class SectionSettingButtonMapping extends SectionSettingBlock {

  constructor(props) {
    super(props);
    this.buttonMappingFeature = this.deviceSelected.features.find(
      feature => feature.featureIdentifier === FeatureIdentifier.BUTTON_MAPPING
    );
    this.state = {
      panelType: this.deviceSelected.panelType || null,
      mappings: [],
      layer: 0x00,
    };

    this.handleMappingsResponse = this.handleMappingsResponse.bind(this);
    this.handleMappingUpdated = this.handleMappingUpdated.bind(this);
  }

  componentDidMount() {
    ipcRenderer.on('button-mappings-response', this.handleMappingsResponse);
    ipcRenderer.on('button-mapping-updated', this.handleMappingUpdated);
    this.requestMappings();
  }

  componentWillUnmount() {
    ipcRenderer.removeListener('button-mappings-response', this.handleMappingsResponse);
    ipcRenderer.removeListener('button-mapping-updated', this.handleMappingUpdated);
  }

  handleMappingsResponse(event, data) {
    this.setState({ mappings: data.mappings });
  }

  handleMappingUpdated(event, data) {
    // Refresh all mappings after an update
    this.requestMappings();
  }

  requestMappings() {
    if (this.state.panelType == null) return;
    ipcRenderer.send('get-button-mappings', {
      device: this.deviceSelected,
      panelId: this.state.panelType,
      layer: this.state.layer,
    });
  }

  switchLayer(layer) {
    this.setState({ layer }, () => {
      this.requestMappings();
    });
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
    const panelConfig = this.buttonMappingFeature.configuration.panels[this.state.panelType];
    if (!panelConfig) return;
    const buttonConfig = panelConfig.buttons.find(b => b.id === buttonId);
    if (!buttonConfig) return;
    ipcRenderer.send('set-button-mapping', {
      device: this.deviceSelected,
      buttonId,
      layer: this.state.layer,
      actionType: buttonConfig.defaultAction.type,
      params: buttonConfig.defaultAction.params,
    });
  }

  renderTitle() {
    return 'Side Button Mapping';
  }

  renderSettings() {
    if (this.buttonMappingFeature == null) {
      return null;
    }

    const { panelType, mappings, layer } = this.state;

    if (panelType == null) {
      return <div style={{ padding: '10px', color: 'grey' }}>
        No side panel detected
      </div>;
    }

    const panelName = PANEL_NAMES[panelType] || `Panel 0x${panelType.toString(16)}`;

    return <div style={{ paddingTop: '10px' }}>
      <div style={{ padding: '0 10px 10px', color: '#47e10c', fontSize: '13px' }}>
        {panelName}
      </div>

      <div style={{ display: 'flex', padding: '0 10px 10px', gap: '5px' }}>
        <button
          onClick={() => this.switchLayer(0x00)}
          style={{
            flex: 1,
            fontSize: '12px',
            padding: '5px',
            borderRadius: '15px',
            border: '1px solid black',
            outline: 'none',
            cursor: 'pointer',
            backgroundColor: layer === 0x00 ? '#47e10c' : '#35363a',
            color: layer === 0x00 ? 'black' : '#47e10c',
          }}
        >Normal</button>
        <button
          onClick={() => this.switchLayer(0x01)}
          style={{
            flex: 1,
            fontSize: '12px',
            padding: '5px',
            borderRadius: '15px',
            border: '1px solid black',
            outline: 'none',
            cursor: 'pointer',
            backgroundColor: layer === 0x01 ? '#47e10c' : '#35363a',
            color: layer === 0x01 ? 'black' : '#47e10c',
          }}
        >Hypershift</button>
      </div>

      {mappings.map(btn => (
        <div key={btn.id} style={{
          display: 'flex',
          flexDirection: 'row',
          alignItems: 'center',
          padding: '4px 10px',
          borderBottom: '1px solid #35363a',
        }}>
          <div style={{ width: '80px', color: '#47e10c', fontSize: '12px' }}>
            {btn.label}
          </div>
          <div style={{ flex: 1, color: 'grey', fontSize: '12px' }}>
            {describeMapping(btn.mapping)}
          </div>
          <button
            onClick={() => this.restoreDefault(btn.id)}
            style={{
              fontSize: '10px',
              padding: '3px 8px',
              marginRight: '4px',
              borderRadius: '10px',
              border: '1px solid black',
              backgroundColor: '#35363a',
              color: '#47e10c',
              cursor: 'pointer',
              outline: 'none',
            }}
          >Default</button>
          <button
            onClick={() => this.setDisabled(btn.id)}
            style={{
              fontSize: '10px',
              padding: '3px 8px',
              borderRadius: '10px',
              border: '1px solid black',
              backgroundColor: '#35363a',
              color: '#47e10c',
              cursor: 'pointer',
              outline: 'none',
            }}
          >Disable</button>
        </div>
      ))}
    </div>;
  }
}
