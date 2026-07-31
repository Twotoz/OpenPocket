# Bill of materials

This BOM describes a **bench prototype**. Do not order a PCB batch or battery
pack from this list. Exact connectors, regulator ratings, and mechanical
dimensions must follow from the reviewed schematic and enclosure.

## Core components

| Quantity | Component | Minimum requirement | Status / note |
|---:|---|---|---|
| 1 | ESP32-S3 development board or module | enough exposed GPIO, native USB, and at least 8 MB flash recommended | MCU family fixed; exact board still open |
| 1 | RX5808 5.8 GHz receiver module | VIDEO OUT, RSSI, and programmable DATA/LE/CLK available | verify the exact PCB revision and pinout |
| 1 | AT7456E OSD module | 30×16 character OSD, SPI, VIDEO IN/OUT, 27 MHz clock, and video passives fitted | module recommended for the first prototype |
| 1 | composite LCD | accepts both PAL and NTSC with a documented 75 Ω video input | pixel resolution does not determine the character grid |
| 1 | ExpressLRS TX module | full-duplex, non-inverted 3.3 V CRSF UART | a normal ELRS receiver is not sufficient |
| 2 | dual-axis gimbal | analog outputs compatible with conditioned ESP32 ADC inputs | four primary axes total |
| 1 | dedicated ARM switch | maintained, two-position | never share it with menu controls |
| 3 | AUX switches | two- or three-position | optional for the first bench test |
| 4 | menu buttons | UP, DOWN, ENTER, and BACK | active-low GPIO with pull-up |
| 1 | pressable rotary encoder | quadrature A/B plus switch contact | optional but recommended |
| 1 | suitable 5.8 GHz antenna | 50 Ω with the correct connector and polarization | never test with a damaged or open RF connector |

## Power and signal integrity

| Quantity | Component | Purpose |
|---:|---|---|
| 1 | current-limited 5 V bench supply, at least 2 A | first bring-up without a battery |
| 1 | 3.3 V regulator if absent from the S3 board | ESP32-S3 and 3.3 V logic |
| 1 | 74AHCT125 or equivalent 3.3 V-to-5 V buffer | SCLK, MOSI/SDIN, and CS into bare 5 V OSD logic |
| 1 | unidirectional 5 V-to-3.3 V buffer | AT7456E SDOUT/MISO into the ESP32-S3 |
| 1 | open-drain transistor stage | optional AT7456E RESET control |
| several | 100 nF ceramic capacitors | each digital and analog supply pin |
| several | 10–470 µF low-ESR bulk capacitors | local to OSD, LCD, RX5808, and ELRS, sized from measured peak load |
| several | 22–100 Ω series resistors | optional digital edge damping after measurement |
| 1 | fuse or resettable PTC | prototype supply fault limiting |

A ready-made AT7456E module may already contain level shifting, the clock, and
video passives. Verify its schematic; do not trust the product title alone.

## Mechanical and later product work

- shielded or carefully routed composite-video cable
- strain-relieved connectors for gimbals, LCD, and RF module
- main switch and controlled power latch
- protected battery, charger, cell monitoring, and suitable fuse
- passive piezo or haptic warning device
- enclosure, controls, sticks, neck-strap point, and antenna mount
- KiCad PCB with deliberate RF, video, digital, and power return paths

Battery chemistry, charger, and power architecture are deliberately not fixed.
That choice requires a separate thermal, charging, and fault analysis.
