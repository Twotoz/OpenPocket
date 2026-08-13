# Revision-A wiring and signal paths

## Internal PCB connections

These connections are routed entirely on the PCB and are not user wiring:

```text
RX5808 VIDEO OUT
  -> TP_VRX_VIDEO
  -> NORMAL/BYPASS solder-jumper input
  -> AT7456E VIN
  -> AT7456E VOUT
  -> TP_OSD_VIDEO
  -> AMT630A CVBS1
```

The manufactured jumper state is **NORMAL**. BYPASS connects RX5808 video
directly to AMT630A CVBS1 for diagnosis. It must never connect both drivers or
create a second 75 ohm termination.

The AMT630A drives 24-bit RGB plus DCLK, DISP, HSYNC, VSYNC, and DE directly to
the edge-mounted Hirose FH12-40S-0.5SH(55). The design is specific to the
Innolux AT050TN33 V.1 or a clone verified pin-for-pin and electrically. It is
not a universal 40-pin TFT interface.

| TFT pin | Net |
|---:|---|
| 1 | VLED- |
| 2 | VLED+ (approximately 19.8 V, 40 mA total) |
| 3 | GND |
| 4 | clean display 3.3 V |
| 5–12 | R0–R7 |
| 13–20 | G0–G7 |
| 21–28 | B0–B7 |
| 29 | GND |
| 30 | DCLK |
| 31 | DISP |
| 32 | HSYNC |
| 33 | VSYNC |
| 34 | DE |
| 35 | NC |
| 36 | GND |
| 37–40 | isolated unpopulated test pads only |

Panel pin 1 and bottom-contact flex orientation are release blockers until
checked against the exact panel datasheet and final mechanical stack.

## RX5808 module

Selected form factor: shielded 28 mm × 23 mm × approximately 3 mm module.

| Module pin | Board connection |
|---:|---|
| 1 | GND |
| 2 | 50 ohm 5.8 GHz antenna feed |
| 3 | RF ground |
| 4 | DATA / CH1 to GPIO7 |
| 5 | LE / CH2 to GPIO8 |
| 6 | CLK / CH3 to GPIO9 |
| 7 | digital ground |
| 8 | filtered switched 5V_VIDEO |
| 9 | RSSI to protected ADC1 GPIO5 |
| 10 | AUDIO test pad only |
| 11 | VIDEO to TP_VRX_VIDEO |
| 12 | analog/video ground |

The consigned module must be the selected SPI-capable 20120322-style revision.
PCBWay must remove the RTC6715 SPI-enable pull-down resistor before module
installation, inspect the modification under magnification, replace the
shield, and verify DATA/LE/CLK tuning. This is never an end-user modification.

Place 100 nF, 10 uF, and 330–470 uF low-ESR bulk capacitance after the local
ferrite/LC filter. Keep RSSI and video short and referenced to uninterrupted
ground. Common digital, analog-video, and module grounds join through the
continuous L2/L7 planes; do not create a floating video ground.

## User-installed connections

The right-edge developer pads are optional: J14 provides exactly four wires,
`OLED_GND`, `OLED_3V3`, `OLED_SDA`, and `OLED_SCL`, for an SSD1306/SH1106-class
128x64 3.3 V I2C OLED. J15 provides `DEV_IO0`–`DEV_IO3` plus
3V3/GND from U19. These are slow expansion signals, not high-speed ESP32
GPIOs; keep attached wires short and away from the RX5808 antenna/video path.

User controls are split into labelled, plated-through-hole groups rather than
one generic controls strip. Every control group has its own adjacent `G` pad,
which connects locally to the ground planes; do not substitute a remote shared
ground pad. The left edge contains J9 (`G/UP`, `G/DN`, `G/ENT`, `G/BACK`) and
J18 (`A/G/B`, `PRESS/G`) for the menu and encoder. The right edge contains J19
(`G/ARM`), J20–J22 (`G/HI/LO` for AUX2–AUX4), and J23–J26 (`G/-/+` for the
AIL, ELE, THR, and RUD trims). J5 is different: it is the isolated two-wire
master-switch contact and must not be tied to ground.

- Insert the exact supported TFT flex into the edge ZIF connector.
- Solder each gimbal's two three-wire axes to its labelled LX/LY (or RX/RY),
  3V3, and GND pads; each connector therefore has six pads.
- Solder switches, menu buttons, trims, encoder, and power switch to their
  labeled edge groups and strain-relief holes.
- Solder welded battery leads to BAT+ and BAT-. Connect a compatible 10 k NTC
  to NTC/NTC_GND. Never solder directly to an 18650 cell can.
- Press a 50-ohm U.FL/MHF1-to-SMA-female bulkhead cable vertically onto the
  bottom-side J11 receptacle. Fasten the SMA bulkhead to the enclosure before
  attaching the 5.8 GHz antenna; never let cable strain reach J11. Match SMA
  versus RP-SMA to the selected antenna. Install the separate 2.4 GHz ELRS and
  ESP32 Wi-Fi antennas in their marked RF regions.
- Connect a pre-flashed ExpressLRS nano receiver using four normal wires:
  ELRS_5V, ELRS_GND, ELRS_RX, ELRS_TX. From the ESP32 perspective GPIO17 TX
  connects to receiver RX; receiver TX connects to GPIO18 RX. ELRS_BOOT and
  ELRS_RESET are optional service pads.

The external ELRS rail is switched and designed for a 500 mA peak. Firmware
starts at 10 mW and exposes at most 100 mW. Controls and CRSF must remain safe
if any video-domain part is absent or faulted.
