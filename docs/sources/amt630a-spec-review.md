# AMT630A source review

- Filename: `AMT630A_Spec_V1.2.pdf`
- Internal document revision: Version 1.1, 2014-10
- SHA-256: `4647d609b51416862bd7e3913a625b21d66032c5ab3abe157a4e034b1ce215f7`
- Reviewed pages: all supplied pages (PDF pages 1–9)

The source PDF is not redistributed by this repository.

## Independently derived pin table

| Pin | Function | Pin | Function | Pin | Function | Pin | Function |
|---:|---|---:|---|---:|---|---:|---|
| 1 | CVBS1 | 17 | SPI_CS | 33 | G1 | 49 | B6 |
| 2 | CVBS2 | 18 | SPI_SI | 34 | G2 | 50 | B7 |
| 3 | CVBS3 | 19 | SPI_SO | 35 | G3 | 51 | DCLK |
| 4 | VCOM_ADC | 20 | SPI_CLK | 36 | G4 | 52 | DE |
| 5 | AVSS_ADC | 21 | DVDD 3.3 V | 37 | G5 | 53 | HSYNC |
| 6 | P0.3 / remote | 22 | internal 1.2 V regulator output | 38 | G6 | 54 | VSYNC |
| 7 | SAR2 | 23 | GND | 39 | G7 | 55 | PWM/diagnostic |
| 8 | SAR1 | 24 | R0 | 40 | DVDD 3.3 V | 56 | PWM/diagnostic |
| 9 | SAR0 | 25 | R1 | 41 | internal 1.2 V regulator output | 57 | UART/diagnostic |
| 10 | DVDD 3.3 V | 26 | R2 | 42 | GND | 58 | UART/diagnostic |
| 11 | internal 1.2 V regulator output | 27 | R3 | 43 | B0 | 59 | diagnostic |
| 12 | GND | 28 | R4 | 44 | B1 | 60 | SDA |
| 13 | AGND | 29 | R5 | 45 | B2 | 61 | SCL |
| 14 | XTAL_OUT | 30 | R6 | 46 | B3 | 62 | DVDD 3.3 V |
| 15 | XTAL_IN | 31 | R7 | 47 | B4 | 63 | RESET |
| 16 | AVDD 3.3 V | 32 | G0 | 48 | B5 | 64 | AVDD_ADC 3.3 V |

## Schematic conclusions

- Pins 11, 22, and 41 are decoupled internal core-regulator outputs. They are
  not driven by an external rail.
- Digital 3.3 V feeds pins 10, 21, 40, and 62. Filtered analog 3.3 V feeds
  pins 16 and 64. All returns use the continuous L2 ground plane; analog return
  current is controlled by placement and filtering rather than a split plane.
- CVBS1 is the normal AT7456E output input. CVBS2, CVBS3, and pins 6–9 are
  diagnostic-only and do not select an alternate production signal path.
- Pins 17–20 connect to the W25X05 through a default-to-AMT four-channel mux.
  AMT reset is asserted before the ESP32 may select the recovery side.
- Pins 24–54 connect directly to the panel RGB888/TCON interface. Pins 55–59
  terminate only at diagnostic pads. Pins 60–61 provide runtime status I2C.
- The 27 MHz crystal network is separately calculated from the selected
  crystal load capacitance; it is not copied from the AT7456E network.
- The supplied excerpt is authoritative for package pinout and electrical
  domains. Public register notes are separately cited in `registers.md`; no
  firmware dump or executable reverse-engineering tool is included.
