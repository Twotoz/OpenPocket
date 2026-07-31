# Wiring

This document uses **net names**, not universal pin numbers. RX5808 and
AT7456E breakout boards exist in several revisions. Record the exact module
markings and check continuity against the matching schematic before wiring.

## Complete signal overview

```text
5.8 GHz antenna
      |
   RX5808
 VIDEO OUT --------> AT7456E VIDEO IN / VIN
                      AT7456E VIDEO OUT / VOUT --------> AMT630A CVBS IN
                                                         |
                                                         +--> matched TFT FFC

RX5808 GND ----------+
AT7456E AGND/DGND ----+---- common video ground ---- AMT630A VIDEO GND
ESP32-S3 GND ---------+

ESP32-S3 DATA/LE/CLK -------------------------------> RX5808 tuning
ESP32-S3 ADC <--------------------------------------- RX5808 RSSI
ESP32-S3 SPI SCLK/MOSI/CS/RESET --------------------> AT7456E control
ESP32-S3 SPI MISO <---------------------------------- AT7456E status
ESP32-S3 CRSF TX/RX <-------------------------------> ExpressLRS TX
```

## Composite-video path

- Use one continuous composite route. Do not leave a second, parallel
  terminated RX5808-to-AMT630A path around the OSD.
- The AMT630A board is the final video load. Do not add a second 75 Ω
  termination without validating the complete source and coupling network.
- Use the AC-coupling and SAG/COUT components specified by the exact AT7456E
  module or relevant datasheet reference circuit.
- Keep video traces away from the ESP32 clock, switching-regulator inductor,
  CRSF lines, and ELRS antenna.

## RX5808 to ESP32-S3

| RX5808 signal | ESP32-S3 connection | Function |
|---|---|---|
| DATA | free output GPIO | serial programming data |
| LE / SELECT | free output GPIO | programming latch |
| CLK | free output GPIO | programming clock |
| RSSI | suitable ADC1 GPIO through scaling/filtering | scan strength |
| VIDEO OUT | no GPIO; connect to AT7456E VIN | composite picture |
| VCC | validated module supply | use the requirement of the exact module |
| GND | common video ground | reference for RSSI and video |

Do not use an ESP32 boot strap, flash/PSRAM pin, or USB D+/D- for RX5808
control. The final firmware driver must not bit-bang DATA/LE/CLK from the
250 Hz control task. Tuning and scanning belong in a service task.

## AT7456E to ESP32-S3

| AT7456E signal | ESP32-S3 / configuration | Requirement |
|---|---|---|
| SCLK | `RIVETTX_AT7456E_SCLK_GPIO` | SPI mode 0, 8 MHz default |
| SDIN / MOSI | `RIVETTX_AT7456E_MOSI_GPIO` | ESP32 to OSD |
| SDOUT / MISO | `RIVETTX_AT7456E_MISO_GPIO` | OSD to ESP32; maximum 3.3 V at ESP pin |
| CS | `RIVETTX_AT7456E_CS_GPIO` | active-low with pull-up during reset |
| RESET | `RIVETTX_AT7456E_RESET_GPIO` | optional active-low; `-1` selects software reset |
| VIN | RX5808 VIDEO OUT | composite input |
| VOUT | selected AMT630A CVBS input | composite output with overlay |
| AGND / DGND | common ground | short, low-impedance connection |

A bare AT7456E normally operates in a 5 V video domain. Use suitable buffers
between 3.3 V and 5 V for a bare IC. Never connect SDOUT directly to an
ESP32-S3 if that line can rise above 3.3 V. A breakout module may already
provide translation; verify its schematic rather than assuming it does.

## AMT630A board and TFT panel

| AMT630A board net | Connection | Requirement |
|---|---|---|
| selected CVBS input | AT7456E VOUT | use the input enabled by the board firmware |
| VIDEO GND | common RX5808/AT7456E ground | short return alongside the video signal |
| board power input | validated display rail | use the exact PCB rating, not the AMT630A IC voltage |
| TFT FFC | matched panel only | verify pin 1, RGB format, timing, and connector orientation |
| backlight output | matched panel backlight | verify current regulation and thermal load |
| key-board input | matching button board/network | optional; preserve known-good factory values |

The first OpenPocket revision treats the AMT630A board as an autonomous
composite-to-TFT stage. Do not connect its internal SPI flash, I2C, UART, or
factory-programming signals to the ESP32-S3. OpenPocket menus remain on the
AT7456E; the AMT630A internal OSD may be used only for display setup.

Before final wiring, prove that this exact board, flash image, and panel show
RF snow when sync is missing and recover quickly when video returns. Many
visually similar AMT630A boards intentionally replace weak video with a blue
screen and therefore do not meet the OpenPocket requirement.

## ExpressLRS and controls

| Function | Connection |
|---|---|
| ESP32 CRSF TX | ExpressLRS module RX |
| ESP32 CRSF RX | ExpressLRS module TX |
| gimbals | suitable ADC1 inputs through appropriate conditioning |
| buttons and switches | GPIO to ground with internal or external pull-up |
| trims and encoder | separate digital GPIOs |

Create a pin-allocation table for the selected ESP32-S3 board before wiring.
RivetTX rejects duplicate or invalid GPIO assignments, but it cannot detect an
electrical conflict with a module function that is not exposed at the header.
