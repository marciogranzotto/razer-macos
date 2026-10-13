import React, { useState, useEffect } from 'react';
import './react-tabs.css';
import { ipcRenderer } from 'electron';
import { ViewDeviceSettings } from './views/viewdevicesettings';
import { ViewColorSettings } from './views/viewcolorpicker';
import { ViewStateSettings } from './views/viewstatesettings';

/**
 * Root React component
 */
export class App extends React.Component {
  constructor(props) {
    super(props);

    this.state = {
      mode: 'device',
      message: null
    };

    ipcRenderer.on('render-view', (event, message) => {
      const {mode} = message;
      this.setState({mode: null, message: null});
      this.setState({mode: mode, message: message});
    })

    this.contentRef = React.createRef();
  }

  componentDidMount() {
    // Report the natural height of the rendered view, so that the main process can fit the window to it
    this.contentObserver = new ResizeObserver(entries => {
      ipcRenderer.send('content-height-changed', Math.ceil(entries[0].contentRect.height));
    });
    this.contentObserver.observe(this.contentRef.current);
  }

  componentWillUnmount() {
    this.contentObserver.disconnect();
  }

  render() {
    return <div id='content' ref={this.contentRef}>{this.renderView()}</div>;
  }

  renderView() {
    if(this.state.mode === 'device') {
      return <ViewDeviceSettings config={this.state.message}></ViewDeviceSettings>;
    } else if(this.state.mode == 'color') {
      return <ViewColorSettings config={this.state.message}></ViewColorSettings>;
    } else if(this.state.mode == 'state') {
      return <ViewStateSettings config={this.state.message}></ViewStateSettings>;
    }
    return <div></div>;
  }


}
