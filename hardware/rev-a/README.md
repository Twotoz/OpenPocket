# OpenPocket Revision A — Engineering Prototype

Revision A is a 55 mm × 45 mm, four-layer, all-in-one transmitter board based
on the ESP32-S3-MINI-1U-N8. The intended assembled signal path is:

```text
5.8 GHz antenna -> RX5808 -> AT7456E -> AMT630A -> 40-pin AT050TN33 V.1
```

Composite video never leaves the PCB. PCBWay installs all normal electronics
and manually installs the selected shielded RX5808 module. The user installs
only the TFT panel, controls, one wired protected 1S battery connection,
antennas, a pre-flashed ExpressLRS nano receiver, and the enclosure.

## Release state

This directory is an engineering-review package, not an order package. The
release script intentionally refuses to generate Gerbers or a manufacturing
ZIP until every blocking item in `release-status.json` is resolved with a
reviewed source artifact.

The current blockers are safety-critical:

1. the exact Innolux AT050TN33 V.1 datasheet and a mechanical pin-1 check are
   not present in the repository;
2. no commercially redistributable, source-built AMT630A firmware with clear
   provenance has been approved;
3. the exact RX5808 20120322-style consigned module, drawing, SPI modification,
   and assembly sample have not been selected and inspected.

PCBWay sourcing/consignment confirmation and first-article HIL remain required
after those inputs are resolved. Software tests are not hardware validation.

## Design constraints

- 55 mm × 45 mm target outline; 60 mm × 48 mm is the absolute maximum.
- Four layers, 1.0 mm finished thickness, 1 oz copper, ENIG.
- L1 components/critical signals, uninterrupted L2 ground, L3 power/slow
  signals, L4 secondary components/routing.
- RX5808 on L4 with shield, solder-joint, antenna and inspection clearances.
- AMT630A next to the edge-mounted TFT connector; AT7456E on the short analog
  path between RX5808 and AMT630A.
- Backlight switching and power converters stay outside the analog/RF region.
- Separate ESP32, ELRS 2.4 GHz, and RX5808 5.8 GHz antenna regions.
- Board marking: `OpenPocket Rev A` and `Engineering Prototype`.

## Contents

| File | Purpose |
|---|---|
| `gpio-map.md` | authoritative ESP32 and expander allocation |
| `wiring.md` | internal and user-installed connections |
| `power-budget.md` | preliminary worst-case and thermal calculations |
| `bom.csv` | controlled component selection and verification state |
| `dnp.csv` | optional/DNP items |
| `consigned-parts.csv` | RX5808 manual-assembly requirement |
| `release-status.json` | machine-readable evidence and blockers |
| `factory-test.md` | pass/fail protocol and first-article sequence |
| `pcbway-notes.md` | stack-up, assembly, inspection, and substitution rules |
| `tools/release_gate.py` | refuses an unsafe manufacturing release |

KiCad manufacturing sources, fabrication outputs, and a versioned release ZIP
must only be added after the missing primary data has been reviewed. An empty
or guessed schematic would be more dangerous than an explicit release block.
