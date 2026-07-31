# RivetTX-firmware voor OpenPocket

OpenPocket gebruikt de `main`-branch van
[Twotoz/RivetTX](https://github.com/Twotoz/RivetTX).

## Bouwen

Installeer en activeer ESP-IDF 5.5.2:

```bash
git clone https://github.com/Twotoz/RivetTX.git
cd RivetTX
idf.py set-target esp32s3
idf.py menuconfig
```

Ga in menuconfig naar:

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

Stel daarna CRSF, gimbals, knoppen, schakelaars, encoder, trims, batterij-ADC
en buzzer in volgens de eigen pintabel. De OSD-pinnen hebben bewust geen
universele standaardwaarde.

```bash
idf.py build
idf.py flash monitor
```

## Verwacht gedrag

- PAL gebruikt alle 30×16 tekencellen.
- Belangrijke inhoud blijft binnen 30×13 voor NTSC.
- Alleen gewijzigde tekens worden naar de AT7456E geschreven.
- Videoverlies en PAL/NTSC-wissels veroorzaken een veilige redraw.
- SPI- en teken-NVM-werk draait buiten control, CRSF en telemetrie.
- De SSD1306 en AT7456E worden nooit tegelijk als presentatie gestart.

## Firmwaregrens

De AT7456E-backend is geïmplementeerd. Een concrete RX5808-hardwaredriver en
de definitieve OpenPocket-pintoewijzing worden pas vastgezet nadat de exacte
module en het referentieschema zijn gereviewd.
