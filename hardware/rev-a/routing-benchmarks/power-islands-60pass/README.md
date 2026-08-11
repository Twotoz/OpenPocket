# Power-islands Freerouting benchmark

> **Benchmark only — do not fabricate this PCB.** The authoritative Rev-A
> board remains `hardware/rev-a/openpocket-rev-a.kicad_pcb` and is generated
> by `tools/generate_design.py`.

This milestone preserves the completed Freerouting 2.3.0 experiment started
from OpenPocket commit `74d10ee07e8e373c9340b1e1b8eccf034250dac3`.
The configured limit was 60 passes. Freerouting stopped automatically after
pass 32 because the route had plateaued, then ran one optimizer pass.

## Result

- Initial autorouter work: 309 connections after fanout
- Best/final Freerouting result: 22 unrouted, 128 Freerouting violations
- Routed by the experiment: 287/309 connections (92.9%)
- Imported geometry: 3,576 track segments and 640 vias
- Runtime: 4 h 25 min 26 s
- Peak Java heap reported by Freerouting: 1,794.7 MB
- KiCad 9.0.9 audit of the temporary import: 619 DRC violations and 50
  unconnected items

The Freerouting and KiCad counts are not directly equivalent. This benchmark
DSN deliberately omitted the GND network/planes and a small set of already
reviewed routes. Consequently, the route may cross local GND fanout geometry
that exists in the authoritative PCB. KiCad also enforces the board's
0.25-mm hole clearance, which accounts for many violations not represented by
the autorouter score.

## Files

- `openpocket-power-islands60.ses`: complete Freerouting session containing
  the benchmark traces.
- `openpocket-power-islands60-imported.kicad_pcb`: temporary strict-parser
  import for inspection and route salvage; never the authoritative board.
- `kicad-drc.rpt`: full KiCad DRC report for that temporary import.
- `routing-audit.json`: critical-net routing audit for the temporary import.
- `../../visuals/openpocket-routing-benchmark-{top,bottom}.png`: surface
  renders of the imported benchmark.

## Reproduce the import

```sh
python3 hardware/rev-a/tools/import_freerouting.py \
  hardware/rev-a/routing-benchmarks/power-islands-60pass/openpocket-power-islands60.ses \
  --board hardware/rev-a/openpocket-rev-a.kicad_pcb \
  --output /tmp/openpocket-power-islands60-imported.kicad_pcb \
  --fallback-parser
```

KiCad's native SES importer rejects the deliberately filtered benchmark
session. The opt-in fallback parser accepts only explicit `path` and `via`
records, validates every net/layer/padstack, preserves board placement and
outline invariants, and is intended to make this routing evidence inspectable.

Before any benchmark copper is promoted, it must be legalized, encoded in the
authoritative generator/session workflow, and prove zero KiCad DRC violations
and zero unconnected items.
