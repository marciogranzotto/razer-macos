import React from 'react';
import MouseSensitivity from '../components/MouseSensitivity';
import { SectionSettingBlock } from './sectionsettingblock';
import { ipcRenderer } from 'electron';
import { FeatureIdentifier } from '../../main/feature/featureidentifier';

export class SectionSettingSensitivity extends SectionSettingBlock {

  constructor(props) {
    super(props);
    this.dpiFeature = this.deviceSelected.features.find(feature => feature.featureIdentifier === FeatureIdentifier.MOUSE_DPI)
    this.state = { dpi: this.deviceSelected.dpi };
    this.handleProfileSwitched = this.handleProfileSwitched.bind(this);
    this.handleSlotCleared = this.handleSlotCleared.bind(this);
  }

  componentDidMount() {
    ipcRenderer.on('profile-switched', this.handleProfileSwitched);
    ipcRenderer.on('slot-cleared', this.handleSlotCleared);
  }

  componentWillUnmount() {
    ipcRenderer.removeListener('profile-switched', this.handleProfileSwitched);
    ipcRenderer.removeListener('slot-cleared', this.handleSlotCleared);
  }

  handleProfileSwitched(event, arg) {
    if (arg.error || typeof arg.dpi !== 'number') return;
    this.setState({ dpi: arg.dpi });
  }

  handleSlotCleared(event, arg) {
    if (arg.error || typeof arg.dpi !== 'number') return;
    this.setState({ dpi: arg.dpi });
  }

  renderTitle() {
    return 'DPI';
  }

  handleClick(currentDpi) {
    let payload = {
      device: this.deviceSelected,
      dpi: currentDpi
    };
    ipcRenderer.send('request-set-dpi', payload);
    this.setState({ dpi: currentDpi });
  };

  renderSettings() {
    if(this.dpiFeature == null) {
      return null;
    }
    return <MouseSensitivity dpi={this.state.dpi} configuration={this.dpiFeature.configuration} handleClick={(dpi) => this.handleClick(dpi)} />;
  }
}