# Revision-A power, ripple and runtime design budget

All values below are pre-fabrication calculations and conservative electrical
acceptance limits. First-article measurements must meet the already frozen
limits in `first-power-up.md`; they are not represented here as measured data.

## Load allocation

| Load | Rail | Normal | Design peak | Power at peak |
|---|---:|---:|---:|---:|
| RX5808 | 5V_VIDEO | 170 mA | 200 mA | 1.00 W |
| AT7456E + translators | 5V_VIDEO | 60 mA | 100 mA | 0.50 W |
| AMT630A + flash | DISPLAY_3V3 | 100 mA | 150 mA | 0.50 W |
| ER-TFT050A3-2 logic | PANEL_3V3 | 120 mA | 220 mA | 0.73 W |
| backlight, 2P6S | 5V_DISPLAY | 185 mA | 230 mA | 1.15 W |
| ELRS receiver-as-TX | 5V_ELRS | 100 mA | 500 mA | 2.50 W |
| PCB buzzer | switched 5 V | intermittent | 110 mA | 0.55 W |
| optional NS4168, 8 Ω/1 W limit | switched 5 V | off | 280 mA | 1.40 W |
| ESP32-S3 + board logic | 3V3_LOGIC | 180 mA | 800 mA | 2.64 W |
| microSD | 3V3_SD | 40 mA | 300 mA | 0.99 W |

The firmware keeps the speaker off unless explicitly requested, disables ELRS
in simulator mode, and does not schedule a continuous buzzer tone with maximum
speaker output. The 5 V continuous design point is 2.0 A and the bounded
transient point is 2.5 A. At 5 V/2.0 A plus a simultaneous 3.3 V/0.8 A load,
90% and 88% conversion efficiencies respectively, a 3.0 V cell supplies
approximately 4.33 A. The 2.5 A 5 V transient would reach 5.25 A and is limited
to converter/load transient duration; supported cells are rated at least 5 A
continuous with welded tabs and low-resistance wiring.

## Converter calculations

### TPS61088 main 5 V boost

R20=316 kΩ and R21=100 kΩ with the 1.204 V feedback reference produce
`1.204 × (1 + 316/100) = 5.008 V`. R51=330 kΩ selects approximately 1 MHz.
L3 is Coilcraft XAL6030-182MEC, 1.8 µH, 10 A-class shielded inductor. At
VIN=3.0 V, VOUT=5.008 V, IOUT=2.0 A and 90% efficiency, average input current
is 3.71 A, duty cycle is 40.1%, and ideal inductor ripple is about 0.67 A p-p;
the calculated peak is 4.05 A. This leaves more than 2:1 margin to the selected
inductor's saturation class and substantial margin to the programmed/device
switch limit. Six 22 µF/10 V output MLCCs are budgeted as at least 55 µF total
effective capacitance after 5 V DC bias. Capacitive ripple is about 15 mV p-p;
including ESR/layout/transient allowance, the release limit is 100 mV p-p.

### TPS63070 3.3 V logic buck-boost

R22=1.00 MΩ and R23=316 kΩ produce approximately 3.332 V. L2 is
SWPA4020S1R0MT, 1.0 µH. At 3.0 V input, 3.3 V/0.8 A output and 88% efficiency,
average input current is 1.00 A. At the approximately 2.4 MHz switching rate,
ideal ripple is 0.12 A p-p and peak inductor current is about 1.06 A, below the
device's 3.05 A minimum positive average-current limit and below the selected
inductor rating. Two 22 µF/10 V output capacitors are treated as 20 µF total
effective minimum; ripple plus load-step acceptance is 75 mV p-p.

### TPS62162 display 3.3 V buck

U10 is the fixed 3.3 V variant and uses L5 SWPA3015S2R2MT, 2.2 µH, with
22 µF output capacitance. From 5.0 V at the 2.25 MHz nominal frequency and
370 mA worst-case display load, ideal inductor ripple is about 0.10 A p-p and
peak current about 0.42 A. This is inside the 1 A converter rating and the
inductor margin. The display-domain limit is 50 mV p-p. FB2/FB3/FB4 isolate
AMT analog, AMT digital and panel return-current loops without splitting L2.

### TPS61165 backlight

The panel is two parallel strings of six LEDs. At the 19.6 V cold maximum and
40.08 mA set by `200 mV / 4.99 Ω`, LED output is 0.786 W. At 85% efficiency,
5 V input current is 185 mA. With 1.2 MHz, L4=10 µH and about 74.5% boost duty,
ideal input/inductor current is 0.185 A and ripple approximately 0.31 A p-p;
peak is about 0.34 A, well below the 1.2 A switch limit and selected inductor
saturation rating. D1 is B240A-13-F (40 V/2 A). Two 1 µF/50 V output MLCCs
provide DC-bias margin; permitted output ripple is 300 mV p-p. The 4.99 Ω,
1% resistor fixes normal current below the 42 mA production stop limit even at
100% PWM. CTRL is hardware pulled off during reset.

### BQ25895 power path and charging

R42=750 Ω sets an ILIM hardware ceiling near 2 A; firmware also applies the
negotiated/input register limit and never commands more than 1 A charge. The
device supports a 3.25 A programmable input limit, but Revision A budgets 2 A
at a 5 V USB source unless the factory fixture explicitly advertises more.
Charge current is reduced to 500 mA when display/video is active and to zero
when measured system demand, input droop or temperature would exceed the
budget. USB-only startup is therefore supported with ELRS hard-gated and
display/video optional. The charger exposed pad and recommended copper/vias
are mandatory; a calculated 0.8 W worst local dissipation at θJA=45 °C/W on
the implemented copper implies about 36 °C junction rise. Firmware begins
thermal reduction at 75 °C reported die temperature and disables charging at
90 °C or on NTC fault.

### Protection and physical switch

U3 is the fixed BQ29700DSER: 4.275 V overvoltage and 2.8 V undervoltage
thresholds, suitable for a 4.2 V Li-ion cell. Q1 is the dual FS8205A; the
back-to-back topology provides charge/discharge/short isolation. U20
TPS22992SRXNR disconnects all radio electronics while charger, protection and
gauge remain alive. C23=10 nF controls the rise; factory acceptance requires
no SYS_SWITCHED overshoot and peak inrush below 2.5 A. Off leakage at the
switched rails must keep each below 0.20 V.

## Thermal allocation

With recommended copper and thermal vias, pre-fabrication dissipation limits
are 0.8 W BQ25895, 0.75 W TPS61088, 0.35 W TPS63070, 0.20 W TPS62162, 0.15 W
TPS61165, 0.20 W Q1, and 0.10 W per load switch. At 40 °C ambient the predicted
worst junction values are respectively below 116, 95, 62, 53, 72, 70 and
55 °C using datasheet board-level θJA values and the implemented copper area.
The first-article stop limits are 110 °C IC case estimate, 85 °C PCB surface,
and 70 °C touch-accessible enclosure surface; exceeding one disables charging
and the affected load and requires an ECO, not a firmware-limit increase.

## Runtime model

The model reserves 15% of nameplate capacity for cutoff, ageing and gauge
uncertainty and uses 3.6 V nominal cell energy. Representative battery-input
powers are: simulator 1.0 W; video/50% backlight/10 mW ELRS 4.9 W;
video/100%/10 mW 5.5 W; video/100%/100 mW 6.2 W; scanning 5.8 W; Wi-Fi
maintenance with video off 2.0 W. Estimated 3000 mAh/new-cell runtimes are
9.2 h, 1.87 h, 1.67 h, 1.48 h, 1.58 h and 4.59 h respectively. Scale by
0.833/1.167 for 2500/3500 mAh; an 80%-health cell yields 80% of those values.
Cold-operation planning applies a further 20% reduction. These figures are
engineering estimates; the endurance mode records real rail states, voltage,
SOC, resets, deadline misses, brightness and RX channel for first-article
comparison.
