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

// Module-scope helper: read per-slot DPI via mouseGetDpiProfile for all 5 slots.
// Prints each reading with the given tag. Non-destructive — reads all 5 even if
// slot 2 is off-limits for writes. Returns nothing.
function readAllDpiSlots(id, tag) {
  const readings = [1, 2, 3, 4, 5].map(s => {
    const r = addon.mouseGetDpiProfile(id, s);
    return `slot${s}=${r.x}`;
  });
  console.log(`  ${tag}: ${readings.join(', ')}`);
}

function probeSetProfile() {
  const id = findNaga();

  console.log('Probe 1: SET_PROFILE active-slot verification');
  console.log('Baseline (no intervention):');
  console.log('  getActiveProfile():', addon.mouseGetActiveProfile(id));
  console.log('  standard mouseGetDpi():', addon.mouseGetDpi(id));
  readAllDpiSlots(id, 'per-slot reads');

  // Slot 2 intentionally skipped per user's hardware constraint.
  for (const target of [3, 4, 5, 1]) {
    console.log(`\nSET_PROFILE(${target}):`);
    addon.mouseSetActiveProfile(id, target);
    console.log('  getActiveProfile():', addon.mouseGetActiveProfile(id));
    console.log('  standard mouseGetDpi():', addon.mouseGetDpi(id));
    readAllDpiSlots(id, 'per-slot reads');
  }
}

function probeGetActive() {
  const id = findNaga();
  console.log('Probe 2: GET_ACTIVE_PROFILE semantics');
  console.log('At rest:', addon.mouseGetActiveProfile(id));
  // Slot 2 intentionally skipped per user's hardware constraint.
  for (const target of [1, 3, 4, 5]) {
    addon.mouseSetActiveProfile(id, target);
    const after = addon.mouseGetActiveProfile(id);
    console.log(`  After SET_PROFILE(${target}): getActive=${after}  (match=${after === target ? 'yes' : 'NO — off by ' + (target - after)})`);
  }
}

function probeSetDpiArgs() {
  const id = findNaga();
  console.log('Probe 3: SET_DPI arg[0] semantics');
  console.log('Strategy: for each arg[0] in {1,3,4,5} (slot 2 skipped), write a distinctive DPI value, read back via');
  console.log('          (a) standard mouseGetDpi on currently-active slot,');
  console.log('          (b) per-slot mouseGetDpiProfile for every slot.');
  console.log('          Also: repeat with SET_PROFILE(arg[0]) issued before the write.');

  // Start from a known active state
  addon.mouseSetActiveProfile(id, 1);
  console.log(`\nInitial state: active=${addon.mouseGetActiveProfile(id)}, standard DPI=${addon.mouseGetDpi(id)}`);

  // Slot 2 intentionally skipped per user's hardware constraint — no writes to slot 2, no SET_PROFILE(2).
  for (const slotArg of [1, 3, 4, 5]) {
    const marker = 1000 + slotArg * 111;  // 1111, 1333, 1444, 1555 — distinctive
    console.log(`\nA. mouseSetDpiProfile(slotArg=${slotArg}, dpi=${marker}) — NO prior SET_PROFILE`);
    addon.mouseSetDpiProfile(id, slotArg, marker, marker);
    console.log(`  standard mouseGetDpi (currently active slot): ${addon.mouseGetDpi(id)}`);
    readAllDpiSlots(id, 'per-slot reads');

    console.log(`\nB. SET_PROFILE(${slotArg}) + mouseSetDpiProfile(slotArg=${slotArg}, dpi=${marker + 10})`);
    addon.mouseSetActiveProfile(id, slotArg);
    const marker2 = marker + 10;
    addon.mouseSetDpiProfile(id, slotArg, marker2, marker2);
    console.log(`  standard mouseGetDpi (currently active slot): ${addon.mouseGetDpi(id)}`);
    readAllDpiSlots(id, 'per-slot reads');
  }

  // Verify cross-slot retention: iterate SET_PROFILE (skipping slot 2), did the marker writes persist?
  console.log('\nFinal cross-slot retention check (slot 2 skipped):');
  for (const s of [1, 3, 4, 5]) {
    addon.mouseSetActiveProfile(id, s);
    console.log(`  After SET_PROFILE(${s}): standard mouseGetDpi = ${addon.mouseGetDpi(id)}`);
  }
}

function probeReadVariants() {
  const id = findNaga();
  console.log('Probe 6: GET_DPI read variants');
  console.log('Strategy: on each active profile, compare mouseGetDpi (standard VARSTORE read) vs');
  console.log('          mouseGetDpiProfile(slot=active) vs mouseGetDpiProfile(slot != active).');

  // Slot 2 intentionally skipped as the SET_PROFILE target per user's hardware constraint.
  // Reads of slot 2 via mouseGetDpiProfile are non-destructive and remain enabled.
  for (const active of [1, 3, 4, 5]) {
    addon.mouseSetActiveProfile(id, active);
    console.log(`\nActive = ${active}:`);
    console.log(`  mouseGetDpi (standard VARSTORE): ${addon.mouseGetDpi(id)}`);
    [1, 2, 3, 4, 5].forEach(s => {
      const r = addon.mouseGetDpiProfile(id, s);
      console.log(`  mouseGetDpiProfile(${s}): x=${r.x} y=${r.y}`);
    });
  }
}

function probeSetBtnArgs() {
  const id = findNaga();
  console.log('Probe 4: button-mapping write arg[0] semantics');
  console.log('Strategy: same shape as probe 3, but with button-mapping writes.');

  // Pick a benign button to test on: button 0x01 — small arbitrary id.
  // Action type 0x01 is typical "mouse button" category; params are just markers.
  const BTN = 0x01;
  const LAYER = 0x00;
  const ACTION_TYPE = 0x01;
  const markerParams = (slot) => [slot, 0xaa, 0xbb, 0xcc, 0xdd, 0xee];

  const readAll = (tag) => {
    console.log(`  ${tag}:`);
    [1, 2, 3, 4, 5].forEach(s => {
      const raw = addon.mouseGetButtonMapping(id, s, BTN, LAYER);
      console.log(`    slot${s}: ${Array.from(raw).slice(0, 10).map(b => b.toString(16).padStart(2, '0')).join(' ')}`);
    });
  };

  addon.mouseSetActiveProfile(id, 1);
  readAll('initial state (active=1)');

  // Slot 2 intentionally skipped per user's hardware constraint — no writes to slot 2, no SET_PROFILE(2).
  for (const slotArg of [1, 3, 4, 5]) {
    console.log(`\nA. mouseSetButtonMapping(slotArg=${slotArg}, params=${markerParams(slotArg)}) — NO prior SET_PROFILE`);
    addon.mouseSetButtonMapping(id, slotArg, BTN, LAYER, ACTION_TYPE, markerParams(slotArg));
    readAll(`after write slotArg=${slotArg} (no preamble)`);

    console.log(`\nB. SET_PROFILE(${slotArg}) + mouseSetButtonMapping(slotArg=${slotArg}, params=${markerParams(slotArg).map(x => x + 1)})`);
    addon.mouseSetActiveProfile(id, slotArg);
    addon.mouseSetButtonMapping(id, slotArg, BTN, LAYER, ACTION_TYPE, markerParams(slotArg).map(x => x + 1));
    readAll(`after write slotArg=${slotArg} (with preamble)`);
  }
}

const PROBES = {
  list: () => { listDevices(); },
  'set-profile': probeSetProfile,
  'get-active': probeGetActive,
  'set-dpi-args': probeSetDpiArgs,
  'set-btn-args': probeSetBtnArgs,
  'read-variants': probeReadVariants,
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
