# OpenPocket Revision-A production-readiness review

Review date: 2026-08-05
Classification: **engineering prototype — manufacturing release blocked**

This document records the pre-fabrication checks performed on the generated
KiCad 9 sources. It is not an order approval. release_gate.py remains the
authoritative fail-closed release control.

## Release decision

Revision A is not production-ready. The PCB now contains a deterministic L2
ground fanout (221 local stubs and 116 through vias), but no signal route has
been accepted. KiCad still reaches its 499-item unconnected-report limit. The
first improved-floorplan route reduced Freerouting's 752 incomplete
connections to 272, but incorrectly used L2 for signals. After the ground
fanout and an explicit L2 power-plane constraint, the next route started at
531 incompletes but exceeded the review host's memory before writing a
session. No partial autoroute was accepted into the design.

Do not upload the generated Gerbers to a fabricator until routing, impedance,
mechanical, independent schematic/layout, custom-part, and first-article gates
are closed.

## Verified results

| Check | Result | Evidence / disposition |
|---|---:|---|
| KiCad 9 ERC | 0 errors, 0 warnings | kicad-cli sch erc |
| KiCad 9 geometric DRC | 0 errors, 1 warning | One location-less F.Cu copper-sliver warning; connectivity separately reaches the 499-item report limit |
| PCB stack | 4 copper layers, 1.0 mm, 90 x 60 mm | KiCad PCB source and Gerber job data |
| Assembly fiducials | 3 top, 3 bottom | 1.0 mm copper / 2.0 mm mask opening |
| Exposed-pad thermal vias | U2: 9, U11: 9, U21: 9 | 0.45/0.20 mm tented, footprint-embedded vias to GND |
| L2 ground fanout | 221 stubs, 116 board vias, 0 open GND items | Persisted L2 fill; no signal copper is permitted on L2 |
| BOM completeness | 229 populated components, 95 populated line items | Every populated line has manufacturer, MPN, LCSC code, and package |
| BOM/CPL population set | exact match | DNP entries are excluded from assembly placement |
| LCSC snapshot | 85 exact matches with stock; 2 custom codes unresolved | 87 unique non-CONS codes checked against the LCSC/JLC search API |
| AMT firmware tests | 5 passed | deterministic rebuild, manifest, timing, register integrity, state machine |
| Manufacturing generator | completed | Gerbers, drill, BOM/CPL, drawings, board-only STEP, firmware, checksums, and ZIPs |
| ZIP integrity | passed | JLCPCB and PCBWay ZIPs tested with unzip -t |

The two unresolved supplier codes are C2908157 (modified RX5808 module) and
C9900018923 (AMT630A). They are intentionally covered by preorder/consigned
assembly instructions; current API lookup did not return either code.

## Analyzer results and limits

- Full PCB analysis: 370 findings — 234 errors, 18 warnings, and 118 information
  items. Of the errors, 233 are the unrouted-net findings; the remaining
  board-edge finding is the intentional edge-mounted microSD connector and
  still requires enclosure/mechanical sign-off.
- EMC pre-compliance analysis: score 79.0/100, with 0 errors and 19 warnings.
  The warnings concern decoupling-via proximity and heuristic switching
  regulator/filter estimates. The report has low trust because extracted
  datasheet coverage is absent and 233 signal nets are not routed.
- Gerber analysis: 0 errors and 1 alignment warning. Copper/edge extents differ
  while routing copper is absent, so this is not a fabrication approval.
- Schematic analysis: 5 heuristic voltage-domain errors and 27 warnings.
  Four domain findings are around the intentional SN74AHCT125 3.3 V-to-5 V
  input stage; the backlight PWM finding also needs datasheet-backed review.
  These findings are not closed merely because ERC passes.
- Thermal analysis was skipped by the analyzer because no extracted
  per-MPN power/thermal dataset was available.
- SPICE validation was not run because ngspice, Xyce, and LTspice were not
  installed in the review environment.
- The LCSC-only lifecycle audit returned unknown for all 87 unique MPNs by
  construction; it is a stock lookup source, not lifecycle evidence.

## Required work before release

1. Route every net and hand-review USB, RX5808 RF, analog video, switching
   nodes, high-current paths, clocks, RGB, and return paths.
2. Obtain clean KiCad DRC with zero unconnected items; rerun PCB, cross-domain,
   EMC, thermal, Gerber, BOM/CPL, and release-gate checks on that exact route.
3. Perform the ER-TFT050A3-2 flex pin-1 and enclosure-stack overlay and approve
   the edge-mounted USB-C and microSD mechanical clearances.
4. Complete independent pin-by-pin schematic and layout reviews.
5. Obtain assembler acceptance for AMT630A and modified RX5808
   preorder/consignment, including the SPI-enable work instruction and an
   inspected sample.
6. Complete the independent AMT630A clean-room/license review.
7. Approve the final JLCPCB/PCBWay stack-up and controlled-impedance geometry.
8. Build and electrically validate first articles using factory-test.md and
   first-power-up.md; only then update release-status.json.

Generated manufacturing output is deliberately ignored by Git. Regenerate it
from the reviewed source with:

~~~sh
python3 hardware/rev-a/tools/generate_manufacturing.py
python3 hardware/rev-a/tools/release_gate.py
~~~

The second command must remain blocked until all evidence above is attached
and every release-status gate is explicitly resolved.
