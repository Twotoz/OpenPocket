# Bring-up en acceptatietests

Vink deze lijst af per fysieke revisie en bewaar meetresultaten, foto's en
firmwarecommit bij het testrapport.

## Elektrisch

- [ ] Iedere voedingsrail klopt onbelast en belast.
- [ ] Geen ESP32-GPIO ziet meer dan 3,3V.
- [ ] Stroomlimiet, zekering en lokale bulkcapaciteit zijn aanwezig.
- [ ] Geen brownout bij LCD-start, ELRS-zenden of video-lock.
- [ ] AT7456E-clock en SPI mode 0 zijn met een logic analyzer gecontroleerd.
- [ ] Composietpad heeft precies één correcte 75Ω-belasting.

## Bediening en RF

- [ ] Alle gimbals zijn gekalibreerd en bewegen in de juiste richting.
- [ ] CH5 is laag bij boot, fout, moduleverlies en onderhoud.
- [ ] ARM en AUX gebruiken uitsluitend hun toegewezen schakelaars.
- [ ] CRSF blijft op 250Hz doorlopen tijdens OSD-redraw en menugebruik.
- [ ] ExpressLRS bind, model-ID, telemetrie en failsafe zijn gecontroleerd.

## Video en OSD

- [ ] PAL-lock toont alle 30×16 cellen zonder afgesneden randen.
- [ ] NTSC-lock toont alle essentiële informatie binnen rijen 0–12.
- [ ] Menu, selectie, editmodus en waarschuwingen zijn leesbaar.
- [ ] Een enkele tekenwijziging veroorzaakt geen volledige redraw.
- [ ] PAL↔NTSC-wissel herstelt zonder reboot.
- [ ] Videoverlies toont een waarschuwing en videoherstel tekent opnieuw.
- [ ] Losse of ontbrekende AT7456E houdt de zender veilig en responsief.

## Duurtest

- [ ] Minimaal twee uur gelijktijdige control, telemetrie en video.
- [ ] Herhaalde power-cycles en brownout-injectie.
- [ ] Thermische controle bij maximale gekozen RF- en LCD-belasting.
- [ ] Geen teken-NVM-upload bij iedere boot.
- [ ] Geen control-deadlines gemist door SPI, logging, USB of UI.

Een geslaagde tafeltest is geen toestemming om met gemonteerde propellers te
testen. Voer daarna afzonderlijke voertuig-, bereik- en failsafetests uit.
