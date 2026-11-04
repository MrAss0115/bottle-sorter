# Three-bin tray implementation checklist

This branch prepares the new common rotating tray. It does not yet contain runnable or validated new-tray firmware.

- [ ] Identify actual lower motor, driver microsteps and tray transmission ratio.
- [ ] Measure pulses per tray output revolution and define the three bin indexes.
- [ ] Select home, arrival and drop-path sensors and document electrical interfaces.
- [ ] Add bounded reference acquisition and sensor-based arrival handling.
- [ ] Preserve ESP32 SCAN/RESULT classification while mapping categories to bin indexes.
- [ ] Require target-bin readiness before the upper feeder releases a bottle.
- [ ] Hold the tray while a bottle falls and until the path is clear.
- [ ] Add timeout/jam fault states and a deliberate recovery procedure.
- [ ] Verify empty and loaded motion with recorded conditions and outcomes.

Do not copy the old -30/0/+30 chute targets into this branch as tray geometry. Nominal bin spacing is 120 degrees; its pulse mapping depends on the actual drive.
