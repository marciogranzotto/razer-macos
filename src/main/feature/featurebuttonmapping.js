import { Feature } from './feature';
import { FeatureIdentifier } from './featureidentifier';

export class FeatureButtonMapping extends Feature {
  constructor(config) {
    super(FeatureIdentifier.BUTTON_MAPPING, config);
  }

  getDefaultConfiguration() {
    return {
      panels: {
        0x01: { // 2-button
          buttons: [
            { id: 0x05, label: 'Button 1', defaultAction: { type: 0x01, params: [0x01, 0x05, 0, 0, 0, 0] } },
            { id: 0x04, label: 'Button 2', defaultAction: { type: 0x01, params: [0x01, 0x04, 0, 0, 0, 0] } },
          ],
        },
        0x04: { // 6-button
          buttons: [
            { id: 0x50, label: 'Button 1', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x1e, 0, 0, 0] } },
            { id: 0x51, label: 'Button 2', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x1f, 0, 0, 0] } },
            { id: 0x52, label: 'Button 3', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x20, 0, 0, 0] } },
            { id: 0x53, label: 'Button 4', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x21, 0, 0, 0] } },
            { id: 0x54, label: 'Button 5', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x22, 0, 0, 0] } },
            { id: 0x55, label: 'Button 6', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x23, 0, 0, 0] } },
          ],
        },
        0x03: { // 12-button
          buttons: [
            { id: 0x40, label: 'Button 1',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x1e, 0, 0, 0] } },
            { id: 0x41, label: 'Button 2',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x1f, 0, 0, 0] } },
            { id: 0x42, label: 'Button 3',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x20, 0, 0, 0] } },
            { id: 0x43, label: 'Button 4',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x21, 0, 0, 0] } },
            { id: 0x44, label: 'Button 5',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x22, 0, 0, 0] } },
            { id: 0x45, label: 'Button 6',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x23, 0, 0, 0] } },
            { id: 0x46, label: 'Button 7',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x24, 0, 0, 0] } },
            { id: 0x47, label: 'Button 8',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x25, 0, 0, 0] } },
            { id: 0x48, label: 'Button 9',  defaultAction: { type: 0x02, params: [0x02, 0x00, 0x26, 0, 0, 0] } },
            { id: 0x49, label: 'Button 10', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x27, 0, 0, 0] } },
            { id: 0x4a, label: 'Button 11', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x2d, 0, 0, 0] } },
            { id: 0x4b, label: 'Button 12', defaultAction: { type: 0x02, params: [0x02, 0x00, 0x2e, 0, 0, 0] } },
          ],
        },
      },
    };
  }
}
