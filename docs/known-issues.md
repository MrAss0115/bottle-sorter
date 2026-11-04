# Known limitations

- Existing sketches control the old chute and are not compatible with the new common tray's angles/transmission by default.
- The initial import uses saved delivery sources, not an extracted copy of a board's firmware. Later manual changes such as starting at station 3 are not assumed.
- Legacy references are manual; pulse counts are commanded positions, not measured positions. There are no home, arrival or drop sensors in the baseline.
- The real-AI baseline enables a PET-only bin guard; a missing/invalid ultrasonic sensor blocks PET. There are no equivalent guards for the other two bins. The manual demo disables this guard and ignores real ESP32 replies.
- One bottle is tracked per cycle. There is no concurrent multi-bottle queue.
- The CAD is a provisional R0.1 design. STL exports are provisional. Physical torque, loaded-bin motion, jamming, print fit and discharge reliability are not established by CAD files or host checks.
- The ESP32 sketch has not been compiled in this environment. A user-supplied demo photo showed one RESULT,0 exchange arriving at Mega and then HOLD PET BIN; this does not establish complete-system reliability or model accuracy.
