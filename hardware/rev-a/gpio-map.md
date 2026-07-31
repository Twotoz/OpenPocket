# Revision-A GPIO allocation

Target module: ESP32-S3-MINI-1U-N8, 8 MiB flash, no PSRAM. GPIO19/20 are native
USB. GPIO0, GPIO45, and GPIO46 remain unassigned boot straps. Analog controls
and RX5808 RSSI use ADC1 only.

| GPIO | Direction | Function | Electrical notes |
|---:|---|---|---|
| 1 | input | left gimbal X | ADC1, 3.3 V maximum, RC filter |
| 2 | input | left gimbal Y | ADC1, 3.3 V maximum, RC filter |
| 3 | input | right gimbal X | ADC1, 3.3 V maximum, RC filter |
| 4 | input | right gimbal Y | ADC1, 3.3 V maximum, RC filter |
| 5 | input | RX5808 RSSI | ADC1, filtered and clamped |
| 6 | — | reserved test capacity | do not populate |
| 7 | output | RX5808 DATA | 3.3 V RTC6715 SPI-like bus |
| 8 | output | RX5808 LE | latch enable |
| 9 | output | RX5808 CLK | bounded GPIO state machine |
| 10 | input | TCA9535 INT | active low, 3.3 V pull-up |
| 11 | output | AT7456E SCLK | through SN74AHCT125 |
| 12 | output | AT7456E MOSI | through SN74AHCT125 |
| 13 | input | AT7456E MISO | guaranteed 5 V-to-3.3 V translator |
| 14 | output | AT7456E CS | through SN74AHCT125; hardware pull-up |
| 15 | bidirectional | board I2C SDA | BQ25895, MAX17048, two TCA9535 |
| 16 | output | board I2C SCL | 400 kHz maximum |
| 17 | output | ELRS_RX | ESP32 CRSF TX through series resistor |
| 18 | input | ELRS_TX | ESP32 CRSF RX through series resistor |
| 19 | bidirectional | USB D- | native USB only |
| 20 | bidirectional | USB D+ | native USB only |
| 21 | output | AT7456E RESET | active low, level shifted |
| 33 | input | encoder A | direct active-low quadrature |
| 34 | input | encoder B | direct active-low quadrature |
| 35 | output | buzzer/haptic driver | transistor input, not direct load |
| 36 | output | AMT flash ownership | break-before-make bus switch control |
| 37 | — | reserved | do not use until module routing review |
| 38 | output | AMT630A RESET | active low |
| 39 | output | AMT flash CS | factory programming only |
| 40 | output | 5V_VIDEO enable | safe external pull-down |
| 41 | output | 5V_DISPLAY enable | safe external pull-down |
| 42 | output | 5V_ELRS enable | safe external pull-down |
| 43 | input | BQ25895 INT | active low |
| 44 | input | MAX17048 ALERT | active low |
| 47 | output | TPS61165 PWM/EN | 20 kHz, default off |
| 48 | input | USB VBUS sense | protected resistor divider |

## TCA9535 control allocation

Both expanders are PCBWay-installed on the board I2C bus. Inputs are active
low with external pull-ups. Their I2C reads occur in `board_io_task`; the 250 Hz
control task consumes only the cached atomic snapshot.

| Snapshot bit | Input |
|---:|---|
| 0–3 | UP, DOWN, ENTER, BACK |
| 4 | ARM / AUX1 |
| 5–6 | AUX2 high / low |
| 7–8 | AUX3 high / low |
| 9–10 | AUX4 high / low |
| 11 | encoder press |
| 12–19 | AIL-, AIL+, ELE-, ELE+, THR-, THR+, RUD-, RUD+ |
| 20–31 | spare external controls/test pads |

The matching firmware defaults are maintained in RivetTX
`sdkconfig.openpocket-rev-a.defaults`. Pin duplication, invalid outputs, and
RX5808 conflicts fail startup validation.
