# Architecture

OpenPocket separates flight-critical control from slower presentation and
hardware services.

```text
high priority: inputs -> mixer -> safety -> CRSF channels -> ExpressLRS
low priority:  UI snapshots -> character compositor -> AT7456E SPI
low priority:  RX5808 tune/scan + RSSI
services:      telemetry, storage, audio, USB, and maintenance
```

The 250 Hz control task owns channel output and the watchdog. OSD, video scan,
file I/O, and network services must not block that task. The AT7456E driver is
therefore a bounded state machine that starts or completes at most one short
SPI transaction per tick.

## Presentation

RivetTX provides a hardware-independent grid of 30 columns and 16 rows. The
AT7456E backend detects PAL/NTSC, maintains a shadow frame, and writes only
changed runs. PAL uses all 16 rows; NTSC uses the safe first 13 rows. Character
uploads are maintenance operations and are not written to NVM on every boot.

## Video

The RX5808 produces baseband composite video. The AT7456E separates sync and
mixes in characters. Its composite output enters the selected AMT630A
snow-screen controller board, which decodes and scales the picture for its
matched parallel-RGB TFT panel. The ESP32 does not process pixels and is not
part of the analog video path.

The AMT630A's built-in OSD is not part of the OpenPocket presentation path.
RivetTX continues to render through the AT7456E so menus have one compositor,
one character set, and one tested failure model. The display board must be a
no-blue-screen firmware variant: weak or absent RX5808 video remains visible as
noise rather than being hidden by a solid fallback color.

## Open design work

- exact ESP32-S3 module and GPIO map
- RX5808 revision, tuning interface, and RSSI calibration
- power tree, charger, battery protection, and power latch
- exact AMT630A board revision, matching TFT panel, and connectors
- KiCad schematic, PCB zones, and mechanical integration
- production test points and HIL fixture
