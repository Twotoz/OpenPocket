# OpenPocket Revision A — Engineering Prototype

Revision A is a 115 mm × 72 mm, eight-layer, all-in-one transmitter board based
on the ESP32-S3-MINI-1U-N8. The intended assembled signal path is:

```text
5.8 GHz antenna -> RX5808 -> AT7456E -> AMT630A -> 40-pin ER-TFT050A3-2
```

Composite video never leaves the PCB. JLCPCB Standard PCBA is the primary
assembly target, with pre-order and consigned-RX5808 variants; the design is
vendor-neutral. The user installs
only the TFT panel, controls, one wired protected 1S battery connection,
antennas, a pre-flashed ExpressLRS nano receiver, and the enclosure.

## Release state

This directory is an engineering-review package, not an order package. The
release script intentionally refuses to generate Gerbers or a manufacturing
ZIP until every blocking item in `release-status.json` is resolved with a
reviewed source artifact.

The generated KiCad draft has a clean ERC and a completed L2 ground fanout,
but signal routing and final DRC remain incomplete. It is therefore not a
fabrication/order package. The source-built AMT630A firmware and circuit
research may be reviewed independently, but they do not waive schematic,
layout, Gerber and first-article gates. Software tests are not hardware
validation.

## Design constraints

- 115 mm × 72 mm fixed outline.
- Eight layers, 1.0 mm finished thickness, 1 oz copper, ENIG.
- L1/L8 components and critical routing, uninterrupted L2/L7 ground, and six
  available routing layers for signals and width-controlled power routes.
- RX5808 on the bottom side with shield, solder-joint, antenna and inspection
  clearances; J11 U.FL/MHF1 is also bottom-side for a via-free 5.8 GHz feed.
- AMT630A next to the edge-mounted TFT connector; AT7456E on the short analog
  path between RX5808 and AMT630A.
- Backlight switching and power converters stay outside the analog/RF region.
- Separate ESP32, ELRS 2.4 GHz, and RX5808 5.8 GHz antenna regions.
- Dedicated user-accessible push-push microSD at 1-bit/20 MHz maximum, with
  switched power and enclosure finger/eject clearance.
- Board marking: `OpenPocket Rev A` and `Engineering Prototype`.

## Contents

| File | Purpose |
|---|---|
| `gpio-map.md` | authoritative ESP32 and expander allocation |
| `microsd.md` | SDMMC circuit, socket audit, limits and acceptance tests |
| `wiring.md` | internal and user-installed connections |
| `power-budget.md` | preliminary worst-case and thermal calculations |
| `routing-constraints.md` | KiCad netclasses, widths, vias and routing order |
| `stackup.md` | nominal 1.0 mm eight-layer construction and impedance sign-off gate |
| `bom.csv` | controlled component selection and verification state |
| `dnp.csv` | optional/DNP items |
| `consigned-parts.csv` | RX5808 manual-assembly requirement |
| `release-status.json` | machine-readable evidence and blockers |
| `factory-test.md` | pass/fail protocol and first-article sequence |
| `pcbway-notes.md` | stack-up, assembly, inspection, and substitution rules |
| `tools/release_gate.py` | refuses an unsafe manufacturing release |

Fabrication outputs and a versioned release ZIP must only be generated after
the KiCad sources pass review, ERC, DRC and independent Gerber inspection.
