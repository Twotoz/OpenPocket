# Revision-A preliminary power budget

This budget is an engineering estimate, not measured validation. It must be
replaced with rail-current and thermal measurements on first articles.

## Peak load estimate

| Load | Rail | Peak assumption | Input power |
|---|---:|---:|---:|
| RX5808 | 5 V | 170 mA | 0.85 W |
| AT7456E and translators | 5 V | 100 mA placeholder maximum | 0.50 W |
| AMT630A, TFT logic, flash, LDO loss | 5 V | 250 mA placeholder maximum | 1.25 W |
| TPS61165 backlight input | 5 V | 19.8 V × 40 mA / 85% | 0.93 W |
| external ELRS | 5 V | 500 mA transient | 2.50 W |
| miscellaneous 5 V margin | 5 V | 100 mA | 0.50 W |
| ESP32-S3 and 3.3 V logic | battery/TPS63070 | 800 mA transient at 3.3 V | 2.64 W |

The simultaneous conservative peak is approximately 6.53 W on the 5 V rail
(1.31 A) plus 2.64 W on 3.3 V. At a 3.0 V battery, 85% 5 V conversion and 90%
3.3 V conversion, estimated battery current is about 3.65 A. A 25% design
margin raises this to 4.56 A, which is why the supported cell requires at least
5 A continuous capability and welded leads. Converter switch/inductor pulse
current is higher than battery average and needs separate validation.

At a more typical 5.5 W total battery input, a 3000 mAh cell with about 10.8 Wh
usable nominal energy gives roughly 1.9 hours. High ELRS duty cycle, display
brightness, cold temperature, conversion losses, and cutoff margin reduce it;
only an endurance test may be published as product runtime.

## Preliminary component calculations

- TPS61088: 5.0 V, 2 A continuous design target and 2.5 A short transient.
  Inductor saturation, MOSFET current limit, copper loss, loop stability, and
  input ripple must be checked at 3.0 V battery. Use X7R capacitors with at
  least 50% effective capacitance after DC-bias derating.
- TPS63070: 3.3 V logic rail; validate buck-boost crossover, ESP32 RF
  transients, and at least 30% inductor saturation margin.
- TPS61165: approximately 19.8 V at 40 mA for two parallel 6-LED strings. With
  a nominal 200 mV feedback target, the initial sense resistor is 4.99 ohm,
  1%, with power of 8 mW. Confirm the selected panel's internal string
  topology and current sharing before population. Use 35 V-rated output parts
  after DC-bias derating and verify OVP above worst-case LED voltage but below
  component ratings.
- TPS7A2033: clean display 3.3 V from 5V_DISPLAY. Validate AMT630A plus TFT
  logic consumption against its current and thermal limits. Separate analog
  and digital filtering with ferrite beads and local decoupling, while L2
  remains a deliberate continuous ground reference.
- BQ25895: USB 5 V power path, conservative 1 A maximum charge configuration,
  NTC derating, and USB-without-battery operation. Charger copper area and
  thermal reduction require first-article measurements.
- BQ2970: the exact suffix and back-to-back MOSFET remain a release item because
  protection thresholds and overcurrent values must match the selected cell.

Startup must be tested with display, backlight, video, and ELRS loads enabled
in controlled steps. TPS61088 input/output ripple, backlight inrush, charger
heat, and battery-lead voltage drop are mandatory oscilloscope/thermal-camera
measurements.
