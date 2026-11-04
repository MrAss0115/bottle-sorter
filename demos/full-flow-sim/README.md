# Full flow manual-result demo

Open `BottleSorter_FullFlow_Sim/BottleSorter_FullFlow_Sim.ino` on Mega 2560. This demo uses the OLD chute, not the new three-bin tray. No ESP32 result is used; OLED and PET-bin guarding are disabled.

USB Serial Monitor: 115200 baud. Align the empty feeder and centre the chute; send `Z`. Load one bottle at fixed station 0 and send `S`. Wait for `STATE: WAIT SIM 1/2/3`, then send `1` (PET left -30), `2` (can middle 0), or `3` (Other right +30). After the chute settles, the upper feeder automatically advances the fifth slot into the drop opening. It then returns to READY after a timed wait. Human-result waiting has no timeout.

To reproduce the optional one-slot approach discussed during the demo, change only `bottleStation = 0` to `bottleStation = 3` inside `startCycle()`, and physically load at the station immediately before recognition. The imported baseline retains 0; later edits on a board are not silently assumed.

`X` stops and locks, not enters test mode. Reset and realign before `Z` can establish references again. No drop is measured.
