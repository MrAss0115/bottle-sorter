# Legacy chute V2

Open `BottleSorter_Mega_V2/BottleSorter_Mega_V2.ino` for Arduino Mega 2560. This is the older single-bottle controller for a lower chute at -30 / 0 / +30 degrees, not the new common three-bin tray.

The baseline enables OLED and PET-bin ultrasonic guarding. A missing/invalid PET sensor prevents PET release. `Z` records manually aligned references after reset; `S` starts one cycle; `R` retries a held result/bin check; `X` stops and locks until reset. `T` enters individual empty-machine tests, with `F` for one feeder step and `1/2/3` for chute positions.

Route: fixed station 0 -> 1 -> 2 -> 3 -> 4, settle, SCAN, RESULT, chute target, settle, feeder 4 -> 5, timed drop wait. One bottle per cycle; other pockets must be empty. There is no automatic homing or actual arrival/drop feedback.
