import React from 'react';
import { SectionSettingBlock } from './sectionsettingblock';
import { ipcRenderer } from 'electron';
import { FeatureIdentifier } from '../../main/feature/featureidentifier';

const PANEL_NAMES = {
  0x01: '2-Button Side Panel',
  0x03: '12-Button Side Panel',
  0x04: '6-Button Side Panel',
};

const PANEL_GRID = {
  0x01: { columns: 2, rows: 1 },
  0x03: { columns: 3, rows: 4 },
  0x04: { columns: 3, rows: 2 },
};

const ACTION_TYPES = [
  { value: 0x00, label: 'Disabled' },
  { value: 0x01, label: 'Mouse Button' },
  { value: 0x02, label: 'Keyboard Key' },
  { value: 0x0a, label: 'Multimedia' },
  { value: 0x0c, label: 'Hypershift' },
  { value: 0x12, label: 'Scroll Wheel' },
  { value: 0x06, label: 'Sensitivity' },
  { value: 'default', label: 'Default' },
];

const MOUSE_BUTTONS = [
  { value: 0x01, label: 'Left Click' },
  { value: 0x02, label: 'Right Click' },
  { value: 0x03, label: 'Middle Click' },
  { value: 0x04, label: 'Back' },
  { value: 0x05, label: 'Forward' },
];

const KEYBOARD_KEYS = [
  { value: 0x04, label: 'A' }, { value: 0x05, label: 'B' }, { value: 0x06, label: 'C' },
  { value: 0x07, label: 'D' }, { value: 0x08, label: 'E' }, { value: 0x09, label: 'F' },
  { value: 0x0a, label: 'G' }, { value: 0x0b, label: 'H' }, { value: 0x0c, label: 'I' },
  { value: 0x0d, label: 'J' }, { value: 0x0e, label: 'K' }, { value: 0x0f, label: 'L' },
  { value: 0x10, label: 'M' }, { value: 0x11, label: 'N' }, { value: 0x12, label: 'O' },
  { value: 0x13, label: 'P' }, { value: 0x14, label: 'Q' }, { value: 0x15, label: 'R' },
  { value: 0x16, label: 'S' }, { value: 0x17, label: 'T' }, { value: 0x18, label: 'U' },
  { value: 0x19, label: 'V' }, { value: 0x1a, label: 'W' }, { value: 0x1b, label: 'X' },
  { value: 0x1c, label: 'Y' }, { value: 0x1d, label: 'Z' },
  { value: 0x1e, label: '1' }, { value: 0x1f, label: '2' }, { value: 0x20, label: '3' },
  { value: 0x21, label: '4' }, { value: 0x22, label: '5' }, { value: 0x23, label: '6' },
  { value: 0x24, label: '7' }, { value: 0x25, label: '8' }, { value: 0x26, label: '9' },
  { value: 0x27, label: '0' },
  { value: 0x2d, label: '-' }, { value: 0x2e, label: '=' },
  { value: 0x3a, label: 'F1' }, { value: 0x3b, label: 'F2' }, { value: 0x3c, label: 'F3' },
  { value: 0x3d, label: 'F4' }, { value: 0x3e, label: 'F5' }, { value: 0x3f, label: 'F6' },
  { value: 0x40, label: 'F7' }, { value: 0x41, label: 'F8' }, { value: 0x42, label: 'F9' },
  { value: 0x43, label: 'F10' }, { value: 0x44, label: 'F11' }, { value: 0x45, label: 'F12' },
  { value: 0x28, label: 'Enter' }, { value: 0x29, label: 'Escape' },
  { value: 0x2a, label: 'Backspace' }, { value: 0x2b, label: 'Tab' },
  { value: 0x2c, label: 'Space' },
  { value: 0x4f, label: 'Right Arrow' }, { value: 0x50, label: 'Left Arrow' },
  { value: 0x51, label: 'Down Arrow' }, { value: 0x52, label: 'Up Arrow' },
];

const MEDIA_KEYS = [
  { value: 0x00cd, label: 'Play/Pause' },
  { value: 0x00b5, label: 'Next Track' },
  { value: 0x00b6, label: 'Previous Track' },
  { value: 0x00e2, label: 'Mute' },
  { value: 0x00e9, label: 'Volume Up' },
  { value: 0x00ea, label: 'Volume Down' },
];

const SCROLL_ACTIONS = [
  { value: 0x04, label: 'Cycle Up Scroll Stages' },
];

function describeMapping(mapping) {
  if (!mapping) return 'Unknown';
  const { actionType, params } = mapping;
  switch (actionType) {
    case 0x00: return 'Disabled';
    case 0x01: {
      const btn = MOUSE_BUTTONS.find(b => b.value === params[1]);
      return btn ? btn.label : `Mouse Btn ${params[1]}`;
    }
    case 0x02: {
      const mod = params[1] || 0;
      const key = KEYBOARD_KEYS.find(k => k.value === params[2]);
      const keyName = key ? key.label : `Key 0x${params[2].toString(16)}`;
      const mods = [];
      if (mod & 0x01) mods.push('Ctrl');
      if (mod & 0x02) mods.push('Shift');
      if (mod & 0x04) mods.push('Alt');
      if (mod & 0x08) mods.push('Cmd');
      return mods.length > 0 ? `${mods.join('+')}+${keyName}` : keyName;
    }
    case 0x0a: {
      const code = (params[1] << 8) | params[2];
      const media = MEDIA_KEYS.find(m => m.value === code);
      return media ? media.label : `Media 0x${code.toString(16)}`;
    }
    case 0x06: {
      const xDpi = (params[2] << 8) | params[3];
      const yDpi = (params[4] << 8) | params[5];
      return xDpi === yDpi ? `Clutch ${xDpi} DPI` : `Clutch ${xDpi}/${yDpi} DPI`;
    }
    case 0x0c: return 'Hypershift';
    case 0x12: {
      const scrollAction = SCROLL_ACTIONS.find(s => s.value === params[1]);
      return scrollAction ? scrollAction.label : `Scroll 0x${params[1].toString(16)}`;
    }
    default: return `Type 0x${actionType.toString(16)}`;
  }
}

const btnStyle = {
  fontSize: '10px',
  padding: '3px 8px',
  borderRadius: '10px',
  border: '1px solid black',
  backgroundColor: '#35363a',
  color: '#47e10c',
  cursor: 'pointer',
  outline: 'none',
};

const selectStyle = {
  fontSize: '11px',
  padding: '3px 6px',
  borderRadius: '6px',
  border: '1px solid #555',
  backgroundColor: '#2a2a2e',
  color: '#47e10c',
  outline: 'none',
  cursor: 'pointer',
};

function gridCellStyle(isSelected) {
  return {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '8px 4px',
    borderRadius: '6px',
    border: isSelected ? '2px solid #47e10c' : '2px solid #35363a',
    backgroundColor: isSelected ? '#35363a' : '#2a2a2e',
    cursor: 'pointer',
    minHeight: '48px',
    transition: 'border-color 0.15s',
  };
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
      editingButton: null,
      editActionType: 0x00,
      editActionValue: 0,
      editModifier: 0,
    };

    this.handleMappingsResponse = this.handleMappingsResponse.bind(this);
    this.handleMappingUpdated = this.handleMappingUpdated.bind(this);
    this.handlePanelTypeResponse = this.handlePanelTypeResponse.bind(this);
    this.handlePanelChanged = this.handlePanelChanged.bind(this);
  }

  componentDidMount() {
    ipcRenderer.on('button-mappings-response', this.handleMappingsResponse);
    ipcRenderer.on('button-mapping-updated', this.handleMappingUpdated);
    ipcRenderer.on('side-panel-type-response', this.handlePanelTypeResponse);
    ipcRenderer.on('panel-type-changed', this.handlePanelChanged);
    this.refreshPanelType();
  }

  componentWillUnmount() {
    ipcRenderer.removeListener('button-mappings-response', this.handleMappingsResponse);
    ipcRenderer.removeListener('button-mapping-updated', this.handleMappingUpdated);
    ipcRenderer.removeListener('side-panel-type-response', this.handlePanelTypeResponse);
    ipcRenderer.removeListener('panel-type-changed', this.handlePanelChanged);
  }

  handlePanelTypeResponse(event, data) {
    const newPanel = data.panelType || null;
    if (newPanel !== this.state.panelType) {
      this.setState({ panelType: newPanel, mappings: [], editingButton: null }, () => {
        this.requestMappings();
      });
    }
  }

  handlePanelChanged(event, data) {
    if (data.productId !== this.deviceSelected.productId) return;
    const newPanel = data.panelId || null;
    this.setState({ panelType: newPanel, mappings: [], editingButton: null }, () => {
      this.requestMappings();
    });
  }

  handleMappingsResponse(event, data) {
    this.setState({ mappings: data.mappings });
  }

  handleMappingUpdated(event, data) {
    this.requestMappings();
  }

  refreshPanelType() {
    ipcRenderer.send('get-side-panel-type', {
      device: this.deviceSelected,
    });
    // Also request mappings if we already have a panel type
    if (this.state.panelType != null) {
      this.requestMappings();
    }
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
    this.setState({ layer, editingButton: null }, () => {
      this.requestMappings();
    });
  }

  startEditing(btn) {
    const mapping = btn.mapping || {};
    this.setState({
      editingButton: btn.id,
      editActionType: mapping.actionType || 0x00,
      editActionValue: this.getValueFromMapping(mapping),
      editModifier: (mapping.actionType === 0x02 && mapping.params) ? (mapping.params[1] || 0) : 0,
    });
  }

  cancelEditing() {
    this.setState({ editingButton: null });
  }

  getValueFromMapping(mapping) {
    if (!mapping) return 0;
    switch (mapping.actionType) {
      case 0x01: return mapping.params[1] || 0x01;
      case 0x02: return mapping.params[2] || 0x04;
      case 0x0a: return (mapping.params[1] << 8) | mapping.params[2] || 0x00cd;
      case 0x0c: return 0;
      case 0x12: return mapping.params[1] || 0x04;
      case 0x06: {
        const xDpi = (mapping.params[2] << 8) | mapping.params[3];
        const yDpi = (mapping.params[4] << 8) | mapping.params[5];
        return (xDpi << 16) | yDpi;
      }
      default: return 0;
    }
  }

  buildParams(actionType, actionValue, modifier = 0) {
    switch (actionType) {
      case 0x00: return [0, 0, 0, 0, 0, 0];
      case 0x01: return [0x01, actionValue, 0, 0, 0, 0];
      case 0x02: return [0x02, modifier, actionValue, 0, 0, 0];
      case 0x0a: return [0x02, (actionValue >> 8) & 0xff, actionValue & 0xff, 0, 0, 0];
      case 0x0c: return [0x01, 0x01, 0, 0, 0, 0];
      case 0x12: return [0x01, actionValue, 0, 0, 0, 0];
      case 0x06: {
        const xDpi = (actionValue >> 16) & 0xffff;
        const yDpi = actionValue & 0xffff;
        const flags = xDpi !== yDpi ? 0x05 : 0x00;
        return [0x05, flags, (xDpi >> 8) & 0xff, xDpi & 0xff, (yDpi >> 8) & 0xff, yDpi & 0xff];
      }
      default: return [0, 0, 0, 0, 0, 0];
    }
  }

  applyEdit(buttonId) {
    const { editActionType, editActionValue, editModifier } = this.state;
    const params = this.buildParams(editActionType, editActionValue, editModifier);
    ipcRenderer.send('set-button-mapping', {
      device: this.deviceSelected,
      buttonId,
      layer: this.state.layer,
      actionType: editActionType,
      params,
    });
    this.setState({ editingButton: null });
  }

  renderTitle() {
    return 'Side Button Mapping';
  }

  renderEditor(btnId) {
    const { editActionType, editActionValue } = this.state;

    return <div style={{
      padding: '8px 10px',
      backgroundColor: '#2a2a2e',
      borderBottom: '1px solid #47e10c',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
        <span style={{ color: '#999', fontSize: '11px', width: '45px' }}>Action:</span>
        <select
          value={editActionType}
          onChange={(e) => {
            const at = parseInt(e.target.value);
            let defaultVal = 0;
            if (at === 0x01) defaultVal = 0x01;
            else if (at === 0x02) defaultVal = 0x04;
            else if (at === 0x0a) defaultVal = 0x00cd;
            else if (at === 0x0c) defaultVal = 0;
            else if (at === 0x12) defaultVal = 0x04;
            else if (at === 0x06) defaultVal = (800 << 16) | 800;
            this.setState({ editActionType: at, editActionValue: defaultVal });
          }}
          style={selectStyle}
        >
          {ACTION_TYPES.map(at => (
            <option key={at.value} value={at.value}>{at.label}</option>
          ))}
        </select>
      </div>

      {editActionType === 0x01 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span style={{ color: '#999', fontSize: '11px', width: '45px' }}>Button:</span>
          <select
            value={editActionValue}
            onChange={(e) => this.setState({ editActionValue: parseInt(e.target.value) })}
            style={selectStyle}
          >
            {MOUSE_BUTTONS.map(mb => (
              <option key={mb.value} value={mb.value}>{mb.label}</option>
            ))}
          </select>
        </div>
      )}

      {editActionType === 0x02 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span style={{ color: '#999', fontSize: '11px', width: '45px' }}>Key:</span>
          <select
            value={editActionValue}
            onChange={(e) => this.setState({ editActionValue: parseInt(e.target.value) })}
            style={selectStyle}
          >
            {KEYBOARD_KEYS.map(kk => (
              <option key={kk.value} value={kk.value}>{kk.label}</option>
            ))}
          </select>
        </div>
      )}

      {editActionType === 0x0a && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <span style={{ color: '#999', fontSize: '11px', width: '45px' }}>Media:</span>
          <select
            value={editActionValue}
            onChange={(e) => this.setState({ editActionValue: parseInt(e.target.value) })}
            style={selectStyle}
          >
            {MEDIA_KEYS.map(mk => (
              <option key={mk.value} value={mk.value}>{mk.label}</option>
            ))}
          </select>
        </div>
      )}

      <div style={{ display: 'flex', gap: '5px', justifyContent: 'flex-end' }}>
        <button onClick={() => this.cancelEditing()} style={btnStyle}>Cancel</button>
        <button onClick={() => this.applyEdit(btnId)}
          style={{ ...btnStyle, backgroundColor: '#47e10c', color: 'black' }}
        >Apply</button>
      </div>
    </div>;
  }

  renderSettings() {
    if (this.buttonMappingFeature == null) {
      return null;
    }

    const { panelType, mappings, layer, editingButton } = this.state;

    if (panelType == null) {
      return <div style={{ padding: '10px', color: 'grey', display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span>No side panel detected</span>
        <button onClick={() => this.refreshPanelType()} style={btnStyle}>Refresh</button>
      </div>;
    }

    const panelName = PANEL_NAMES[panelType] || `Panel 0x${panelType.toString(16)}`;

    return <div style={{ paddingTop: '10px' }}>
      <div style={{ display: 'flex', padding: '0 10px 10px', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ color: '#47e10c', fontSize: '13px' }}>{panelName}</span>
        <button onClick={() => this.refreshPanelType()} style={btnStyle}>Refresh</button>
      </div>

      <div style={{ display: 'flex', padding: '0 10px 10px', gap: '5px' }}>
        <button
          onClick={() => this.switchLayer(0x00)}
          style={{
            flex: 1, fontSize: '12px', padding: '5px', borderRadius: '15px',
            border: '1px solid black', outline: 'none', cursor: 'pointer',
            backgroundColor: layer === 0x00 ? '#47e10c' : '#35363a',
            color: layer === 0x00 ? 'black' : '#47e10c',
          }}
        >Normal</button>
        <button
          onClick={() => this.switchLayer(0x01)}
          style={{
            flex: 1, fontSize: '12px', padding: '5px', borderRadius: '15px',
            border: '1px solid black', outline: 'none', cursor: 'pointer',
            backgroundColor: layer === 0x01 ? '#47e10c' : '#35363a',
            color: layer === 0x01 ? 'black' : '#47e10c',
          }}
        >Hypershift</button>
      </div>

      {(() => {
        const grid = PANEL_GRID[panelType] || { columns: 2, rows: 1 };
        return <div style={{
          display: 'grid',
          gridTemplateColumns: `repeat(${grid.columns}, 1fr)`,
          gap: '6px',
          padding: '0 10px 10px',
        }}>
          {mappings.map(btn => (
            <div
              key={btn.id}
              onClick={() => this.startEditing(btn)}
              style={gridCellStyle(editingButton === btn.id)}
            >
              <div style={{ color: '#47e10c', fontSize: '11px', fontWeight: 'bold' }}>
                {btn.label}
              </div>
              <div style={{ color: '#999', fontSize: '9px', marginTop: '2px', textAlign: 'center' }}>
                {describeMapping(btn.mapping)}
              </div>
            </div>
          ))}
        </div>;
      })()}

      {editingButton != null && this.renderEditor(editingButton)}
    </div>;
  }
}
