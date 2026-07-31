# Bench prototype build guide

## 1. Build the power system without RF or video

1. Set the bench supply to 5.0 V with a conservative current limit.
2. Power only the ESP32-S3 board and verify 3.3 V, USB, and serial logging.
3. Add fused 5 V and 3.3 V rails with local decoupling.
4. Measure inrush, idle current, and temperature before adding another module.

## 2. Add controls

1. Connect the four gimbal axes to suitable ADC1 inputs.
2. Add UP, DOWN, ENTER, BACK, and the dedicated ARM switch.
3. Add AUX controls, trims, and the encoder only after the basic inputs work.
4. Verify every input in RivetTX and complete calibration.

## 3. Add ExpressLRS

1. Keep RF output locked and select the lowest power setting.
2. Connect full-duplex 3.3 V CRSF TX, RX, and ground.
3. Check model ID, telemetry, channel order, and CH5/ARM polarity.
4. Test module loss and recovery with the vehicle safe and propellers removed.

## 4. Test composite video without the OSD

1. Power the RX5808 and LCD according to their own specifications.
2. Temporarily connect RX5808 VIDEO OUT to LCD CVBS IN through the required
   coupling network.
3. Verify PAL and NTSC, noise floor, sync, and the single 75 Ω termination.
4. Remove the temporary direct connection afterward.

## 5. Insert the AT7456E

1. Connect `RX5808 VIDEO OUT -> AT7456E VIN`.
2. Connect `AT7456E VOUT -> LCD CVBS IN`.
3. Connect level-shifted SCLK, MOSI, MISO, CS, and optional RESET.
4. Flash the OpenPocket profile and verify the interface in PAL and NTSC.
5. Remove the antenna or video source. Video loss must be reported while
   controls, CRSF, and telemetry continue uninterrupted.

## 6. Add RX5808 tuning

1. Verify DATA, LE, CLK, and RSSI on the exact RX5808 revision.
2. Start on one known frequency with a shielded or legally operated video
   transmitter.
3. Measure the programmed frequency and RSSI response.
4. Test the full scan table and video-loss recovery only after that succeeds.

## 7. Stop conditions

Stop immediately after any brownout, unexpected RF output, overheating,
broken common ground, GPIO overvoltage, missing failsafe, or unstable
composite sync. Correct the root cause before connecting the next subsystem.
