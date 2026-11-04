# Setup

## Legacy Mega and manual demo

Select Arduino Mega 2560 (`arduino:avr:mega`) in Arduino IDE. Open a sketch from its matching folder; do not concatenate the real-AI sketch and manual demo. The real-AI Mega sketch needs Adafruit GFX and Adafruit SSD1306. The standalone manual demo only needs the Arduino AVR core.

USB Serial Monitor is 115200 baud. On the real-AI Mega sketch, the ESP32 board-to-board Serial1 port is 9600 baud, not the USB rate. Confirm wiring and empty-machine alignment before recording references with Z. The software has no automatic homing or position/drop feedback.

## ESP32

Target hardware: Freenove ESP32-S3-WROOM N8R8 with OV3660. Install the ESP32 board support appropriate to your IDE; validate flash/PSRAM/camera settings on the actual board. The ESP32 build is not validated by this repository's AVR checks.

1. Install `dependencies/ei-dajimk-project-1-arduino-1.0.5.zip` using Arduino IDE Add .ZIP Library.
2. Open `firmware/esp32/Bottle_AI_Camera_Preview/Bottle_AI_Camera_Preview.ino`.
3. Copy `local_secrets.example.h` to `local_secrets.h` in that same sketch folder and replace the example password with your own password of at least eight characters. The local file is ignored by Git.
4. Verify board and camera settings, compile, upload, and inspect the serial output.

The preview hotspot is local; camera inference runs on the ESP32. The code captures 640x480 JPEG, decodes to RGB, centre-crops to 480x480 and resizes to the model's 96x96 input. Threshold 0.65 is a decision threshold, not a measured accuracy. USB M and the preview webpage classify locally but do not send a result to Mega; the automatic UART path begins with Mega's SCAN request.
