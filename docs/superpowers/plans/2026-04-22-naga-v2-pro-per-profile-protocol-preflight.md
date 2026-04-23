# Naga V2 Pro Per-Profile Protocol — Preflight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Phases 1 and 2 of the per-profile protocol spec — decode existing USB captures and run on-device probes — to produce a confirmed per-sub-problem fork decision for the Phase 3 rewrite.

**Architecture:** Two sequential phases. Phase 1 is pure investigation from captures (no hardware): build a Razer-report decoder, run it against the pcapng and the extracted packet data in `analyze_profile_switches.py`, produce working protocol notes with fork predictions. Phase 2 verifies against live hardware: a Node.js probe script that drives the existing addon bindings in controlled sequences, observes responses and visible side effects, confirms or revises the predictions. Output of this plan is `docs/naga-v2-pro-protocol-notes.md` containing decoded Synapse traffic plus probe findings, with an explicit "Fork Decision" section per sub-problem (DPI, buttons, active-profile indexing, mirror logic). That document feeds the follow-up rewrite plan written after this one completes.

**Tech Stack:** Python 3 (capture decoding, reusing the existing `captures/*.py` script conventions), Node.js (probe script using the existing `src/driver/index.js` → `build/Release/addon.node` bindings), no new dependencies. The Naga V2 Pro must be physically connected during Phase 2.

**Spec:** `docs/superpowers/specs/2026-04-22-naga-v2-pro-per-profile-protocol-design.md`

**Preconditions:**
- Naga V2 Pro connected via USB (required for Phase 2; not required for Phase 1).
- The C addon already built (`yarn` has been run once; `build/Release/addon.node` exists). If not: `yarn && yarn rebuild` — requires Node 16 per `.nvmrc`.
- Python 3 available (`python3 --version` succeeds).

**Hardware constraint (user-set):** Slot 2 must NOT be written to or left as the active slot during probes. Probes may READ slot 2 (non-destructive) to establish baseline state, but any iteration that issues `SET_PROFILE` or writes DPI / button mappings must skip slot 2. Slots 1, 3, 4, 5 are available for testing. Every probe in Phase 2 is written with this constraint applied.

**Hardware constraint (user-set, added 2026-04-22 during Phase 2):** Mouse must stay usable throughout probing.
- DPI writes must use reasonable values (around 6400); no writing values like 1111/1333 that leave the pointer crawling.
- Button-mapping probes must NOT write to the primary click buttons. Button id `0x01` is the primary/left click on the main mouse body; ids `0x40–0x4b` (12-button side panel), `0x50–0x55` (6-button side panel), `0x04`, `0x05` (2-button side panel) are the side-panel buttons and are the only safe targets.
- Any probe that mutates DPI or button mappings must end with a restore step (set DPI to 6400 on active slot; restore touched button ids to their default left-click mapping).

---

## Phase 1 — Capture Analysis

### Task 1.1: Razer report decoder module

**Files:**
- Create: `captures/razer_report_decoder.py`

- [ ] **Step 1: Create the decoder module**

```python
#!/usr/bin/env python3
"""Razer report decoder — parses 90-byte Razer HID reports into structured records.

Report layout (per openrazer):
  byte 0      status
  byte 1      transaction_id
  bytes 2-3   remaining_packets (big-endian u16)
  byte 4      protocol_type
  byte 5      data_size
  byte 6      command_class
  byte 7      command_id
  bytes 8-87  arguments (80 bytes)
  byte 88     crc
  byte 89     reserved
"""

from dataclasses import dataclass
from typing import Optional

# Command-name lookup keyed on (class, cmd). Populated from our C driver and
# razerchromacommon.c; extended as we decode unknowns. A None value means "observed
# in traffic but semantics not yet confirmed".
COMMAND_NAMES = {
    (0x00, 0x85): None,  # observed in captures, unknown
    (0x04, 0x05): "SET_DPI (class=04 cmd=05)",
    (0x04, 0x06): "SET_DPI_STAGES (class=04 cmd=06)",
    (0x04, 0x85): "GET_DPI (class=04 cmd=85)",
    (0x04, 0x86): "GET_DPI_STAGES_OR_PROFILE (class=04 cmd=86)",
    (0x05, 0x02): None,  # observed preceding per-slot writes, unknown
    (0x05, 0x03): "SET_ACTIVE_PROFILE (class=05 cmd=03)",
    (0x05, 0x08): None,  # observed as multi-packet, unknown (likely profile metadata)
    (0x05, 0x82): "GET_ACTIVE_PROFILE (class=05 cmd=82)",
    (0x06, 0x8e): "MACRO_CLEAR (class=06 cmd=8e)",
    (0x0f, 0x80): None,  # observed at startup, unknown
    (0x15, 0x80): None,  # observed in flows, unknown
}


@dataclass
class RazerReport:
    status: int
    transaction_id: int
    remaining_packets: int
    protocol_type: int
    data_size: int
    command_class: int
    command_id: int
    arguments: bytes  # 80 bytes
    crc: int
    reserved: int

    @property
    def name(self) -> str:
        key = (self.command_class, self.command_id)
        named = COMMAND_NAMES.get(key)
        if named:
            return named
        return f"UNKNOWN class=0x{self.command_class:02x} cmd=0x{self.command_id:02x}"

    def args_hex(self, n: int = 8) -> str:
        return self.arguments[:n].hex()

    def summary(self) -> str:
        return (
            f"class=0x{self.command_class:02x} cmd=0x{self.command_id:02x} "
            f"size={self.data_size} args={self.args_hex(self.data_size)} "
            f"| {self.name}"
        )


def parse_hex(hex_str: str) -> Optional[RazerReport]:
    """Parse a 180-hex-char (90-byte) Razer report. Returns None if malformed."""
    hex_str = hex_str.strip().replace(" ", "")
    if len(hex_str) != 180:
        return None
    data = bytes.fromhex(hex_str)
    return RazerReport(
        status=data[0],
        transaction_id=data[1],
        remaining_packets=int.from_bytes(data[2:4], "big"),
        protocol_type=data[4],
        data_size=data[5],
        command_class=data[6],
        command_id=data[7],
        arguments=data[8:88],
        crc=data[88],
        reserved=data[89],
    )
```

- [ ] **Step 2: Verify the decoder against a known packet**

Run:
```bash
python3 -c "
from captures.razer_report_decoder import parse_hex
r = parse_hex('000e00000001050303' + '00' * 80 + '0400')
print(r.summary())
assert r.command_class == 0x05 and r.command_id == 0x03 and r.arguments[0] == 0x03
print('OK')
"
```

Expected output includes `class=0x05 cmd=0x03 size=1 args=03 | SET_ACTIVE_PROFILE (class=05 cmd=03)` and `OK`.

- [ ] **Step 3: Commit**

```bash
git add captures/razer_report_decoder.py
git commit -m "chore(captures): add Razer report decoder for protocol analysis"
```

---

### Task 1.2: Decode the profile-switch sequence

**Files:**
- Create: `captures/decode_profile_switch.py`
- Output: `docs/naga-v2-pro-protocol-notes.md` (append; created in Task 1.7 but start populating now)

- [ ] **Step 1: Create the decoder wrapper that reads the existing extracted data**

```python
#!/usr/bin/env python3
"""Decode the profile-switch traffic extracted in analyze_profile_switches.py.

Produces a human-readable timeline of every Razer report in the switch flow.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from razer_report_decoder import parse_hex

# Import the raw data block from the existing script
import importlib.util
spec = importlib.util.spec_from_file_location(
    "_aps", os.path.join(os.path.dirname(__file__), "analyze_profile_switches.py")
)
_aps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_aps)

RAW = _aps.RAW_DATA.strip().splitlines()

print(f"{'time(s)':>10}  {'summary'}")
print("-" * 100)
for line in RAW:
    parts = line.strip().split(None, 1)
    if len(parts) != 2:
        continue
    ts_ns, hex_pkt = parts
    try:
        ts = float(ts_ns) if "." in ts_ns else int(ts_ns) / 1e9
    except ValueError:
        continue
    rpt = parse_hex(hex_pkt)
    if rpt is None:
        continue
    print(f"{ts:>10.3f}  {rpt.summary()}")
```

- [ ] **Step 2: Run the decoder and capture output**

Run:
```bash
python3 captures/decode_profile_switch.py | tee /tmp/profile-switch-decoded.txt
```

Expected: a timeline of decoded reports with timestamps and command names. Confirm the output contains at least one `SET_ACTIVE_PROFILE` and one `MACRO_CLEAR`.

- [ ] **Step 3: Manually walk the timeline and identify the profile-switch pattern**

Read `/tmp/profile-switch-decoded.txt`. Identify the commands Synapse sends specifically when switching profiles (as opposed to startup chatter or DPI-stage reconfiguration). Expected pattern (hypothesis from session report):

```
SET_ACTIVE_PROFILE(N) → MACRO_CLEAR
```

— but note any additional commands surrounding it. Write this observed pattern in a scratch note at `/tmp/phase1-observations.md` for later consolidation in Task 1.7.

- [ ] **Step 4: Commit**

```bash
git add captures/decode_profile_switch.py
git commit -m "chore(captures): add profile-switch decoder"
```

---

### Task 1.3: Extract and decode DPI-change sequences from the pcapng

**Files:**
- Create: `captures/extract_dpi_changes.py`

- [ ] **Step 1: Check whether tshark is available**

Run: `which tshark && tshark --version | head -1`

If missing, install: `brew install wireshark` (CLI only works via `brew install --cask wireshark` for Wireshark.app, but `brew install wireshark` gives tshark). If you can't install tshark on this machine, skip to Step 3 (work from `analyze_profile_switches.py` data only and document the gap in `/tmp/phase1-observations.md`).

- [ ] **Step 2: Create the extraction script**

```python
#!/usr/bin/env python3
"""Extract DPI-related packets from the Naga V2 Pro capture.

Filters for class=0x04 (DPI family) reports in both directions.
Prints timeline with decoded summaries.
"""

import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from razer_report_decoder import parse_hex

PCAP = os.path.join(os.path.dirname(__file__), "razer-naga-pannel-swaps.pcapng")
TSHARK = "tshark"

# usb.capdata is the raw HID payload. Filter by length==180 hex chars (90 bytes)
# to catch only Razer reports, and by byte offset 6 == 0x04 to catch DPI class.
cmd = [
    TSHARK, "-r", PCAP, "-T", "fields",
    "-e", "frame.time_relative",
    "-e", "usb.capdata",
    "-Y", "usb.capdata",
]
proc = subprocess.run(cmd, check=True, capture_output=True, text=True)

print(f"{'time(s)':>10}  {'summary'}")
print("-" * 100)
for line in proc.stdout.splitlines():
    parts = line.strip().split("\t")
    if len(parts) != 2:
        continue
    ts, hex_pkt = parts
    hex_pkt = hex_pkt.replace(":", "").replace(",", "").strip()
    rpt = parse_hex(hex_pkt)
    if rpt is None or rpt.command_class != 0x04:
        continue
    try:
        ts_f = float(ts)
    except ValueError:
        continue
    print(f"{ts_f:>10.3f}  {rpt.summary()}")
```

- [ ] **Step 3: Run it and record findings**

Run:
```bash
python3 captures/extract_dpi_changes.py | tee /tmp/dpi-changes-decoded.txt
```

Expected: a list of `0x04:0x05` (SET_DPI), `0x04:0x06` (SET_DPI_STAGES), `0x04:0x85`/`0x04:0x86` (reads) with their `arg[0]` values.

Manually examine. For each SET_DPI (`0x04:0x05`), note: what was `arg[0]`? Did Synapse precede it with a `0x05:0x02` or `0x05:0x03`? What's the time gap? Record findings in `/tmp/phase1-observations.md`.

If tshark was unavailable in Step 1, mark this task's findings as "pcapng-derived portion deferred; captured-sequence evidence for DPI limited to the subset present in analyze_profile_switches.py" in `/tmp/phase1-observations.md`, and move on.

- [ ] **Step 4: Commit**

```bash
git add captures/extract_dpi_changes.py
git commit -m "chore(captures): add DPI-change extractor from pcapng"
```

---

### Task 1.4: Extract and decode button-remap sequences from the pcapng

**Files:**
- Create: `captures/extract_button_remap.py`

- [ ] **Step 1: Create the extractor**

```python
#!/usr/bin/env python3
"""Extract button-mapping (class=0x02) traffic from the Naga V2 Pro capture."""

import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from razer_report_decoder import parse_hex

PCAP = os.path.join(os.path.dirname(__file__), "razer-naga-pannel-swaps.pcapng")
TSHARK = "tshark"

cmd = [
    TSHARK, "-r", PCAP, "-T", "fields",
    "-e", "frame.time_relative",
    "-e", "usb.capdata",
    "-Y", "usb.capdata",
]
proc = subprocess.run(cmd, check=True, capture_output=True, text=True)

# Class 0x02 = button-mapping in our driver (BUTTON_MAPPING_SET / GET)
# Also include class 0x05 (profile) for context; useful to see preambles.
RELEVANT = {0x02, 0x05, 0x06}

print(f"{'time(s)':>10}  {'summary'}")
print("-" * 100)
for line in proc.stdout.splitlines():
    parts = line.strip().split("\t")
    if len(parts) != 2:
        continue
    ts, hex_pkt = parts
    hex_pkt = hex_pkt.replace(":", "").replace(",", "").strip()
    rpt = parse_hex(hex_pkt)
    if rpt is None or rpt.command_class not in RELEVANT:
        continue
    try:
        ts_f = float(ts)
    except ValueError:
        continue
    print(f"{ts_f:>10.3f}  {rpt.summary()}")
```

- [ ] **Step 2: Run it and record findings**

Run:
```bash
python3 captures/extract_button_remap.py | tee /tmp/button-remap-decoded.txt
```

Manually examine the output. For each SET_BUTTON_MAPPING (`0x02:0x0d` is our driver's write command; verify command_id in the capture), note the `arg[0]` value and whether it's preceded by `0x05:0x02` or `0x05:0x03`. Record in `/tmp/phase1-observations.md`.

If tshark unavailable, note the gap as in Task 1.3 Step 3.

- [ ] **Step 3: Commit**

```bash
git add captures/extract_button_remap.py
git commit -m "chore(captures): add button-remap extractor from pcapng"
```

---

### Task 1.5: Identify and label unknown commands

**Files:**
- Modify: `captures/razer_report_decoder.py` (update `COMMAND_NAMES` with findings)

- [ ] **Step 1: Catalogue unknowns from previous tasks**

Open `/tmp/profile-switch-decoded.txt`, `/tmp/dpi-changes-decoded.txt`, and `/tmp/button-remap-decoded.txt`. List every `UNKNOWN class=0x? cmd=0x?` combination observed.

For each one, note in `/tmp/phase1-observations.md`:
- The `(class, cmd)` pair
- Observed `data_size`s
- Observed `arg[0..N]` value ranges
- Direction (request from host vs response from device — status byte 0x00 typically host→device, 0x02 device→host, verify by context)
- Immediate surrounding commands (what preceded it, what followed)
- Best-guess semantic label

Specific unknowns flagged in the spec to resolve:
- `0x05:0x02` — hypothesis: SELECT_PROFILE_CONTEXT (opens a write scope for per-slot operations without changing the user-visible active profile).
- `0x05:0x08` — hypothesis: PROFILE_METADATA (multi-packet with name/uuid string, data_size=0x45 observed).
- `0x00:0x85` — hypothesis: unknown read; observed responding to a 0x05:0x08 sequence.
- `0x15:0x80` — hypothesis: unknown; observed surrounding profile-switch.

- [ ] **Step 2: Update `COMMAND_NAMES` in the decoder**

Edit `captures/razer_report_decoder.py`. Replace `None` entries with labels where hypotheses are strong enough to name (e.g., `(0x05, 0x02): "SELECT_PROFILE_CONTEXT (hypothesized)"`). Leave `None` for commands still genuinely unknown.

- [ ] **Step 3: Re-run the three decoders to confirm names flow through**

```bash
python3 captures/decode_profile_switch.py | head -30
python3 captures/extract_dpi_changes.py 2>/dev/null | head -10 || echo "tshark unavailable, skipped"
python3 captures/extract_button_remap.py 2>/dev/null | head -10 || echo "tshark unavailable, skipped"
```

Expected: hypothesized labels now appear in the output.

- [ ] **Step 4: Commit**

```bash
git add captures/razer_report_decoder.py
git commit -m "chore(captures): label observed Naga V2 Pro commands with hypotheses"
```

---

### Task 1.6: Inspect the Synapse config export

**Files:**
- Input: `docs/profiles - 1774992262695.synapse4` (existing)

- [ ] **Step 1: Verify the file is JSON and dump its top-level structure**

Run:
```bash
python3 -c "
import json
with open('docs/profiles - 1774992262695.synapse4') as f:
    data = json.load(f)
print('keys:', list(data.keys()))
print('productId:', data.get('productId'))
print('profiles:', len(data.get('profiles', [])))
for i, p in enumerate(data.get('profiles', [])[:5]):
    print(f'  profile[{i}] keys:', list(p.keys()))
"
```

Expected output confirms it is a JSON Synapse configuration export. Capture the structure: profile count, per-profile keys (name/uuid/dpi/buttons/etc).

- [ ] **Step 2: Record findings**

Append to `/tmp/phase1-observations.md` a short note: "Synapse config export is JSON. Top-level keys: [...]. Per-profile shape: [...]. Useful for interpreting capture (e.g., a profile name observed in `0x05:0x08` payload can be cross-referenced here)."

No code changes; this is purely a sanity check.

- [ ] **Step 3: No commit needed** — observations feed Task 1.7.

---

### Task 1.7: Write working protocol notes with fork predictions

**Files:**
- Create: `docs/naga-v2-pro-protocol-notes.md`

- [ ] **Step 1: Consolidate `/tmp/phase1-observations.md` into the working notes**

Create `docs/naga-v2-pro-protocol-notes.md` using the structure below. **Replace every `<...>` marker with concrete content derived from your observations.** Do not commit with any `<...>` markers or `TBD`/`TODO` in the text. For any section where observations are genuinely absent (e.g., tshark was unavailable and that section is deferred), write the explicit deferral sentence in place of `<...>`.

```markdown
# Naga V2 Pro Protocol Notes (Working)

**Status:** Phase 1 complete. Preflight findings below. Phase 2 probes pending.

## Source data
- USB capture: `captures/razer-naga-pannel-swaps.pcapng` (~52 MB)
- Extracted profile-switch packets: `captures/analyze_profile_switches.py`
- Synapse config export (JSON, not a capture): `docs/profiles - 1774992262695.synapse4`

## Command inventory

| (class, cmd) | data_size range | observed arg[0] | label | notes |
|--------------|------------------|-----------------|-------|-------|
| (0x04, 0x05) | 0x07 | ... | SET_DPI | ... |
| (0x04, 0x06) | 0x26 | ... | SET_DPI_STAGES | ... |
| (0x04, 0x86) | 0x50 / 0x26 | ... | GET_DPI_STAGES_OR_PROFILE | ... |
| (0x05, 0x02) | 0x01 | ... | SELECT_PROFILE_CONTEXT (hypothesized) | ... |
| (0x05, 0x03) | 0x01 | ... | SET_ACTIVE_PROFILE | ... |
| (0x05, 0x08) | 0x45 | ... | PROFILE_METADATA (hypothesized) | ... |
| (0x05, 0x82) | 0x01 | ... | GET_ACTIVE_PROFILE | ... |
| (0x06, 0x8e) | 0x0e | ... | MACRO_CLEAR | ... |
| ... | | | | |

## Observed Synapse flows

### Profile switch (slot A → slot B)
<sequence decoded from analyze_profile_switches.py>

### DPI change on profile N
<sequence from /tmp/dpi-changes-decoded.txt, or "not available without tshark">

### Button remap on profile N
<sequence from /tmp/button-remap-decoded.txt, or "not available without tshark">

## Fork predictions (to be confirmed in Phase 2)

### Sub-problem: DPI
- Prediction: Fork A (`arg[0]` is VARSTORE/NOSTORE, not a slot) OR Fork B (`arg[0]` is a slot, requires `0x05:0x02` preamble).
- Evidence: <cite observed Synapse flow>
- Phase 2 probes that will confirm: 2.4 (SET_DPI arg[0] semantics).

### Sub-problem: Button mapping
- Prediction: <Fork A / Fork B>
- Evidence: <cite>
- Phase 2 probes that will confirm: 2.5.

### Sub-problem: Active profile indexing
- Prediction: <0-indexed hardware / wrong-command-id>
- Evidence: <cite>
- Phase 2 probes that will confirm: 2.3.

### Sub-problem: Mirror-to-slot-1
- Prediction: removable in both forks.
- Evidence: once underlying read/write is honest, mirror is actively harmful.
- Phase 2 probes that will confirm: indirectly by 2.2 and 2.4.

## Still-unknown commands
<list (class, cmd) pairs that remain unlabeled>
```

- [ ] **Step 2: Verify no placeholders remain**

Run:

```bash
grep -nE '<[A-Za-z]|TBD|TODO' docs/naga-v2-pro-protocol-notes.md && { echo "Placeholders remain — fix before commit"; exit 1; } || echo "Clean."
```

Expected: `Clean.` Additionally, each of DPI / Buttons / Active-profile indexing / Mirror logic must have a stated prediction (even "Fork A, medium confidence" is fine). The prediction may be wrong; Phase 2 exists to verify. If any sub-problem lacks a prediction, write one based on best available evidence, then re-run the grep.

- [ ] **Step 3: Commit**

```bash
git add docs/naga-v2-pro-protocol-notes.md
git commit -m "docs: Naga V2 Pro protocol notes — Phase 1 (capture analysis) findings"
```

---

## Phase 2 — On-Device Probes

### Task 2.1: Probe script skeleton

**Files:**
- Create: `scripts/probes/naga-v2-pro-probe.js`

- [ ] **Step 1: Create the script with a CLI wrapper and a list-device sanity check**

```javascript
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

const addon = require('../../src/driver');

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

const PROBES = {
  list: () => { listDevices(); },
  // Other probes registered by subsequent tasks
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
```

- [ ] **Step 2: Run the sanity check**

Run:
```bash
node scripts/probes/naga-v2-pro-probe.js list
```

Expected: at least one device listed with `pid=0xa7` (Naga V2 Pro wired) or `pid=0xa8` (wireless). If the list is empty, the device is not connected or the addon is not built; resolve before proceeding (run `yarn rebuild`).

- [ ] **Step 3: Commit**

```bash
git add scripts/probes/naga-v2-pro-probe.js
git commit -m "chore(probes): Naga V2 Pro probe script skeleton"
```

---

### Task 2.2: Probe 1 — SET_PROFILE active-slot verification

**Files:**
- Modify: `scripts/probes/naga-v2-pro-probe.js`

- [ ] **Step 1: Add the probe function**

Edit `scripts/probes/naga-v2-pro-probe.js`. After the `listDevices`/`findNaga` block and before `const PROBES = {`, add:

```javascript
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
```

Register it in `PROBES`:

```javascript
const PROBES = {
  list: () => { listDevices(); },
  'set-profile': probeSetProfile,
};
```

- [ ] **Step 2: Run the probe**

Run:
```bash
node scripts/probes/naga-v2-pro-probe.js set-profile 2>&1 | tee /tmp/probe-set-profile.txt
```

Expected: output shows active-profile readings and per-slot DPI readings before and after each SET_PROFILE call.

- [ ] **Step 3: Record findings in the protocol notes**

Append to `docs/naga-v2-pro-protocol-notes.md` under a new section `## Phase 2 — On-device probe findings`:

```markdown
### Probe 1: SET_PROFILE active-slot verification

Ran: `node scripts/probes/naga-v2-pro-probe.js set-profile`
Output: `/tmp/probe-set-profile.txt` (reproduce the salient lines inline).

Findings:
- Does `mouseGetDpi` (standard VARSTORE read) return a different value after `SET_PROFILE(N)`? <yes/no>
- Does `mouseGetActiveProfile` match the slot we just set? <yes, matches / no, returns X>
- If per-slot reads (`mouseGetDpiProfile`) return garbage, confirm that matches the session report finding.

Implication for DPI fork:
<Fork A evidence / Fork B evidence>
```

- [ ] **Step 4: Commit**

```bash
git add scripts/probes/naga-v2-pro-probe.js docs/naga-v2-pro-protocol-notes.md
git commit -m "chore(probes): probe 1 — SET_PROFILE active-slot verification"
```

---

### Task 2.3: Probe 2 — GET_ACTIVE_PROFILE semantics

**Files:**
- Modify: `scripts/probes/naga-v2-pro-probe.js`

- [ ] **Step 1: Add the probe**

In `scripts/probes/naga-v2-pro-probe.js`, add:

```javascript
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
```

Register in `PROBES`: `'get-active': probeGetActive,`.

- [ ] **Step 2: Run it**

```bash
node scripts/probes/naga-v2-pro-probe.js get-active 2>&1 | tee /tmp/probe-get-active.txt
```

Expected: five lines showing whether the return value matches the slot we set.

- [ ] **Step 3: Record findings**

Append to `docs/naga-v2-pro-protocol-notes.md` under Phase 2:

```markdown
### Probe 2: GET_ACTIVE_PROFILE semantics

Output: `/tmp/probe-get-active.txt`

Findings:
- At rest: <value>
- After SET_PROFILE(N), return value: <matches N exactly / N-1 (0-indexed) / unrelated>

Implication for active-profile-indexing fork:
- If consistently N-1: 0-indexed hardware; normalize +1/-1 at device layer boundary.
- If consistently N: command is correct; Finding 1's "returned 0 at rest" means the device starts without a user-selected profile (slot 0 = "no profile" or similar sentinel).
- If unrelated: wrong command ID; investigate alternatives (e.g., 0x05:0x84).
```

- [ ] **Step 4: Commit**

```bash
git add scripts/probes/naga-v2-pro-probe.js docs/naga-v2-pro-protocol-notes.md
git commit -m "chore(probes): probe 2 — GET_ACTIVE_PROFILE semantics"
```

---

### Task 2.4: Probe 3 — SET_DPI arg[0] semantics

**Files:**
- Modify: `scripts/probes/naga-v2-pro-probe.js`

- [ ] **Step 1: Add the probe**

```javascript
function probeSetDpiArgs() {
  const id = findNaga();
  console.log('Probe 3: SET_DPI arg[0] semantics');
  console.log('Strategy: for each arg[0] in {1..5}, write a distinctive DPI value, read back via');
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
    [1, 2, 3, 4, 5].forEach(s => {
      // Reads across all 5 slots (including 2) are non-destructive and valuable for baseline evidence.
      const r = addon.mouseGetDpiProfile(id, s);
      console.log(`  per-slot getDpiProfile(${s}): x=${r.x}`);
    });

    console.log(`\nB. SET_PROFILE(${slotArg}) + mouseSetDpiProfile(slotArg=${slotArg}, dpi=${marker + 10})`);
    addon.mouseSetActiveProfile(id, slotArg);
    const marker2 = marker + 10;
    addon.mouseSetDpiProfile(id, slotArg, marker2, marker2);
    console.log(`  standard mouseGetDpi (currently active slot): ${addon.mouseGetDpi(id)}`);
    [1, 2, 3, 4, 5].forEach(s => {
      const r = addon.mouseGetDpiProfile(id, s);
      console.log(`  per-slot getDpiProfile(${s}): x=${r.x}`);
    });
  }

  // Verify cross-slot retention: iterate SET_PROFILE (skipping slot 2), did the marker writes persist?
  console.log('\nFinal cross-slot retention check (slot 2 skipped):');
  for (const s of [1, 3, 4, 5]) {
    addon.mouseSetActiveProfile(id, s);
    console.log(`  After SET_PROFILE(${s}): standard mouseGetDpi = ${addon.mouseGetDpi(id)}`);
  }
}
```

Register: `'set-dpi-args': probeSetDpiArgs,`.

- [ ] **Step 2: Run it**

```bash
node scripts/probes/naga-v2-pro-probe.js set-dpi-args 2>&1 | tee /tmp/probe-set-dpi-args.txt
```

Expected: a large trace. This probe may change the mouse's DPI visibly — that's fine, we'll reset in Task 2.8.

- [ ] **Step 3: Record findings**

Append to notes:

```markdown
### Probe 3: SET_DPI arg[0] semantics

Output: `/tmp/probe-set-dpi-args.txt`

Key questions answered:
- Writes with `slotArg=1` (which happens to equal VARSTORE=0x01): persist on the active slot? <yes/no>
- Writes with `slotArg ∈ {2..5}` without prior SET_PROFILE: persist anywhere? <yes, on slot N / yes, on active slot / no>
- Writes with `slotArg ∈ {2..5}` after SET_PROFILE(slotArg): persist on slot N? <yes/no>
- Final retention check: when iterating SET_PROFILE through 1..5, do the markers survive?

Fork determination for DPI:
- If writes only persist when `slotArg == VARSTORE (=1)` or `slotArg == currently active slot`: FORK A.
- If writes with `slotArg=N` after `SET_PROFILE(N)` persist: FORK B (arg[0] IS a slot, but device uses active-context routing).
- If writes persist for any `slotArg` regardless of SET_PROFILE: unexpected — document and reconsider.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/probes/naga-v2-pro-probe.js docs/naga-v2-pro-protocol-notes.md
git commit -m "chore(probes): probe 3 — SET_DPI arg[0] semantics"
```

---

### Task 2.5: Probe 4 — button-mapping write arg[0] semantics

**Files:**
- Modify: `scripts/probes/naga-v2-pro-probe.js`

- [ ] **Step 1: Add the probe**

```javascript
function probeSetBtnArgs() {
  const id = findNaga();
  console.log('Probe 4: button-mapping write arg[0] semantics');
  console.log('Strategy: same shape as probe 3, but with button-mapping writes.');

  // Pick a benign button to test on: button 0x01 (typical "left click" equivalent in the protocol; adjust if panelType suggests another safe id).
  const BTN = 0x01;
  const LAYER = 0x00;
  const ACTION_TYPE = 0x01;  // "mouse button" or similar — we only care about round-tripping
  // Distinctive parameter bytes per slot so we can identify persistence.
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
```

Register: `'set-btn-args': probeSetBtnArgs,`.

- [ ] **Step 2: Run it**

```bash
node scripts/probes/naga-v2-pro-probe.js set-btn-args 2>&1 | tee /tmp/probe-set-btn-args.txt
```

- [ ] **Step 3: Record findings**

Append to notes in the same shape as probe 3, answering:
- Writes with `slotArg=1` (no preamble): persist?
- Writes with `slotArg ∈ {2..5}` (no preamble): persist? Where?
- Writes with `slotArg ∈ {2..5}` (with preamble): persist on slot N?

Fork determination for button-mapping:
- Fork A (arg[0] is a flag; slot addressing via SET_PROFILE): if writes only persist on active slot.
- Fork B (arg[0] is a real slot): if SET_PROFILE + write-to-slotArg works reliably.

- [ ] **Step 4: Commit**

```bash
git add scripts/probes/naga-v2-pro-probe.js docs/naga-v2-pro-protocol-notes.md
git commit -m "chore(probes): probe 4 — button-mapping write arg[0] semantics"
```

---

### Task 2.6: Probe 6 — GET_DPI read variants

**Files:**
- Modify: `scripts/probes/naga-v2-pro-probe.js`

- [ ] **Step 1: Add the probe**

```javascript
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
```

Register: `'read-variants': probeReadVariants,`.

- [ ] **Step 2: Run it**

```bash
node scripts/probes/naga-v2-pro-probe.js read-variants 2>&1 | tee /tmp/probe-read-variants.txt
```

- [ ] **Step 3: Record findings**

Append to notes:

```markdown
### Probe 6: GET_DPI read variants

Output: `/tmp/probe-read-variants.txt`

Findings:
- Does `mouseGetDpi` always agree with `mouseGetDpiProfile(active)`? <yes/no>
- Does `mouseGetDpiProfile(slot != active)` return:
  - The DPI value stored for that slot? — Fork B evidence (real per-slot read).
  - Garbage / stage metadata (~0x0505, 0x0405)? — Fork A evidence; the current `0x04:0x86` command is not a per-slot DPI read.
  - Identical value to the active-slot DPI? — Fork A evidence; command ignores the slot arg and returns active-slot DPI.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/probes/naga-v2-pro-probe.js docs/naga-v2-pro-protocol-notes.md
git commit -m "chore(probes): probe 6 — GET_DPI read variants"
```

---

### Task 2.7: Probe 5 — side-effect observation (interactive, user-run)

**Files:**
- Modify: `scripts/probes/naga-v2-pro-probe.js`

- [ ] **Step 1: Add the interactive probe**

```javascript
function probeSideEffects() {
  const id = findNaga();
  console.log('Probe 5: side-effect observation');
  console.log('INSTRUCTIONS: watch the mouse LEDs and profile indicator during this probe.');
  console.log('Note any visible changes (LED blink, color change, lighting reset, indicator number change).');
  console.log('After each action, press ENTER to continue.\n');

  const wait = () => new Promise(r => process.stdin.once('data', () => r()));

  (async () => {
    const wasActive = addon.mouseGetActiveProfile(id);
    console.log(`Starting active profile: ${wasActive}. Press ENTER to begin.`);
    await wait();

    // Slot 2 intentionally skipped per user's hardware constraint.
    for (const target of [1, 3, 4, 5]) {
      console.log(`\nAbout to SET_PROFILE(${target}). Watch the mouse. Press ENTER.`);
      await wait();
      addon.mouseSetActiveProfile(id, target);
      console.log(`  Sent. Observed side effects? Type note, press ENTER.`);
      await wait();
    }

    console.log('\nAbout to send mouseMacroClear. Watch the mouse. Press ENTER.');
    await wait();
    addon.mouseMacroClear(id);
    console.log('  Sent. Observed? Press ENTER.');
    await wait();

    console.log('\nProbe complete. Restoring original profile.');
    addon.mouseSetActiveProfile(id, wasActive);
    process.exit(0);
  })();
}
```

Register: `'side-effects': probeSideEffects,`.

- [ ] **Step 2: Run it (user must be present)**

```bash
node scripts/probes/naga-v2-pro-probe.js side-effects
```

This is **interactive** and requires the user to observe the mouse. The executor agent cannot complete this probe alone — prompt the user to run it and report back what they see.

- [ ] **Step 3: Record findings**

Append to notes:

```markdown
### Probe 5: Side-effect observation (user-reported)

- SET_PROFILE(N) visible effects: <e.g., "profile indicator on right side of mouse switches to show the number N", "no LED change", "lighting briefly blinks">
- MACRO_CLEAR visible effects: <e.g., "no visible effect">
- Audible side effects (clicks from mouse): <yes/no>
- Duration of any animation: <seconds>
- Delay / lag in the mouse responding to subsequent commands: <yes/no>

Implication for architecture:
- If SET_PROFILE is visibly noisy: reinforce the "track active slot locally, gate SET_PROFILE on mismatch" strategy; consider batching.
- If silent: simpler implementation is fine.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/probes/naga-v2-pro-probe.js docs/naga-v2-pro-protocol-notes.md
git commit -m "chore(probes): probe 5 — side-effect observation (user-run)"
```

---

### Task 2.8: Consolidate findings, confirm fork decisions, restore state

**Files:**
- Modify: `docs/naga-v2-pro-protocol-notes.md`

- [ ] **Step 1: Restore mouse to a clean state**

The probes have written test DPI values and button mappings across slots 1, 3, 4, 5. Slot 2 was preserved per the hardware constraint and does not need restoration. Restore the other slots:

```bash
node scripts/probes/naga-v2-pro-probe.js list  # confirm device still detected
# Manually: open the app, select each of slots 1, 3, 4, 5, and re-apply the user's desired DPI and button mappings.
# Alternatively, if the user has a Synapse config to restore from, do that.
# SET_PROFILE(2) is safe to issue now if the user wants to return to slot 2 as the active profile.
```

Ask the user to confirm the mouse is back to a usable state before moving on.

- [ ] **Step 2: Write the Fork Decisions section**

Append to `docs/naga-v2-pro-protocol-notes.md`:

```markdown
## Fork Decisions (confirmed by Phase 2)

### DPI — Fork A / Fork B
Confirmed: <A or B>.
Key evidence: <probe 3 observation — e.g., "writes with slotArg=N after SET_PROFILE(N) persist; without SET_PROFILE they no-op. arg[0] is effectively required to equal the currently-active slot, which means the active-slot routing is what matters, not arg[0] semantics. Fork A.">
Implication for Phase 3:
- Driver: <delete mouseSetDpiProfile / fix it to use VARSTORE / keep as-is with preamble helper>.
- Device layer: <specific changes>.

### Button mapping — Fork A / Fork B
Confirmed: <A or B>. <evidence>. <implication>.

### Active profile indexing
Confirmed: <0-indexed / 1-indexed / wrong command>. <evidence>. <implication>.

### Mirror-to-slot-1
Confirmed: <removable / must be kept for reason X>. <evidence>.

## Unknown commands still outstanding
<any (class, cmd) pairs still unresolved; flag as deferred to future investigation>

## Ready for Phase 3 (rewrite)
All four sub-problems have confirmed forks. The rewrite plan can be written against these findings.
```

Fill in the `<...>` placeholders with the actual findings. No placeholders allowed at commit time.

- [ ] **Step 3: Verify no placeholders remain**

```bash
grep -nE '<[A-Z]|TBD|TODO|\.\.\.\b' docs/naga-v2-pro-protocol-notes.md && { echo "Placeholders remain — fix before commit"; exit 1; } || echo "Clean."
```

Expected: `Clean.`

- [ ] **Step 4: Commit**

```bash
git add docs/naga-v2-pro-protocol-notes.md
git commit -m "docs: Naga V2 Pro protocol notes — Phase 2 probes + fork decisions"
```

- [ ] **Step 5: Hand off to rewrite plan**

Preflight is complete. The executor should now stop and report back to the user:

> "Preflight complete. Fork decisions:
> - DPI: Fork <X>
> - Buttons: Fork <Y>
> - Active profile indexing: <Z>
> - Mirror logic: <status>
>
> Ready to write the rewrite plan. I will invoke writing-plans again with these confirmed findings as input."

Do NOT begin Phase 3 implementation without a new plan. The spec explicitly states the rewrite plan is written against confirmed forks.

---

## Self-Review Summary

Spec coverage check:
- Phase 1 (capture analysis) → Tasks 1.1–1.7 ✓
- Phase 2 (on-device probes) → Tasks 2.1–2.8 ✓
- Unknown command inventory (`0x05:0x02`, `0x05:0x08`, `0x00:0x85`, `0x15:0x80`) → Task 1.5 ✓
- `.synapse4` inspection → Task 1.6 ✓
- Side-effect observation → Task 2.7 ✓
- Fork decisions per sub-problem → Task 2.8 ✓
- Phase 3 and Phase 4 are explicitly out of scope for this plan — handled in a follow-up plan written after preflight completes.
