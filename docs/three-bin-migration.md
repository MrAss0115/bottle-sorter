# Three-bin tray migration

## Confirmed direction

The fixed upper feed deck has a local drop opening and six rotating partitions. The lower common tray carries three removable bins and rotates to place the selected bin under that opening. Fusion R0.1 represents this concept; bin spacing is nominally 120 degrees.

## Controller adaptation still required

- Confirm real motor shaft, driver current/microsteps, transmission ratio and pulses per tray revolution. A 120-degree geometric spacing alone is not enough to determine a pulse count.
- Establish category-to-bin index mapping and a measured zero reference. Decide sensor type, electrical levels, placement and target markers with the team.
- Implement bounded homing, debounced/stable arrival detection and timeout/fault handling after the hardware is defined. Manual reference remains the legacy baseline, not automatic homing.
- Move the selected bin into position and confirm arrival before releasing the upper feeder. Keep the tray stationary during falling and until the drop path is clear; define drop sensing rather than assuming a timer proves clearance.
- Verify coupling, support rollers, acceleration, clearance, step loss and motion under realistic bin loads. Stop on missing markers or jams rather than indefinitely adding steps.

## Proposed code modules

`Config`: hardware revision and measured parameters; `MotorControl`: pulse scheduling; `Sensors`: observations and debouncing; `SerialProtocol`: messages; `SorterStateMachine`: allowed transitions and interlocks. Add modules incrementally while retaining a working baseline.

## Planned flow

References -> ready -> feed to recognition -> request classification -> select bin -> move tray -> confirm bin position -> release bottle -> confirm/allow clearance -> ready. Actual sensor-driven transitions are pending implementation and hardware validation.

No runnable new-tray sketch is supplied yet. Future portal/frontend/database work is also planned, not implemented here.
