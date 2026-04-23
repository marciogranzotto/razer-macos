#!/usr/bin/env node
/**
 * Empirically discover GET_ACTIVE_PROFILE on the Naga V2 Pro.
 * Strategy: for each (cmd_id, arg[0]) pair in 0x05 class, baseline response
 * bytes; then call SET_PROFILE(N) for N ∈ {1, 3, 4, 5} (slot 2 skipped per
 * user constraint) and compare responses. Any response whose bytes change
 * in lockstep with SET_PROFILE arg[0] is a candidate.
 */

const addon = require('../../build/Release/addon.node');

function probeResponse(id, cmdClass, cmdId, dataSize, args) {
  const argBuf = new Uint8Array(80);
  for (let i = 0; i < args.length; i++) argBuf[i] = args[i];
  const resp = addon.mouseProbeRaw(id, cmdClass, cmdId, dataSize, argBuf);
  // resp[0] = status; resp[8..87] = args (80 bytes). We care about status + first ~8 bytes of args.
  const status = resp[0];
  const argsPreview = Array.from(resp.slice(8, 16)).map(b => b.toString(16).padStart(2, '0')).join(' ');
  return { status, argsPreview, full: resp };
}

const devices = addon.getAllDevices();
const naga = devices.find(d => d.productId === 0x00a7 || d.productId === 0x00a8);
if (!naga) { console.error('Naga not found'); process.exit(1); }
const id = naga.internalDeviceId;

console.log('Discovery: candidates for GET_ACTIVE_PROFILE (class=0x05)');
console.log('productId=0x' + naga.productId.toString(16));
console.log();

// Collect responses for each active-slot state.
const SLOTS = [1, 3, 4, 5];  // skip slot 2
const results = {};  // results[slot] = { 'cmd_0xNN_arg_0xMM': { status, argsPreview } }

for (const slot of SLOTS) {
  console.log(`Setting active profile to ${slot}...`);
  addon.mouseSetActiveProfile(id, slot);
  // Small settle delay — some devices need a moment.
  const start = Date.now(); while (Date.now() - start < 100) {}

  results[slot] = {};
  for (let cmdId = 0x00; cmdId <= 0xff; cmdId++) {
    // Skip SET_ACTIVE_PROFILE (0x03) — already called above; avoid re-setting.
    if (cmdId === 0x03) continue;
    for (const argVal of [0x00, slot]) {  // try arg[0]=0 and arg[0]=current_slot
      try {
        const key = `cmd_0x${cmdId.toString(16).padStart(2, '0')}_arg_0x${argVal.toString(16).padStart(2, '0')}`;
        const resp = probeResponse(id, 0x05, cmdId, 0x01, [argVal]);
        // Keep only responses with status != 0x05 (FAIL) and status != 0x04 (NOT_SUPPORTED).
        // status=0x02 is SUCCESS in Razer protocol.
        if (resp.status !== 0x05 && resp.status !== 0x04) {
          results[slot][key] = resp;
        }
      } catch (e) {
        // Ignore individual probe failures
      }
    }
  }
  console.log(`  ${Object.keys(results[slot]).length} non-FAIL responses on slot ${slot}`);
}

// Park on slot 1 for safety.
addon.mouseSetActiveProfile(id, 1);

// Compare: for each (cmd, arg) combination seen in all 4 slot states, does the response differ?
console.log();
console.log('=== Candidates (commands whose response changes with active slot) ===');
console.log();

const allKeys = new Set();
for (const slot of SLOTS) for (const k of Object.keys(results[slot])) allKeys.add(k);

const candidates = [];
for (const key of allKeys) {
  const perSlot = SLOTS.map(s => results[s][key]).filter(r => r !== undefined);
  if (perSlot.length !== 4) continue;  // need data for all 4 slots
  const statuses = perSlot.map(r => r.status);
  const previews = perSlot.map(r => r.argsPreview);
  // Interesting if previews differ across slots
  const unique = new Set(previews);
  if (unique.size > 1) {
    candidates.push({ key, previews, statuses });
  }
}

if (candidates.length === 0) {
  console.log('No candidates found. GET_ACTIVE_PROFILE likely does not exist as a standalone query.');
} else {
  for (const c of candidates) {
    console.log(`  ${c.key}`);
    SLOTS.forEach((s, i) => {
      console.log(`    slot=${s}: status=0x${c.statuses[i].toString(16)} args[0..7]=${c.previews[i]}`);
    });
  }
}

// Special focus: does any command's FIRST response arg match the active slot exactly?
console.log();
console.log('=== Commands where response arg[0] (first byte of args section) matches active slot ===');
for (const c of candidates) {
  const firstBytes = c.previews.map(p => parseInt(p.split(' ')[0], 16));
  if (firstBytes[0] === SLOTS[0] && firstBytes[1] === SLOTS[1] && firstBytes[2] === SLOTS[2] && firstBytes[3] === SLOTS[3]) {
    console.log(`  STRONG CANDIDATE: ${c.key}`);
    console.log(`    arg[0] tracks active slot exactly: ${firstBytes.join(',')} for slots ${SLOTS.join(',')}`);
  }
}
