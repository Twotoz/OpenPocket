# Revision-A eight-layer stack-up

The KiCad source and Gerber job file carry this symmetric nominal 1.00 mm
construction. It is an order target; the fabricator must substitute its
available pressed materials while preserving 1.00 mm finished thickness and
confirming the impedance geometries before fabrication.

| Order | Layer/material | Nominal thickness |
|---:|---|---:|
| 1 | Top solder mask, green | 0.010 mm |
| 2 | L1 `F.Cu`, 1 oz | 0.035 mm |
| 3 | FR-4 prepreg | 0.100 mm |
| 4 | L2 `GND1`, 1 oz, continuous reference | 0.035 mm |
| 5 | FR-4 core | 0.100 mm |
| 6 | L3 `SIG1`, 1 oz | 0.035 mm |
| 7 | FR-4 prepreg | 0.100 mm |
| 8 | L4 `SIG2`, 1 oz | 0.035 mm |
| 9 | FR-4 core | 0.100 mm |
| 10 | L5 `SIG3`, 1 oz | 0.035 mm |
| 11 | FR-4 prepreg | 0.100 mm |
| 12 | L6 `SIG4`, 1 oz | 0.035 mm |
| 13 | FR-4 core | 0.100 mm |
| 14 | L7 `GND2`, 1 oz, continuous reference | 0.035 mm |
| 15 | FR-4 prepreg | 0.100 mm |
| 16 | L8 `B.Cu`, 1 oz | 0.035 mm |
| 17 | Bottom solder mask, green | 0.010 mm |

Nominal total: `2 × 0.010 + 8 × 0.035 + 7 × 0.100 = 1.000 mm`.
Surface finish is ENIG. L2 and L7 are uninterrupted ground-reference planes
and must not carry signal tracks. Signal and routed power distribution may use
L1/L3/L4/L5/L6/L8 subject to the netclass widths and return-path review.

Before order approval, request and record:

- the fabricator's exact low-cost 8-layer/1.0 mm pressed stack and tolerance;
- 90 ohm differential geometry for USB D+/D- on L1 referenced to L2;
- 50 ohm grounded-coplanar geometry for `RX_RF` on L1 referenced to L2;
- any required width/spacing ECO, followed by KiCad DRC and fresh Gerbers.

Manufacturer references checked on 2026-08-05:

- JLCPCB PCB capabilities: <https://jlcpcb.com/capabilities/Capabilities?type=1>
- JLCPCB multilayer overview: <https://jlcpcb.com/resources/multiple-layer-pcb>
- JLCPCB impedance-calculator guide:
  <https://jlcpcb.com/help/article/user-guide-to-the-jlcpcb-impedance-calculator>

JLCPCB lists FR-4 thicknesses including 1.0 mm and multilayer production, but
the order configurator/fabricator review remains authoritative for the exact
8-layer stack code. Do not freeze controlled-impedance widths without that
order-specific confirmation.
