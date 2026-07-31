# Onderdelenlijst

Deze BOM beschrijft een **tafelprototype**. Koop nog geen PCB-serie of
accupakket op basis van deze lijst; exacte connectoren, regelaarvermogens en
mechanische maten volgen uit het gereviewde schema en de behuizing.

## Kernonderdelen

| Aantal | Onderdeel | Minimale eis | Status/opmerking |
|---:|---|---|---|
| 1 | ESP32-S3 ontwikkelbord of module | voldoende uitbreekbare GPIO, USB en minimaal 8 MB flash aanbevolen | vaste MCU-familie; definitief bord nog kiezen |
| 1 | RX5808 5,8GHz ontvangermodule | VIDEO OUT, RSSI en programmeerbare DATA/LE/CLK beschikbaar | controleer de exacte printrevisie en pinout |
| 1 | AT7456E OSD-module | 30×16 teken-OSD, SPI, VIDEO IN/OUT, 27MHz-klok en video-passives aanwezig | module aanbevolen voor eerste prototype |
| 1 | composiet LCD | accepteert PAL én NTSC en heeft gedocumenteerde 75Ω-video-ingang | resolutie is niet bepalend voor het tekenraster |
| 1 | ExpressLRS TX-module | full-duplex, niet-geïnverteerde 3,3V CRSF UART | een normale ELRS-ontvanger is niet voldoende |
| 2 | twee-assige gimbal | analoge uitgang passend bij ESP32 ADC na conditionering | vier primaire assen totaal |
| 1 | vaste ARM-schakelaar | twee standen | niet delen met menuknoppen |
| 3 | AUX-schakelaar | twee of drie standen | optioneel voor eerste tafeltest |
| 4 | menubediening | UP, DOWN, ENTER en BACK | actieve-laag GPIO met pull-up |
| 1 | draai-encoder met drukknop | quadratuur A/B plus drukcontact | optioneel maar aanbevolen |
| 1 | geschikte 5,8GHz-antenne | 50Ω en passende connector/polarisatie | nooit ontvangen/testen met beschadigde connector |

## Voeding en signaalintegriteit

| Aantal | Onderdeel | Doel |
|---:|---|---|
| 1 | stroombegrensde 5V tafelvoeding, minimaal 2A | eerste bring-up zonder accu |
| 1 | 3,3V-regelaar indien niet op het S3-bord aanwezig | ESP32-S3 en 3,3V-logica |
| 1 | 74AHCT125 of gelijkwaardige 3,3V→5V buffer | SCLK, MOSI/SDIN en CS naar kale 5V-OSD-logica |
| 1 | 5V→3,3V unidirectionele buffer | AT7456E SDOUT/MISO naar ESP32-S3 |
| 1 | open-drain transistortrap | optionele AT7456E RESET |
| meerdere | 100nF keramische condensatoren | bij iedere digitale en analoge voedingspin |
| meerdere | 10–470µF low-ESR bulkcondensatoren | lokaal bij OSD, LCD, RX5808 en ELRS volgens gemeten piekbelasting |
| meerdere | serieweerstanden 22–100Ω | optioneel op snelle digitale lijnen na meting |
| 1 | zekering of resetbare PTC | begrenzing van de prototypevoeding |

Een kant-en-klare AT7456E-module kan level-shifting, klok en videopassives al
bevatten. Verifieer het schema; vertrouw niet alleen op een producttitel.

## Mechanisch en later productwerk

- afgeschermde of zorgvuldig geroute composietvideokabel
- connectoren met trekontlasting voor gimbals, LCD en RF-module
- hoofdschakelaar en gecontroleerde power-latch
- beveiligde accu, lader, celbewaking en geschikte zekering
- passieve piezo of haptische waarschuwing
- behuizing, knoppen, sticks, draagbeugel en antennebevestiging
- KiCad-PCB met gescheiden RF-, video-, digitaal- en vermogensretourpaden

Accutype, lader en vermogensarchitectuur zijn bewust nog niet vastgelegd. Die
keuze vereist een afzonderlijke thermische, laad- en foutanalyse.
