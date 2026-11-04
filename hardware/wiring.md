# Wiring baseline

This table documents the legacy chute baseline. The new tray's motor, transmission and sensor wiring must be confirmed before extending it.

| Function | Mega pin | Connection |
|---|---|---|
| Upper motor pulse | D2 | Upper driver PUL+ |
| Upper motor direction | D3 | Upper driver DIR+ |
| Lower motor pulse | D4 | Lower driver PUL+ |
| Lower motor direction | D5 | Lower driver DIR+ |
| ESP32 command TX1 | D18 | Level conversion to ESP32 GPIO41 RX |
| ESP32 result RX1 | D19 | ESP32 GPIO42 TX |
| Start button | D22 | Button to GND, INPUT_PULLUP |
| PET ultrasonic TRIG | D24 | Sensor TRIG |
| PET ultrasonic ECHO | D25 | Sensor ECHO |
| OLED SDA / SCL | D20 / D21 | I2C address 0x3C |

Use a common signal ground. The established driver test wiring uses PUL- and DIR- at ground; match the actual driver's electrical interface rather than assuming all drivers are identical. Driver motor power comes from the appropriate external supply; Mega GPIO does not supply winding current. Driver microstep and current switch settings depend on the actual unit.

The old firmware assumes 1600 commanded pulses per output revolution with direct motion. This is not yet a confirmed value for the common three-bin tray. Record actual motor, microstep and transmission data in the BOM before using new angles.
