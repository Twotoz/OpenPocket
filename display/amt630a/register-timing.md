# AMT630A register and timing review record

This file defines the data that must be filled from reviewed primary sources
before firmware release. Values marked `BLOCKED` are intentionally not guessed.

| Item | Required value | State |
|---|---|---|
| crystal | 27.000 MHz | selected; load network pending crystal MPN |
| active pixels | 480 × 272 | selected |
| pixel clock | exact panel-datasheet range | BLOCKED |
| horizontal total/front porch/sync/back porch | exact panel values | BLOCKED |
| vertical total/front porch/sync/back porch | exact panel values | BLOCKED |
| DCLK edge | exact panel value | BLOCKED |
| HSYNC/VSYNC/DE/DISP polarity | exact panel values | BLOCKED |
| RGB ordering | R0–R7, G0–G7, B0–B7 | mapping selected; controller bit order review open |
| CVBS source | CVBS1 from AT7456E VOUT | selected |
| PAL/NTSC mode | automatic | selected; register sequence open |
| aspect | 16:9 full panel | selected; scaling register sequence open |
| no-signal policy | snow, never forced blue | selected; register sequence open |
| boot behavior | automatic, no prompt | selected; register sequence open |
| recovery | automatic after lost sync | selected; timing/timeout open |

The hardware uses the documented CVBS reference network starting with an 18
ohm series element, 22 nF AC coupling, and the documented 56 ohm/reference
branch where required. The final network must be recalculated as one source and
load system across RX5808, AT7456E and AMT630A so there is no accidental second
75 ohm termination.
