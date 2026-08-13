# OpenPocket Rev-A manual routing package

Open `hardware/rev-a/openpocket-rev-a.kicad_pro` in KiCad 9. The schematic is
the authoritative netlist and passes KiCad ERC with zero errors and warnings.

The PCB is 115 x 72 mm with six copper layers:

1. `F.Cu` — components and critical signals
2. `GND` — uninterrupted ground plane; do not route signals here
3. `PWR` — power distribution and slow signals where appropriate
4. `SIG1` — signal routing
5. `SIG2` — signal routing
6. `B.Cu` — secondary components and signal routing

Mechanical constraints already fixed in the board:

- J1 is horizontal; pin 1 is at X=20 mm and the FPC inserts from below.
- USB-C and microSD are at the top edge.
- The L2 GND zone and local ground fanout are intentional and should remain.

Follow `hardware/rev-a/routing-constraints.md`. Hand-route USB, RX5808 RF,
analog video, crystal/switching loops, and high-current paths before ordinary
signals. Final acceptance requires zero DRC violations and zero unconnected
items on the exact board used to generate manufacturing files.
