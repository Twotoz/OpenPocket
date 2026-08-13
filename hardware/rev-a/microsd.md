# Revision-A microSD subsystem

Revision A uses the SOFNG TF-001A-P3 push-push socket (`J12`, JLC/LCSC
`C3021282`) in dedicated ESP32-S3 SDMMC 1-bit mode. It is not connected to the
AT7456E SPI bus or AMT630A flash mux. The card ejects toward the top enclosure
edge; the card body, locked/ejected positions, finger access and push-push
travel are mechanical keep-outs.

## Electrical implementation

| Item | Selection / limit |
|---|---|
| Socket | SOFNG TF-001A-P3, 14.55 × 15.80 × 1.9 mm maximum envelope, normally-open card switch |
| Power switch | `U22` TPS22918DBVR, JLC/LCSC `C131941`, VIN=`3V3_LOGIC`, VOUT=`3V3_SD` |
| Card transient allowance | 300 mA minimum |
| Local capacitance | `C24` 100 nF 10 V 0402 + `C25` 10 µF 25 V 0805 + optional `C26` 47 µF 10 V 1206 |
| SD pull-ups | 10 kΩ to `3V3_SD` on CMD and DAT0/DAT1/DAT2/DAT3 |
| Card detect | socket switch to GND, 10 kΩ to `3V3_LOGIC`; logic 0 = card fully inserted |
| Series damping | 27 Ω on CLK, CMD and DAT0, placed at the ESP32 end |
| ESD | two TI TPD4E001DRLR arrays, JLC `C527516`, 1.5 pF/channel |
| Bus mode | SDMMC, 1-bit (`slot.width = 1`) |
| Clock | 400 kHz identification; 20 MHz maximum for Revision A |

TPS22918 worst-case room-temperature on-resistance is budgeted at 52 mΩ. At
300 mA this gives 15.6 mV drop and 4.7 mW dissipation. The 47 µF footprint is
provided because the effective capacitance of X5R MLCCs falls under DC bias;
with a conservative 33 µF combined effective capacitance, a 100 mA/10 µs load
edge produces approximately 30 mV capacitive droop before regulator response.
The acceptance limit at `TP_3V3_SD` is 3.135–3.465 V steady-state and less than
100 mV peak-to-peak ripple/step excursion during initialization and writes.

The 27 Ω resistors plus the ESP32 output impedance provide source damping for
the short 20 MHz traces. CLK/CMD/DAT0 must each be under 45 mm, remain on L1
over continuous L2 ground, use no stubs other than the adjacent ESD/test pad,
and avoid vias where possible. They must stay outside the CVBS, RSSI,
TPS61165, class-D, USB and all antenna exclusion regions. The 1.5 pF ESD load
adds roughly 75 ps at a 50 Ω source and is acceptable at the capped clock;
40 MHz remains firmware-disabled pending first-article eye/edge testing.

Test points are `TP_3V3_SD`, `TP_SD_CLK`, `TP_SD_CMD`, `TP_SD_D0`,
`TP_SD_DETECT`, and an adjacent ground pad. The socket shell uses four short
ground pads with local stitching into the uninterrupted L2 plane.

## Socket pin audit

| Socket pin | microSD function | Revision-A net |
|---:|---|---|
| 1 | DAT2 | `SD_DAT2`, 10 kΩ pull-up, ESD, no ESP32 connection |
| 2 | DAT3 / CS | `SD_DAT3`, 10 kΩ pull-up, ESD, no ESP32 connection |
| 3 | CMD | `SD_CMD`, GPIO41 through 27 Ω, 10 kΩ pull-up, ESD |
| 4 | VDD | `3V3_SD` |
| 5 | CLK | `SD_CLK`, GPIO40 through 27 Ω, ESD |
| 6 | VSS | GND |
| 7 | DAT0 | `SD_D0`, GPIO42 through 27 Ω, 10 kΩ pull-up, ESD |
| 8 | DAT1 | `SD_DAT1`, 10 kΩ pull-up, ESD, no ESP32 connection |
| 9 | card switch | `SD_CARD_DETECT`, closes to GND when inserted |
| shell | shield/retention | GND at four short pads |

The custom KiCad land pattern is derived from the SOFNG vertical-view drawing:
P1–P8 use 0.80 mm pitch, P9 is the independent card-switch pad, and all four
retention pads are present. Before fabrication release, the plotted pads and
card/eject outlines must be overlaid 1:1 against that drawing and inspected in
the enclosure STEP assembly.

## Factory and first-article acceptance

Use a 500 MHz or faster oscilloscope with a short ground spring and a
current-limited supply. With the radio master switch closed:

1. No card: detect high, `3V3_SD` below 0.20 V, radio controls and CRSF run for
   ten minutes with zero deadline misses.
2. Insert card: detect goes below 0.30 V and remains stable for the 80 ms
   debounce interval; `3V3_SD` reaches 90% within 5 ms and stays within
   3.135–3.465 V.
3. Initialization/write: rail excursion below 100 mV p-p, CLK has no
   overshoot above 3.6 V or below -0.3 V, and the card mounts as FAT32 at
   20 MHz or below.
4. Removal during continuous telemetry logging: the service unmounts and
   disables `3V3_SD`; control remains at 250 Hz, CRSF has no missed frame, and
   re-insertion recovers without reboot.
5. Corrupt BPB, FAT16, exFAT and unreadable media: no automatic format, update
   or flash action; the UI reports unavailable/corrupt and radio safety is
   unchanged.
6. Power-cycle the card 100 times and run 10,000 bounded log writes without a
   control deadline miss or a boot-critical configuration change.

Required card matrix (FAT32, one specimen each) is SanDisk Industrial 8 GB
`SDSDQAF3-008G-I`, Kingston Canvas Select Plus 16 GB `SDCS2/16GB`, and Samsung
PRO Endurance 32 GB `MB-MJ32KA`. Compatibility is not claimed until these
exact tests run on first articles; exFAT and arbitrary cards are outside the
Revision-A claim.
