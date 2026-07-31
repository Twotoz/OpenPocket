# RivetTX firmware for OpenPocket

OpenPocket uses the `main` branch of
[Twotoz/RivetTX](https://github.com/Twotoz/RivetTX).

## Build

Install and activate ESP-IDF 5.5.2:

```bash
git clone https://github.com/Twotoz/RivetTX.git
cd RivetTX
idf.py set-target esp32s3
idf.py menuconfig
```

Open this menu:

```text
Component config
└── RivetTX hardware
    ├── Use OpenPocket AT7456E analog OSD instead of SSD1306 = enabled
    ├── AT7456E SPI clock GPIO
    ├── AT7456E SPI MOSI / SDIN GPIO
    ├── AT7456E SPI MISO / SDOUT GPIO
    ├── AT7456E active-low chip-select GPIO
    └── AT7456E active-low reset GPIO
```

Configure CRSF, gimbals, buttons, switches, encoder, trims, battery ADC, and
buzzer from the pin table for your board. The OSD pins intentionally have no
universal defaults.

```bash
idf.py build
idf.py flash monitor
```

## Expected behavior

- PAL uses all 30×16 character cells.
- Essential content stays within 30×13 for NTSC.
- Only changed cells are written to the AT7456E.
- Video loss and PAL/NTSC changes trigger a safe redraw.
- SPI and character-NVM work runs outside control, CRSF, and telemetry.
- SSD1306 and AT7456E presentation backends never start together.

The AMT630A snow-screen board is an autonomous composite-to-TFT stage. It does
not require an ESP32 driver in the first hardware revision. Its onboard OSD is
used only for display setup; RivetTX continues to render every OpenPocket menu
through the AT7456E.

## Firmware boundary

The AT7456E backend is implemented. The physical RX5808 target driver, exact
AMT630A board/panel pair, and final OpenPocket pin assignment remain open until
the selected modules and reference schematic have been reviewed.
