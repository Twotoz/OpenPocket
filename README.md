# OpenPocket

OpenPocket is een open, compacte FPV-handzender rond de **ESP32-S3**. De
zender gebruikt [RivetTX](https://github.com/Twotoz/RivetTX) voor bediening,
mixing, veiligheid, CRSF en ExpressLRS. Een **RX5808** ontvangt analoge
5,8GHz-video; een **AT7456E** plaatst het bestaande 30×16 OpenPocket-menu over
het composietbeeld en stuurt dat naar een composiet LCD.

> [!CAUTION]
> OpenPocket is een engineering prototype en nog geen vliegklaar product.
> Bouw en test eerst op een stroombegrensde tafelvoeding. Verwijder propellers
> en maak mechanismen veilig totdat de volledige zender, failsafe, voeding,
> RF-link en videoketen hardware-in-the-loop zijn getest.

## Vaste ontwerpkeuzes

| Onderdeel | Keuze | Functie |
|---|---|---|
| hoofdcontroller | ESP32-S3 | bediening, RivetTX, UI, opslag en USB |
| RC-link | ExpressLRS TX-hardware via CRSF | besturing en telemetrie |
| video-ontvanger | RX5808 | analoge 5,8GHz FPV-video en RSSI |
| video-OSD | AT7456E | PAL/NTSC-tekenoverlay over composiet video |
| scherm | composiet PAL/NTSC LCD | live FPV-beeld en OpenPocket-menu |
| firmware | RivetTX OpenPocket-profiel | 30×16 PAL, veilige 30×13 NTSC-layout |

De ESP32-S3 is bewust gekozen boven de C3 vanwege de extra GPIO, dual-core
taakscheiding, native USB en ruimte voor gimbals, schakelaars, trims, CRSF,
RX5808, AT7456E en toekomstige uitbreidingen. Zie
[ADR-0001](docs/decisions/0001-esp32-s3.md).

## Systeemoverzicht

```text
gimbals / switches / encoder
            |
            v
        ESP32-S3 <---- CRSF ----> ExpressLRS TX ---- RF control
          |   |
          |   +---- SPI/control ----> AT7456E
          +-------- RX5808 tune + RSSI

5.8GHz antenna -> RX5808 VIDEO -> AT7456E VIN
                                  AT7456E VOUT -> composite LCD
```

## Begin hier

1. Lees de [onderdelenlijst](docs/bom.md).
2. Controleer de [bedrading en spanningsniveaus](docs/wiring.md).
3. Bouw eerst het [tafelprototype](docs/build-guide.md).
4. Configureer en flash [RivetTX voor ESP32-S3](docs/firmware.md).
5. Volg de [bring-up- en veiligheidstests](docs/bring-up.md).

## Projectstatus

| Onderdeel | Status |
|---|---|
| RivetTX OpenPocket-tekencompositor en menu | geïmplementeerd en native getest |
| AT7456E SPI-backend, PAL/NTSC en video-loss recovery | geïmplementeerd en native getest |
| ESP32-S3/RX5808/AT7456E referentieschema | nog te tekenen en reviewen |
| definitieve GPIO-toewijzing | wacht op gekozen S3-module, display en PCB-layout |
| RX5808 hardwaredriver en targetmeting | gepland |
| behuizing, voeding, lader en accubeveiliging | nog te kiezen en valideren |
| volledige RF/video/control HIL | vereist vóór gebruik |

De map [`hardware/`](hardware/) wordt de bron voor KiCad-schema, PCB,
productiebestanden en mechanische tekeningen. Tot die bestanden gereviewd zijn,
is deze repository een bouw- en integratiegids voor een tafelprototype.

## Licentie

Documentatie en toekomstige hardwarebestanden worden gepubliceerd onder de
[MIT-licentie](LICENSE). RivetTX heeft zijn eigen repository en licentie.
