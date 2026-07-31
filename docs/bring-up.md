# Bring-up and acceptance tests

Complete this checklist for every physical revision. Keep measurements,
photographs, and the firmware commit with the test report.

## Electrical

- [ ] Every supply rail is correct both unloaded and loaded.
- [ ] No ESP32 GPIO is exposed to more than 3.3 V.
- [ ] Current limiting, a fuse, and local bulk capacitance are present.
- [ ] AMT630A/backlight startup, ELRS transmission, and video lock cause no brownout.
- [ ] AT7456E clock and SPI mode 0 have been checked with a logic analyzer.
- [ ] The composite path has exactly one correct 75 Ω termination.

## Controls and RF

- [ ] All gimbals are calibrated and move in the correct direction.
- [ ] CH5 is low at boot, during faults, after module loss, and in maintenance.
- [ ] ARM and AUX functions use only their assigned switches.
- [ ] CRSF continues at 250 Hz during OSD redraw and menu use.
- [ ] ExpressLRS binding, model ID, telemetry, and failsafe are verified.

## Video and OSD

- [ ] PAL lock shows all 30×16 cells without clipped edges.
- [ ] NTSC lock keeps all essential information inside rows 0–12.
- [ ] Menus, selection, edit mode, and warnings are readable.
- [ ] A one-character change does not trigger a full-screen redraw.
- [ ] PAL-to-NTSC and NTSC-to-PAL changes recover without a reboot.
- [ ] Video loss shows a warning and recovery causes a clean redraw.
- [ ] An absent or disconnected AT7456E leaves control responsive and safe.
- [ ] Lost or weak video produces snow, never a persistent blue/black fallback.
- [ ] Loss-to-snow and snow-to-picture recovery times are measured and accepted.
- [ ] PAL and NTSC both fill the intended TFT area without wrong scaling.
- [ ] The AMT630A board adds no unacceptable camera-to-photon latency.

## Endurance

- [ ] At least two hours of simultaneous control, telemetry, and video.
- [ ] Repeated power cycles and controlled brownout injection.
- [ ] Thermal check at the maximum selected RF, AMT630A, and backlight load.
- [ ] No character-NVM upload on every boot.
- [ ] No control deadlines missed by SPI, logging, USB, or UI activity.

A successful bench test is not permission to test with fitted propellers.
Perform separate vehicle, range, and failsafe tests afterward.
