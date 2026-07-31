# TF-001A-P3 source review

- Reviewed filename: `TF-001A-P3.pdf` (downloaded as the public LCSC
  `C3021282` datasheet; not redistributed here)
- Manufacturer: SOFNG Electronic Technology Co., Ltd.
- Product: TF-001A-P3 push-push microSD socket
- SHA-256: `4bbff766385a2d4da414b91257904be0da96f1dc7bc8d545a459b4039cbfa012`
- Internal drawing identification: `TF-001A-P3`, 8+1 card-detect,
  normally-open, consumer-electronics revision shown by the public two-page
  drawing
- Reviewed pages: 1–2

## Independently derived conclusions

- P1 DAT2, P2 DAT3, P3 CMD, P4 VDD, P5 CLK, P6 VSS, P7 DAT0, P8 DAT1.
- The ninth electrical pad is a normally-open mechanical card-detect switch;
  a fully inserted card connects it to the grounded shell contact.
- P1–P8 are on 0.80 mm pitch. The footprint includes P9 and all four shell/
  retention lands shown in the vertical-view PCB drawing.
- The maximum body envelope used for collision checking is 14.55 mm wide,
  15.80 mm deep and 1.9 mm high.
- Push-in, locked and pushed-out offsets are 0.51 mm, 1.35 mm and 4.47 mm,
  respectively; the ejected position therefore extends 3.12 mm beyond the
  locked position.
- Contact rating is 50 mA at 24 V DC; this is a signal-contact rating, not a
  statement of the microSD card's transient supply demand. Revision A budgets
  the `3V3_SD` power path separately for at least 300 mA.

The final fabrication gate requires a 1:1 overlay of the plotted footprint,
card outlines and shell pads against this drawing. That overlay has not yet
passed while the parent PCB remains unrouted and fails DRC.
