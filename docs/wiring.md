# Bedrading

Dit document gebruikt **netnamen**, geen universele pinnummers. RX5808- en
AT7456E-breakoutboards bestaan in meerdere revisies. Noteer eerst de exacte
modulemarkeringen en controleer continuïteit tegen het bijbehorende schema.

## Videoketen

```text
5.8GHz antenna
      |
   RX5808
 VIDEO OUT --------> AT7456E VIDEO IN / VIN
                      AT7456E VIDEO OUT / VOUT --------> LCD CVBS IN

RX5808 GND ----------+
AT7456E AGND/DGND ----+---- common video ground ---- LCD VIDEO GND
ESP32-S3 GND ---------+
```

- Gebruik één doorlopende composietroute; leg geen tweede, parallel afgesloten
  RX5808→LCD-route om de OSD heen.
- Het LCD vormt de enkele 75Ω-belasting. Voeg niet willekeurig een tweede
  75Ω-afsluiting toe.
- Gebruik de AC-koppeling en SAG/COUT-componenten van de exacte AT7456E-module
  of datasheetreferentie.
- Houd video weg van de ESP32-klok, DC/DC-spoel, CRSF en ELRS-antenne.

## RX5808 naar ESP32-S3

| RX5808-signaal | ESP32-S3 | Functie |
|---|---|---|
| DATA | vrije output-GPIO | seriële programmeerdata |
| LE / SELECT | vrije output-GPIO | programmeerlatch |
| CLK | vrije output-GPIO | programmeerklok |
| RSSI | ADC1-geschikte GPIO via schaal/filter | scansterkte |
| VIDEO OUT | geen GPIO; naar AT7456E VIN | composietbeeld |
| VCC | gevalideerde modulevoeding | gebruik waarde van exacte module |
| GND | gemeenschappelijke video-ground | referentie voor RSSI en video |

Gebruik geen ESP32-opstartstrap, flash/PSRAM-pin of USB D+/D− voor RX5808-
besturing. De uiteindelijke firmwaredriver moet DATA/LE/CLK niet vanuit de
250Hz-controltask bitbangen; tuning en scanning horen bij de servicetaak.

## AT7456E naar ESP32-S3

| AT7456E-signaal | ESP32-S3/configuratie | Opmerking |
|---|---|---|
| SCLK | `RIVETTX_AT7456E_SCLK_GPIO` | SPI mode 0, standaard 8MHz |
| SDIN/MOSI | `RIVETTX_AT7456E_MOSI_GPIO` | ESP32 naar OSD |
| SDOUT/MISO | `RIVETTX_AT7456E_MISO_GPIO` | OSD naar ESP32; maximaal 3,3V aan ESP-pin |
| CS | `RIVETTX_AT7456E_CS_GPIO` | actief laag, pull-up tijdens reset |
| RESET | `RIVETTX_AT7456E_RESET_GPIO` | optioneel actief laag; `-1` gebruikt software-reset |
| VIN | RX5808 VIDEO OUT | composiet ingang |
| VOUT | LCD CVBS IN | composiet uitgang met overlay |
| AGND/DGND | common ground | korte, lage-impedantie verbinding |

Een kale AT7456E draait normaal in een 5V-videodomein. Gebruik voor een kaal
IC geschikte buffers tussen 3,3V en 5V. Sluit SDOUT nooit rechtstreeks op een
ESP32-S3 aan als die lijn boven 3,3V kan komen.

## CRSF en bediening

| Functie | Verbinding |
|---|---|
| ESP32 CRSF TX | ExpressLRS module RX |
| ESP32 CRSF RX | ExpressLRS module TX |
| gimbals | ADC1-geschikte ingangen via passende conditionering |
| knoppen/schakelaars | GPIO naar GND, intern of extern opgetrokken |
| trims/encoder | afzonderlijke digitale GPIO's |

Maak vóór het bedraden een pintabel voor het gekozen ESP32-S3-bord. RivetTX
weigert dubbele of ongeldige GPIO-toewijzingen, maar kan elektrische conflicten
met niet-uitgebroken modulefuncties niet detecteren.
