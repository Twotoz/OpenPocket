# Architectuur

OpenPocket scheidt de vluchtkritische besturing van langzamere presentatie- en
hardwarediensten.

```text
high priority: inputs -> mixer -> safety -> CRSF channels -> ExpressLRS
low priority:  UI snapshots -> character compositor -> AT7456E SPI
low priority:  RX5808 tune/scan + RSSI
services:      telemetry, storage, audio, USB and maintenance
```

De 250Hz-controltask bezit de kanaaluitvoer en watchdog. OSD, video scan,
bestands-I/O en netwerkdiensten mogen die taak niet blokkeren. De AT7456E-
driver is daarom een begrensde state machine die per tick maximaal één korte
SPI-transactie start of afrondt.

## Presentatie

RivetTX levert een hardware-onafhankelijk raster van 30 kolommen en 16 rijen.
De AT7456E-backend detecteert PAL/NTSC, onderhoudt een shadowscherm en schrijft
alleen gewijzigde runs. PAL gebruikt 16 rijen; NTSC gebruikt de veilige eerste
13 rijen. Tekenuploads zijn onderhoudswerk en worden niet tijdens iedere boot
naar NVM geschreven.

## Video

De RX5808 produceert baseband composietvideo. De AT7456E scheidt sync, mengt
tekens in en stuurt het resultaat naar het LCD. De ESP32 verwerkt geen pixels
en zit niet in het analoge videopad.

## Open ontwerpwerk

- exacte ESP32-S3-module en GPIO-map
- RX5808-revisie, tuning-interface en RSSI-kalibratie
- power tree, lader, accubeveiliging en power-latch
- LCD en connectoren
- KiCad-schema, PCB-zones en mechanische integratie
- productietestpunten en HIL-fixture
