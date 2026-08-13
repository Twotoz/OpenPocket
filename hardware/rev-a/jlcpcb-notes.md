# JLCPCB Standard PCBA order notes

Product marking: **OpenPocket Rev A — Engineering Prototype**.

- PCB: 115.00 mm × 72.00 mm, eight layers, 1.0 mm finished thickness, 1 oz on
  every copper layer, ENIG, green solder mask unless the quote specifies
  another colour.
- L2 and L7 are uninterrupted ground references. Do not substitute split
  planes. Request JLC's controlled-impedance review for
  native USB and the short 50 Ω RX5808 antenna feed before order approval.
- Assembly service: Standard PCBA, both sides. No substitutions are permitted
  for power ICs, AT7456E, AMT630A, translators, crystals, display connector,
  protection IC/MOSFET, buzzer or speaker amplifier without a schematic-owner
  ECO.
- Use either `OPENPOCKET-REV-A-JLC-PREORDER` with RX5808 `C2908157`, or
  `OPENPOCKET-REV-A-JLC-CONSIGNED-RX5808`. Both variants use the same PCB.
- For the consigned variant, MOD1 must already have the documented RTC6715 SPI
  enable modification. Align pin 1 and shield outline, use the fixture/manual
  placement drawing, inspect every elongated joint, and continuity-test DATA,
  LE, CLK, RSSI, VIDEO, 5 V and all grounds before electrical test.
- JP1 is a hand-soldered diagnostic feature. Factory NORMAL state bridges
  pads 1–2 and 4–5 only. Never bridge BYPASS without cutting both NORMAL
  bridges. This prevents driver contention and removes the OSD input
  termination in bypass mode.
- Do not populate DNP designators. Integral user solder pads and ENIG test
  pads appear in the DNP list but are PCB features, not missing components.
- Program the ESP32 factory image over native USB-C using the supplied flash
  arguments. It verifies/programs the approved AMT630A image through the
  isolated flash mux while AMT reset is asserted, then reports newline-delimited
  JSON. Ship only a unit whose mandatory summary record is `passed:true`.
- J1 is a bottom-contact FH12-40S-0.5SH(55). Inspect pin 1, actuator operation,
  FPC insertion direction and absence of solder bridges at 20× magnification.
- Populate J11 (Hirose U.FL-R-SMT-1(10)) on the bottom side. Inspect its centre
  contact and ground tabs at magnification; J10 intentionally does not exist,
  because a second antenna branch would form a 5.8 GHz stub.
- Keep RX5808, ESP32 U.FL/coax, ELRS and buzzer/speaker acoustic regions free of
  labels, fixture clamps, adhesive and packing material.

The release ZIP is also vendor-neutral. PCBWay or another assembler can use
the generic BOM/position files and the same Gerbers without schematic changes.
