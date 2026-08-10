# Rev-A placement optimization

`tools/optimize_placement.py` is the reproducible placement search for the
authoritative Rev-A generator. It loads the generated KiCad board/netlist,
locks enclosure-facing geometry, and searches XY, rotation, and permitted
side changes with a seeded simulated-annealing loop. `generate_design.py`
consumes `placement-optimized.json`; it remains the single source of truth for
the generated PCB (the manifest is not a one-off PCB patch).

## Objective

The score is the sum of weighted net MST wirelength, 5 mm grid congestion,
estimated ratsnest crossings, nonlinear functional-dependency penalties, and
nonlinear IC-to-decoupler penalties. Net weights prioritize RF, converter
switch loops, crystals/decoupling, CVBS/RGB, high-current power, USB/SD and
SPI over GPIO. Hard legality rejects courtyard/body overlap, board-boundary
violations, the MOD1/U.FL keepout, and copper-pad intersections.

Dependencies include MOD1-J11, the video chain, converter/inductor pairs,
USB/charger, SD/ESD, ELRS/ESD, speaker, GPIO expanders/J9, crystals and local
decouplers. Locked references are the board-accessible connectors, mounting
holes, MOD1/J11 and other enclosure geometry listed in the source.

## Reproduce

```sh
python3 hardware/rev-a/tools/optimize_placement.py \
  --iterations 100 --seeds 11 23 47 71 \
  --output hardware/rev-a/placement-optimized.json \
  --report hardware/rev-a/placement-optimization-report.json
python3 hardware/rev-a/tools/generate_design.py --stage board
```

The default seeds are deterministic. Increase `--iterations` for a deeper
search; compare the generated report before accepting a replacement.

## Current result

The four-seed run reduced the weighted objective from **4,099,417.5** to
**2,458,300.0** (**40.033%**). Full critical-pair distances are recorded in
`placement-critical-distances.json`; baseline and optimized top/bottom renders
are in `visuals/placement-{baseline,optimized}-{top,bottom}.png`.

KiCad DRC on the placement-only board reports 499 expected unconnected items
before routing and one pre-existing fixed TVS1/L1 SwitchNode clearance warning;
the optimizer introduced no courtyard overlap, pad intersection, or edge
clearance violation.

This is a placement-quality result, not a production-release claim. A fresh
signal-only FreeRouting benchmark must be run before final routing/Gerber
release, and its session must not be imported automatically.
