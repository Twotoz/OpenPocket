# Register derivation

The immutable table in `src/registers.c` selects the 480×272 24-bit RGB+DE
output (`FC00=00`, `FD34..FD43=22`, `FD50=0F`), the documented 480×272 PLL
tuple (`FD0A=A8`, `FD0F=09`, `FD16=0A`), CVBS1, and separate PAL/NTSC scaler
timings. `FED7[7,6,1,0]` and `FEDC[7,6,4]` remain clear: those documented bits
disable snow or request a blue/background substitute.

The selected input sequence is the older-reference CVBS1 mapping:
`FED7[4:3]=0`, `FED8[7:6]=2`, `FEDC[5:4]=0`, then `FED7[4:3]=3`. A fixture
test must confirm that CVBS1 corresponds to physical pin 1 on the assembled
AMT630A; this is an execution check against an already frozen circuit, not an
unresolved architecture choice.
