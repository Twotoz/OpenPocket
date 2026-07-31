# ADR-0002: AMT630A snow-screen display controller

- Status: accepted
- Date: 2026-07-31

## Decision

OpenPocket uses an AMT630A composite-to-TFT controller board after the
AT7456E. The selected board must run a no-blue-screen, or “snow-screen,”
firmware variant and must be supplied with a verified matching TFT panel.

The video chain is:

```text
RX5808 VIDEO OUT -> AT7456E VIN/VOUT -> AMT630A CVBS IN -> matched TFT
```

## Rationale

- the AMT630A accepts composite PAL and NTSC and drives small parallel-RGB TFTs
- a snow-screen variant preserves weak analog information instead of masking
  it with a blue or black no-signal screen
- keeping the AT7456E in front of the display board preserves the existing
  RivetTX 30×16 compositor, custom glyphs, delta updates, and failure handling
- the ESP32-S3 does not need to capture, scale, buffer, or output video pixels

## Constraints

- “AMT630A” is a controller IC, not a complete board specification
- input voltage, CVBS connector, panel pinout, backlight circuit, and flash
  firmware must be verified for the exact PCB revision
- the board and panel are a matched set; a similar 40-pin FFC is not proof of
  electrical or timing compatibility
- the board must demonstrate PAL/NTSC lock, snow on signal loss, prompt video
  recovery, acceptable latency, and clean AT7456E character rendering
- OpenPocket does not control or replace the AMT630A firmware in the first
  hardware revision

## References

- [AMT630A product specification v1.1](https://www.8bcraft.com/wp-content/uploads/2019/06/AMT630A_Brief_Spec_v1.1.pdf)
- [RivetTX AT7456E hardware guide](https://github.com/Twotoz/RivetTX/blob/main/docs/hardware.md)
