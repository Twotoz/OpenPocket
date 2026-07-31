# PCBWay quote and assembly notes

Classification: **OpenPocket Rev A — Engineering Prototype**.

- Fabrication: four copper layers, 1.0 mm finished thickness, 1 oz all layers,
  ENIG, controlled USB differential pair, impedance coupon/report requested.
- L2 is a continuous ground plane. Do not split or remove ground beneath USB,
  video, RGB clock, or converters except documented RF antenna keep-outs.
- No component substitutions without written approval. Manufacturer part
  numbers, not descriptive values, control procurement.
- Standard assembly includes every electronic component except TFT panel,
  ExpressLRS receiver, gimbals, buttons/switches, battery, antennas, and
  enclosure.
- MOD1 is consigned/manual assembly. PCBWay performs and documents the selected
  SPI-enable resistor removal before installation. Return one modified loose
  witness module and microscope photographs with the lot.
- Program U16 only from the released AMT630A image and verify the published
  SHA-256. Do not use a monitor-board factory dump.
- Default analog-video jumper is NORMAL. BYPASS remains open.
- Backlight is hardware default-off. All 5 V load-switch enables have physical
  pull-downs. AMT630A and AT7456E resets have deterministic boot states.
- Verify J1 pin 1 with the assembly drawing and inspected panel flex before
  population. Connector is bottom contact with direct flex insertion.
- X-ray or microscope inspect exposed pads, charger/converter QFNs, fine-pitch
  AMT630A, AT7456E EP, USB-C anchors, J1 contacts, and MOD1 shield/pads.
- Mark the PCB `OpenPocket Rev A` and `Engineering Prototype`; include the
  manufacturing release ID and source commit in copper or permanent silk.

Quote is not accepted until PCBWay confirms the exact module/IC sourcing,
consigned MOD1 operation, no-substitution list, panel-connector footprint,
stack-up, impedance, and programmed-flash procedure in writing.
