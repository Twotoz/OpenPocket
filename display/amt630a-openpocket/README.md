# OpenPocket AMT630A firmware

This directory contains an original MIT-licensed SDCC/mcs51 firmware for the
AMT630A used by OpenPocket Revision A. It is built from register documentation,
the AMT630A product specification, and public reference-circuit observations;
it is not a monitor-board dump and contains no vendor firmware.

`make test` builds a deterministic 64 KiB W25X05 image and verifies panel
timing, PAL/NTSC state handling, sync-loss recovery, CVBS1 selection, RGB pin
muxing, and that documented snow/blue-substitution controls are disabled. The
controller keeps TFT timing active during video loss and pulses decoder resync
until video returns. Whether a particular weak RF signal visibly produces the
desired snow texture remains a first-article acceptance measurement.

The RivetTX factory service holds AMT RESET low, selects the ESP32 side of U19
(SN74CB3Q3257PWR), checks JEDEC ID `EF 30 10`, erases/programs/reads every byte,
compares SHA-256, restores AMT ownership, releases reset, then waits for I2C
status before enabling the backlight.
