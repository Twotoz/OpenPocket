# Hardware sources

The [Revision-A engineering package](rev-a/README.md) is the authoritative
location for the integrated board's requirements, controlled selections, and
release evidence. It will contain the releasable sources for:

- KiCad schematic and PCB files
- controlled BOM with manufacturer part numbers
- integrated AMT630A circuit, licensed flash revision, and matched TFT panel
- Gerber, drill, and pick-and-place files
- mechanical drawings and enclosure interfaces
- test points and fixture documentation

No production files have been released yet. `rev-a/tools/release_gate.py`
refuses artifact generation while primary-source, sourcing, review, or HIL
evidence is missing. Use first articles only on a current-limited bench until
all formal and physical gates pass.
