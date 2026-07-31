# AMT630A firmware target

Target image name: `amt630a_at050tn33.bin`

Target behavior:

- Innolux AT050TN33 V.1, 480 × 272, 16:9 full-panel output;
- automatic PAL and NTSC detection;
- automatic startup and recovery after composite-sync loss;
- no panel-selection prompt;
- no deliberate blue-screen substitution; weak/no signal remains snow;
- external ESP32 control of backlight and AMT630A reset.

## Licensing and provenance gate

No binary is committed yet. The available reverse-engineered reference archive
identifies Martin Korth as copyright holder and describes itself as a freeware
sample, but it does not include a license granting this project the clear
commercial redistribution rights needed for a PCBWay-programmed product.
The no$x51 tool is separately described as free for non-commercial use. An
unknown monitor-board factory dump is not acceptable provenance.

Release requires either written redistribution permission for the selected
source and toolchain or a clean-room source implementation under a compatible
license. Until then, `build.py` exits with a machine-readable blocker and no
image/checksum is generated.

## Required build output

Once the source/license gate is resolved, the deterministic build must create:

```text
amt630a_at050tn33.bin
amt630a_at050tn33.bin.sha256
build-manifest.json
```

The manifest records source revision, toolchain name/version/hash, panel timing,
PAL/NTSC settings, no-signal policy, and output SHA-256. RivetTX factory mode
must identify the W25X05, erase, program, read back, hash, release the flash bus,
boot AMT630A, and report panel/video status.

## Technical references

- AMT630A brief and full register documentation for pinout, 27 MHz clock,
  display timing, composite input, reset, and SPI flash behavior.
- Reverse-engineered no$x51-compatible source only as a behavior/register
  reference subject to its copyright and licensing terms.
- The exact Innolux panel datasheet for pixel-clock, porch/sync polarity, DISP,
  RGB order, FPC pinout, and power sequencing.

Register guesses and proprietary dumps must not enter the manufacturing branch.
