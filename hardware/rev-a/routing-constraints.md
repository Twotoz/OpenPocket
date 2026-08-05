# Revision-A routing constraints

These KiCad netclasses are mandatory engineering constraints for placement and
routing. They prevent a generic-width autoroute from being confused with a
reviewed layout. Widths for USB and RF are preliminary until the assembler
confirms the exact 1.0 mm four-layer stack-up and returns an impedance review.

| Netclass | Clearance | Track | Via / drill | Intended use |
|---|---:|---:|---:|---|
| `FinePitch` | 0.10 mm | 0.12 mm | 0.45 / 0.20 mm | AMT630A RGB escape and panel bus |
| `DigitalFast` | 0.12 mm | 0.15 mm | 0.50 / 0.25 mm | SPI, SDMMC, I2S and RX control |
| `USB_Preliminary` | 0.15 mm | 0.15 mm | 0.45 / 0.20 mm | native USB D+/D-; hand-route as a pair |
| `AnalogVideo` | 0.15 mm | 0.25 mm | 0.60 / 0.30 mm | RX5808, AT7456E and AMT630A CVBS path |
| `RF_Preliminary` | 0.30 mm | 0.25 mm | 0.60 / 0.30 mm | short RX5808-to-coax feed; hand-route |
| `PowerLogic` | 0.15 mm | 0.40 mm | 0.70 / 0.35 mm | 3.3 V domains, speaker and local rails |
| `Power` | 0.15 mm | 0.80 mm | 0.80 / 0.40 mm | switched 5 V distribution |
| `HighCurrent` | 0.20 mm | 1.20 mm | 1.00 / 0.50 mm | battery, USB, charger and main rails |
| `SwitchNode` | 0.20 mm | 0.80 mm | 0.80 / 0.40 mm | converter switch loops; keep short |
| `BacklightHV` | 0.20 mm | 0.40 mm | 0.70 / 0.35 mm | boosted LED anode/cathode path |
| `Ground` | 0.10 mm | 0.50 mm | 0.70 / 0.35 mm | L2 plane fan-out and stitching |
| `Default` | 0.10 mm | 0.20 mm | 0.60 / 0.30 mm | low-speed control and sensing |

## Routing order

1. Lock the reviewed component placement and mechanical keep-outs.
2. Hand-route switch loops, crystal loops, CVBS, RX RF and USB.
3. Route main power and ground fan-out, then verify return paths on L2.
4. Route RGB, SDMMC, SPI/I2S and remaining low-speed controls.
5. Add ground stitching without breaking the RF, video or USB return paths.
6. Refill zones and require clean KiCad ERC/DRC with zero unconnected pads.

Autorouting may be used only as a seed for non-critical nets. Its imported
session must preserve these netclasses and is never evidence of impedance,
thermal, EMI or manufacturing approval by itself.
