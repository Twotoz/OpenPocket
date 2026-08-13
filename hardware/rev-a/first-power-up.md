# Revision-A first power-up and acceptance limits

This procedure is for `OpenPocket Rev A — Engineering Prototype`. It defines
the measurements to perform on every first article; it does not claim that an
unbuilt board has passed them.

## Equipment and initial state

Use a current-limited 5.00 V laboratory supply or USB current injector, a
4-channel oscilloscope of at least 200 MHz with short ground springs, a DMM,
thermal camera, programmable 0–4.2 V battery emulator, PAL/NTSC pattern source,
and an electronic load. Fit no cell, TFT, ELRS receiver or antenna for the
first stage. Leave the external latching power switch open.

Before applying power, microscope-inspect polarity and pin 1 on U2/U3/Q1/U5/
U6/U10/U11/U14/U17/U20, both crystals, J1 and MOD1. Resistance from VBUS_USB,
SYS_ALWAYS, SYS_SWITCHED, 3V3_LOGIC and SYS_SWITCHED_5V to ground must exceed
10 kΩ after capacitors charge; any steady reading below 100 Ω is a hard fail.

## Controlled sequence

1. Set 5.00 V, 100 mA current limit and apply USB with the master switch open.
   `SYS_ALWAYS` must rise to 3.50–4.55 V within 100 ms, while `SYS_SWITCHED`,
   `3V3_LOGIC` and `SYS_SWITCHED_5V` remain below 0.20 V. Expected settled USB
   current is 1–10 mA; reaching the limit is a fail.
2. Raise the limit to 500 mA and close the master switch. `POWER_GOOD` must go
   high after the TPS22992 controlled rise, `3V3_LOGIC` must be 3.20–3.40 V,
   and native USB must enumerate within 3 s. Expected ESP32 boot current is
   40–300 mA from USB; a sustained value above 400 mA with all 5 V domains off
   is a fail.
3. The safe boot state is `5V_VIDEO`, `5V_DISPLAY`, `5V_ELRS`, `3V3_SD`,
   `LCD_DISP`, backlight PWM, NS4168 enable and buzzer PWM all low. AMT reset is
   asserted until display power is valid. Any enabled RF rail or audible output
   before firmware requests it is a fail.
4. Raise the supply limit to 2.5 A. Enable video, then display logic, release
   AMT reset, assert DISP, and finally ramp backlight. Nominal delays are
   10 ms after a load-switch rise, 20 ms after display 3.3 V Power Good,
   100 ms maximum for AMT ready, and at least 20 ms from valid panel timing to
   the first non-zero backlight PWM. Shutdown is the reverse order.
5. Enable ELRS only after simulator mode is confirmed off and ARM/CH5 is low.
   The factory image never enables ELRS automatically.

## Test-point limits

| Test point | Expected enabled voltage | Ripple/step limit | Disabled limit |
|---|---:|---:|---:|
| `SYS_ALWAYS` | 3.50–4.55 V | 150 mV p-p | present for charging |
| `SYS_SWITCHED` | within 100 mV of SYS_ALWAYS | 150 mV p-p | <0.20 V |
| `3V3_LOGIC` | 3.20–3.40 V | 75 mV p-p | <0.20 V |
| `SYS_SWITCHED_5V` | 4.85–5.15 V | 100 mV p-p | <0.20 V |
| `5V_VIDEO` | 4.80–5.15 V | 75 mV p-p | <0.20 V |
| `5V_DISPLAY` | 4.80–5.15 V | 100 mV p-p | <0.20 V |
| `5V_ELRS` | 4.75–5.15 V | 150 mV p-p | <0.20 V |
| `DISPLAY_3V3` | 3.20–3.40 V | 50 mV p-p | <0.20 V |
| `PANEL_3V3` | 3.15–3.40 V | 50 mV p-p | <0.20 V |
| `3V3_SD` | 3.135–3.465 V | 100 mV p-p | <0.20 V |
| `BL_LED_A` | 15–22 V with panel | 300 mV p-p | <1.0 V |

Use the adjacent ground test point and a ground spring for every ripple test.
No switch node may overshoot its component absolute maximum. Backlight LED
current must be 38.4–41.6 mA at 100% command; 42 mA is the production stop
limit. The hardware 4.99 Ω feedback resistor, not firmware, sets the ceiling.

## Subsystem current increments

At 5.0 V, expected current added by video is 190–300 mA, display logic
120–300 mA, 100% backlight 160–230 mA, ELRS 50–500 mA depending on its declared
power table, buzzer 60–110 mA while sounding, and the optional 8 Ω/1 W speaker
up to 280 mA. An increment outside its interval is a fail and the affected
load switch must be disabled immediately. The firmware prevents simultaneous
full-power speaker and continuous buzzer operation and limits Revision-A PCM
output to 1 W nominal.

## Fault response

A missing video, display, SD or ELRS subsystem produces a bounded timeout,
disables only its rail, records a machine-readable fault and leaves controls/
CRSF running. A rail short must trip the bench limit or local load protection;
firmware then latches that domain off until an explicit factory retry. A short
on `SYS_SWITCHED`, 3.3 V or main 5 V is a whole-board fail. USB removal while a
battery is present and battery insertion/removal while USB is present must not
reset the controller or pulse ELRS/backlight on. Repeated brownout booting is a
fail; low battery instead disables ELRS, dims the backlight and performs the
documented orderly shutdown.
