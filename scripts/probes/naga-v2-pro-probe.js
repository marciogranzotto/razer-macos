#!/usr/bin/env node
/**
 * Naga V2 Pro protocol probe. ONE-OFF — this file is deleted in the Phase 4
 * cleanup plan. Do not import it from production code.
 *
 * Usage:
 *   node scripts/probes/naga-v2-pro-probe.js <probe-name>
 *
 * Available probes (registered below):
 *   list          — list detected Razer devices (sanity check)
 *   set-profile   — Probe 1: SET_PROFILE active-slot verification
 *   get-active    — Probe 2: GET_ACTIVE_PROFILE at rest and after SET_PROFILE
 *   set-dpi-args  — Probe 3: SET_DPI with arg[0] ∈ {0..5}, readback each
 *   set-btn-args  — Probe 4: button-mapping write with varying arg[0]
 *   read-variants — Probe 6: GET_DPI read with varying arg[0]
 *   side-effects  — Probe 5: interactive; user observes LED/visual changes
 */

// src/driver/index.js is a webpack ES-module shim and cannot be require()'d
// directly from a standalone script. Load the native addon binary directly.
const addon = require('../../build/Release/addon.node');

function listDevices() {
  const devices = addon.getAllDevices();
  console.log(`Found ${devices.length} device(s):`);
  devices.forEach((d, i) => {
    console.log(`  [${i}] pid=0x${d.productId.toString(16)} internalId=${d.internalDeviceId}`);
  });
  return devices;
}

// Naga V2 Pro has two USB IDs: 0x00A7 (wired) and 0x00A8 (wireless).
const NAGA_V2_PRO_IDS = new Set([0x00a7, 0x00a8]);

function findNaga() {
  const devices = listDevices();
  const naga = devices.find(d => NAGA_V2_PRO_IDS.has(d.productId));
  if (!naga) throw new Error('Naga V2 Pro (productId 0x00A7 or 0x00A8) not found');
  return naga.internalDeviceId;
}

function probeSetProfile() {
  const id = findNaga();
  const readAllSlots = (tag) => {
    const readings = [1, 2, 3, 4, 5].map(s => {
      const r = addon.mouseGetDpiProfile(id, s);
      return `slot${s}=${r.x}`;
    });
    console.log(`  ${tag}: ${readings.join(', ')}`);
  };

  console.log('Probe 1: SET_PROFILE active-slot verification');
  console.log('Baseline (no intervention):');
  console.log('  getActiveProfile():', addon.mouseGetActiveProfile(id));
  console.log('  standard mouseGetDpi():', addon.mouseGetDpi(id));
  readAllSlots('per-slot reads');

  // Slot 2 intentionally skipped per user's hardware constraint.
  for (const target of [3, 4, 5, 1]) {
    console.log(`\nSET_PROFILE(${target}):`);
    addon.mouseSetActiveProfile(id, target);
    console.log('  getActiveProfile():', addon.mouseGetActiveProfile(id));
    console.log('  standard mouseGetDpi():', addon.mouseGetDpi(id));
    readAllSlots('per-slot reads');
  }
}

const PROBES = {
  list: () => { listDevices(); },
  'set-profile': probeSetProfile,
};

function main() {
  const name = process.argv[2];
  if (!name || !PROBES[name]) {
    console.error(`Unknown probe: ${name}`);
    console.error(`Available: ${Object.keys(PROBES).join(', ')}`);
    process.exit(1);
  }
  PROBES[name]();
}

main();

module.exports = { findNaga, PROBES };
