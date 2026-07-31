# Revision-A factory test protocol

Factory firmware emits one newline-delimited JSON object per check over native
USB CDC. Every object contains `fixture`, `serial`, `firmware_commit`, `test`,
`passed`, `measurement`, `units`, and `limit`. The final record is
`{"test":"summary","passed":true}` only when all mandatory checks pass.

## Safe sequence

1. Visual/microscope inspection and resistance-to-ground checks with no cell,
   TFT, ELRS, or antennas attached.
2. Apply current-limited USB 5 V. Confirm 3.3 V, charger power path, USB
   enumeration, BOOT, RESET, and safe-off 5 V enables/backlight.
3. Check BQ25895 identity/status, MAX17048 absent-battery behavior, VBUS sense,
   both TCA9535 devices, and every control input with fixture switches.
4. Test gimbal ADC stimulus and verify monotonic calibrated readings.
5. Loop back CRSF UART and verify no transmission while simulator mode is
   active. ARM/CH5 must remain low.
6. Enable each switched 5 V domain separately and measure rise time, steady
   voltage, inrush, and off leakage.
7. With no card installed, verify active-high card detect and `3V3_SD` below
   0.20 V. Insert the fixture FAT32 card, require detect below 0.30 V after
   80 ms, rail 3.135–3.465 V with less than 100 mV excursion, then read/write/
   readback a 512-byte pseudorandom block at 400 kHz and 20 MHz. Remove it
   during a bounded logging run and require zero control or CRSF deadline
   misses. The JSON tests are `sd_detect`, `sd_power`, `sd_rw`, and
   `sd_hot_remove`.
8. Identify, erase, program, read back, and SHA-256 verify W25X05 while AMT630A
   reset is asserted and the isolated bus belongs to ESP32. Release ownership
   before AMT630A reset.
9. Verify AT7456E SPI identity/activity, reset, custom glyph upload, PAL/NTSC
   status, and independent sync-loss reporting.
10. Tune RX5808 through all 48 table entries. Record exact RTC6715 frames, RSSI
   ADC baseline, and video output at TP_VRX_VIDEO. Cancel a scan during dwell
   and verify the saved channel is restored.
11. Apply fixture PAL and NTSC composite sources through the NORMAL chain.
    Verify TP_OSD_VIDEO, OSD overlay, AMT630A automatic recovery, snow/no-blue
    behavior, panel timings, and colour bars.
12. Ramp backlight PWM while measuring VLED+, total LED current, switch-node
    waveform, inductor/diode temperature, and default-off restart.
13. Attach a protected fixture cell and NTC. Verify conservative charge current,
    thermal/current reduction, gauge voltage/SOC, operation while charging,
    USB-only operation, and low-battery shutdown.

Composite test points are oscilloscope/fixture measurements, not user wiring.
No propeller or powered aircraft mechanism is permitted during factory test.

First articles additionally require thermal imaging, RF coexistence, ELRS at
10 mW and 100 mW, antenna-region validation, multi-hour endurance, and a
propeller-off HIL report. Until those pass, the board remains an engineering
prototype.
