# Safe-rules Freerouting benchmark

> **Benchmark only — do not fabricate this PCB.** The authoritative Rev-A
> board remains `hardware/rev-a/openpocket-rev-a.kicad_pcb` and is generated
> by `tools/generate_design.py`.

This milestone preserves the completed Freerouting 2.3.0 experiment started
from OpenPocket commit `96e4b115041a86ea5dd4e42bbec4f9ebcc084661`.
The run disabled automatic neckdown, used zero neck width, enforced strict
DRC and 0.25 mm hole clearance, and reserved L2/L7 as uninterrupted GND
planes. The configured limit was 60 passes. Freerouting stopped automatically
after pass 18 because the route had plateaued, then ran its optimizer stage.

## Result

- Initial autorouter work: 341 unrouted items after fanout
- Best/final Freerouting result: 86 unrouted, 383 Freerouting violations
- Imported geometry: 3,012 track segments and 471 vias
- Runtime: 10 h 34 min 31 s
- KiCad 9 audit of the temporary import: 13 reported DRC violations and 100
  unconnected items
- Of the 13 DRC entries, 7 are copper/geometry errors and 6 are missing local
  footprint-library warnings
- Critical routing audit: failed; unsafe USB geometry, crystal vias/length,
  and local high-current neckdowns remain

The Freerouting and KiCad counts are not directly equivalent. In particular,
the 383 Freerouting violations were constant throughout the run and include
tool-internal connectivity state. The KiCad report is the manufacturing-rule
authority for the imported board.

This route is materially cleaner than the earlier power-islands benchmark in
KiCad DRC terms, but it is not safe to promote. It is retained so remaining
connections can be inspected or hand-routed without losing the experiment.

## Selective salvage

`import_freerouting.py --exclude-net NET` can retain the authoritative PCB's
existing copper for selected critical nets while importing the remainder of
this session. Excluding the USB pairs, oscillator nets, failed clearance nets,
and high-current nets identified by `routing-audit.json` produced a temporary
board with zero KiCad copper/geometry violations (six local footprint-library
warnings remained) and 137 unconnected items. This is the safer starting point
for targeted routing; the unfiltered 100-open import must not be mistaken for
the better engineering result.

## Files

- `openpocket-safe-rules60.ses`: completed Freerouting session.
- `openpocket-safe-rules60-imported.kicad_pcb`: temporary strict-fallback
  import for inspection and manual route work; never the authoritative board.
- `openpocket-safe-rules60-filtered.kicad_pcb`: safer hand-routing starting
  point with the critical nets from `safe-salvage-exclusions.txt` retained
  from the authoritative generator PCB.
- `kicad-drc.rpt`: full KiCad DRC report for the temporary import.
- `routing-audit.json`: critical-net routing audit for the temporary import.
- `filtered-kicad-drc.rpt` and `filtered-routing-audit.json`: validation
  evidence for the safer filtered import.
- `safe-salvage-exclusions.txt`: exact critical-net exclusion set.
- `../../visuals/openpocket-safe-rules60-{top,bottom}.png`: 3D inspection
  renders of this imported routing milestone.

## Reproduce the import

```sh
python3 hardware/rev-a/tools/import_freerouting.py \
  hardware/rev-a/routing-benchmarks/safe-rules-60pass/openpocket-safe-rules60.ses \
  --board hardware/rev-a/openpocket-rev-a.kicad_pcb \
  --output /tmp/openpocket-safe-rules60-imported.kicad_pcb \
  --fallback-parser
```

Before any benchmark copper is promoted, it must be legalized, encoded in the
authoritative generator/session workflow, and prove zero KiCad DRC violations,
zero unconnected items, and a clean critical-routing audit.
