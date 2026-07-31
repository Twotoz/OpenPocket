# Bouwgids voor het tafelprototype

## 1. Bouw de voeding zonder RF of video

1. Stel de tafelvoeding in op 5,0V met een conservatieve stroomlimiet.
2. Voed alleen het ESP32-S3-bord en controleer 3,3V, USB en seriële logging.
3. Voeg gezekerde 5V- en 3,3V-rails toe met lokale ontkoppeling.
4. Meet inschakelpiek, ruststroom en temperatuur voordat andere modules volgen.

## 2. Voeg bediening toe

1. Verbind vier gimbalassen met ADC1-geschikte ingangen.
2. Voeg UP, DOWN, ENTER, BACK en de vaste ARM-schakelaar toe.
3. Voeg pas daarna AUX, trims en encoder toe.
4. Controleer iedere ingang in RivetTX en voer de kalibratie uit.

## 3. Voeg ExpressLRS toe

1. Houd RF-uitgang vergrendeld en gebruik de laagste vermogensstand.
2. Verbind full-duplex 3,3V CRSF TX, RX en GND.
3. Controleer model-ID, telemetrie, kanaalvolgorde en CH5/ARM-polariteit.
4. Test moduleverlies en herstel met het voertuig veilig en zonder propellers.

## 4. Test de composietketen zonder OSD

1. Voed RX5808 en LCD volgens hun eigen specificaties.
2. Verbind tijdelijk RX5808 VIDEO OUT met LCD CVBS IN via de vereiste
   koppeling.
3. Controleer PAL én NTSC, ruisvloer, sync en correcte 75Ω-afsluiting.
4. Verwijder daarna de tijdelijke directe verbinding.

## 5. Plaats de AT7456E ertussen

1. Verbind `RX5808 VIDEO OUT → AT7456E VIN`.
2. Verbind `AT7456E VOUT → LCD CVBS IN`.
3. Verbind level-shifted SCLK, MOSI, MISO, CS en eventueel RESET.
4. Flash het OpenPocket-profiel en controleer de HUD in PAL en NTSC.
5. Trek de antenne/video weg: het systeem moet videoverlies melden terwijl
   bediening, CRSF en telemetrie blijven lopen.

## 6. Voeg RX5808-tuning toe

1. Verifieer DATA, LE, CLK en RSSI op de exacte RX5808-revisie.
2. Start op één bekende frequentie met een afgeschermde of legaal gebruikte
   videosender.
3. Meet de geprogrammeerde frequentie en RSSI-respons.
4. Test pas daarna de volledige scanlijst en video-loss recovery.

## 7. Stopcriteria

Stop direct bij brownouts, onverwachte RF-output, heet wordende onderdelen,
verlies van gemeenschappelijke ground, overbelaste GPIO's, ontbrekende
failsafe of instabiele composietsync. Los de oorzaak op voordat de volgende
module wordt aangesloten.
