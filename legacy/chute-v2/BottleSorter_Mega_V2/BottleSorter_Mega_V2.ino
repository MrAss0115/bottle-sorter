/*
  BottleSorter V2 - Arduino Mega 2560
  Feeder: D2 PUL+, D3 DIR+. Sort chute: D4 PUL+, D5 DIR+.
  ESP32 UART remains Serial1 D18 TX / D19 RX, 9600 baud:
  SCAN\n -> RESULT,0 / RESULT,1 / RESULT,2 / RESULT,-1\n.
  One bottle per cycle. All other feeder pockets must be empty.
  No home/arrival/drop sensors: positions are commanded, not measured.
  USB 115200: Z=confirm both references, S=start, R=retry held bottle,
  X=software stop+lock, T=empty-machine test mode, F=one feeder step,
  1/2/3=left/middle/right (test mode only), P=status, H=help.
*/
#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <string.h>

// ===== EDIT THESE PARAMETERS AFTER EMPTY-MACHINE CALIBRATION =====
const byte FEED_PUL_PIN = 2;
const byte FEED_DIR_PIN = 3;
const byte SORT_PUL_PIN = 4;
const byte SORT_DIR_PIN = 5;
const byte FEED_FORWARD_LEVEL = HIGH; // Verify route 0->1->2->3->4->5, NOT 0->5.
const byte SORT_POSITIVE_LEVEL = HIGH; // Verify positive angle points toward right.
const long FEED_PULSES_PER_REV = 1600L;
const long SORT_PULSES_PER_REV = 1600L;
const int BIN_ANGLE_DEG[3] = {-30, 0, 30}; // left, middle, right
const byte TYPE_TO_BIN[3] = {0, 1, 2}; // PET->left, AluCan->middle, Other->right
const uint32_t HALF_PULSE_US = 2000UL; // Nominal 250 pulses/s; no acceleration.
const uint32_t CAMERA_SETTLE_MS = 500UL; // Provisional; verify image stability.
const uint32_t SORT_SETTLE_MS = 500UL;   // Provisional; not a position sensor.
const uint32_t DROP_WAIT_MS = 1500UL;    // Provisional; not a drop detector.
const uint32_t SCAN_TIMEOUT_MS = 20000UL;
const byte START_BUTTON_PIN = 22;       // Button to GND.
const byte TRIG_PIN = 24;
const byte ECHO_PIN = 25;
const bool USE_PLASTIC_SENSOR = true;  // Preserves supplied Mega's PET-bin guard.
const bool USE_OLED = true;            // Requires Adafruit GFX + SSD1306 libraries.
const float FULL_DISTANCE_CM = 10.0f;
const float CLEAR_DISTANCE_CM = 13.0f;
static_assert(FEED_PULSES_PER_REV >= 6 && FEED_PULSES_PER_REV <= 1000000L,
              "Invalid feeder pulses per output revolution");
static_assert(SORT_PULSES_PER_REV > 0 && SORT_PULSES_PER_REV <= 1000000L,
              "Invalid sorter pulses per output revolution");

enum SystemState : byte {
  NEED_REFERENCE, READY, FEED_TO_CAMERA, CAMERA_SETTLING, WAIT_AI,
  HOLD_UNKNOWN, HOLD_BIN, SORT_TO_BIN, SORT_SETTLING,
  FEED_TO_DROP, DROP_WAIT, TEST_READY, TEST_FEED, TEST_SORT, FAULT
};
enum MotorOwner : byte { NO_MOTOR, FEED_MOTOR, SORT_MOTOR };
SystemState state = NEED_REFERENCE;
uint32_t stateSinceMs = 0;
bool referencesSet = false;
bool configurationOK = false;
bool testMode = false;
byte feedPhase = 0;                  // Rotor phase 0..5, NOT bottle station.
long feedPositionSteps = 0;           // Commanded rotor position in this revolution.
long sortPositionSteps = 0;           // Signed commanded position relative to middle.
int bottleStation = -1;               // -1=no tracked bottle; 0..5=fixed station.
int bottleType = -1;                  // -1=unknown/error, 0=PET, 1=AluCan, 2=Other.
unsigned long completedCycles = 0;    // Timed cycles, NOT physically verified drops.

bool motorActive = false;
bool pulseHigh = false;
MotorOwner motorOwner = NO_MOTOR;
byte activePulPin = 0;
long pulsesRemaining = 0;
int motionSign = 1;
uint32_t nextEdgeUs = 0;

char rxBuffer[40];
byte rxIndex = 0;
bool rxDiscardLine = false;
uint32_t scanStartedMs = 0;

float distanceCM = -1.0f;
bool sensorOK = false;
bool plasticFull = false;
byte fullCount = 0;
byte clearCount = 0;
uint32_t lastSensorMs = 0;
uint32_t lastDisplayMs = 0;
bool buttonRaw = false;
bool buttonStable = false;
uint32_t buttonChangedMs = 0;
bool oledReady = false;
Adafruit_SSD1306 display(128, 64, &Wire, -1);

// Explicit declarations keep Arduino auto-prototype generation unambiguous.
const char* stateName(SystemState value);
void setState(SystemState value);
void softwareStop();
void serviceMotor();
void serviceStateMachine();
void startCycle();
void requestScan();
void processResponse(const char* line);
void checkESP32Communication();
void updateContainerStatus();
void updateOLED();
void printStatus();
void printHelp();
void serviceButton();
void serviceUSB();

const char* stateName(SystemState value) {
  switch (value) {
    case NEED_REFERENCE: return "ALIGN + Z";
    case READY: return "READY";
    case FEED_TO_CAMERA: return "FEED TO 4";
    case CAMERA_SETTLING: return "CAMERA SETTLE";
    case WAIT_AI: return "WAIT AI";
    case HOLD_UNKNOWN: return "HOLD UNKNOWN";
    case HOLD_BIN: return "HOLD PET BIN";
    case SORT_TO_BIN: return "SORT TO BIN";
    case SORT_SETTLING: return "SORT SETTLE";
    case FEED_TO_DROP: return "FEED TO 5";
    case DROP_WAIT: return "DROP WAIT";
    case TEST_READY: return "TEST READY";
    case TEST_FEED: return "TEST FEED";
    case TEST_SORT: return "TEST SORT";
    case FAULT: return "FAULT RESET";
  }
  return "INVALID";
}

void setState(SystemState value) {
  state = value;
  stateSinceMs = (uint32_t)millis();
  // Call only with pulse output idle, avoiding long log writes during motion.
  Serial.print(F("STATE: "));
  Serial.println(stateName(state));
}

// Symmetric nearest-step rounding supports negative angles, e.g. -30 -> -133.
long angleToSteps(int degrees) {
  const long numerator = SORT_PULSES_PER_REV * (long)degrees;
  return numerator >= 0 ? (numerator + 180L) / 360L
                        : -((-numerator + 180L) / 360L);
}

bool validateConfiguration() {
  for (byte i = 0; i < 3; ++i) {
    if (BIN_ANGLE_DEG[i] < -180 || BIN_ANGLE_DEG[i] > 180 || TYPE_TO_BIN[i] > 2)
      return false;
  }
  if (!(BIN_ANGLE_DEG[0] < BIN_ANGLE_DEG[1] &&
        BIN_ANGLE_DEG[1] < BIN_ANGLE_DEG[2])) return false;
  return true;
}

void confirmReferences() {
  if (!configurationOK || state != NEED_REFERENCE || referencesSet) {
    Serial.println(F("Z rejected. References are set only after power-up/reset."));
    return;
  }
  // Operator aligns EMPTY feeder to fixed station boundaries, chute to middle.
  feedPhase = 0;
  feedPositionSteps = 0;
  sortPositionSteps = angleToSteps(BIN_ANGLE_DEG[1]);
  bottleStation = -1;
  referencesSet = true;
  setState(READY);
  Serial.println(F("References recorded. Z performed no physical homing."));
}

void startMotion(MotorOwner owner, long delta) {
  if (!referencesSet || motorActive || state == FAULT) return;
  motorOwner = owner;
  activePulPin = owner == FEED_MOTOR ? FEED_PUL_PIN : SORT_PUL_PIN;
  const byte dirPin = owner == FEED_MOTOR ? FEED_DIR_PIN : SORT_DIR_PIN;
  const byte positiveLevel =
      owner == FEED_MOTOR ? FEED_FORWARD_LEVEL : SORT_POSITIVE_LEVEL;
  motionSign = delta >= 0 ? 1 : -1;
  pulsesRemaining = delta >= 0 ? delta : -delta;
  digitalWrite(activePulPin, LOW);
  digitalWrite(dirPin, motionSign > 0 ? positiveLevel : !positiveLevel);
  pulseHigh = false;
  nextEdgeUs = (uint32_t)micros() + 20UL; // DIR setup before first pulse.
  motorActive = pulsesRemaining > 0;
}

void serviceMotor() {
  if (!motorActive) return;
  const uint32_t now = (uint32_t)micros();
  if ((int32_t)(now - nextEdgeUs) < 0) return;
  if (pulseHigh) {
    digitalWrite(activePulPin, LOW);
    pulseHigh = false;
    --pulsesRemaining;
    if (motorOwner == FEED_MOTOR) feedPositionSteps += motionSign;
    else sortPositionSteps += motionSign;
    nextEdgeUs = now + HALF_PULSE_US;
  } else if (pulsesRemaining == 0) {
    // Complete only after the final LOW interval; no short pulse at boundaries.
    motorActive = false;
    motorOwner = NO_MOTOR;
  } else {
    digitalWrite(activePulPin, HIGH);
    pulseHigh = true;
    nextEdgeUs = now + HALF_PULSE_US;
  }
}

// Rounded cumulative boundaries: 267,533,800,1067,1333,1600.
// Delta sequence: 267,266,267,267,266,267. Phase survives across bottles.
void startFeederStep() {
  const long boundary =
      (FEED_PULSES_PER_REV * (long)(feedPhase + 1) + 3L) / 6L;
  startMotion(FEED_MOTOR, boundary - feedPositionSteps);
}

void finishFeederStep() {
  feedPhase = (feedPhase + 1) % 6;
  if (feedPhase == 0) feedPositionSteps = 0;
}

void startSorterBin(byte bin) {
  startMotion(SORT_MOTOR, angleToSteps(BIN_ANGLE_DEG[bin]) - sortPositionSteps);
}

void clearIncomingAI() {
  while (Serial1.available()) Serial1.read();
  rxIndex = 0;
  rxDiscardLine = false;
}

void requestScan() {
  if (motorActive || bottleStation != 4 ||
      !(state == CAMERA_SETTLING || state == HOLD_UNKNOWN)) return;
  clearIncomingAI();
  bottleType = -1;
  setState(WAIT_AI);
  scanStartedMs = (uint32_t)millis();
  Serial1.println("SCAN");
  Serial.println(F("SCAN sent. Bottle must remain at fixed station 4."));
}

float readDistanceCM() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  const unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);
  if (duration == 0) return -1.0f;
  const float cm = duration * 0.0343f / 2.0f;
  return cm < 2.0f || cm > 400.0f ? -1.0f : cm;
}

void updateContainerStatus() {
  if (!USE_PLASTIC_SENSOR || motorActive) return;
  distanceCM = readDistanceCM();
  lastSensorMs = (uint32_t)millis();
  sensorOK = distanceCM >= 0;
  if (!sensorOK) {
    fullCount = clearCount = 0;
    return;
  }
  if (distanceCM <= FULL_DISTANCE_CM) {
    if (fullCount < 3) ++fullCount;
    clearCount = 0;
    if (fullCount >= 3) plasticFull = true;
  } else if (distanceCM >= CLEAR_DISTANCE_CM) {
    if (clearCount < 3) ++clearCount;
    fullCount = 0;
    if (clearCount >= 3) plasticFull = false;
  } else {
    fullCount = clearCount = 0;
  }
}

bool binAllowsRelease() {
  if (bottleType != 0 || !USE_PLASTIC_SENSOR) return true;
  updateContainerStatus(); // Fresh PET distance immediately before decisions.
  return sensorOK && !plasticFull && distanceCM > FULL_DISTANCE_CM;
}

void startSortingResult() {
  if (bottleType < 0 || bottleType > 2 || bottleStation != 4) return;
  if (!binAllowsRelease()) {
    setState(HOLD_BIN);
    Serial.println(F("PET blocked. Clear bin/fix sensor; R retries without feeding."));
    return;
  }
  setState(SORT_TO_BIN);
  startSorterBin(TYPE_TO_BIN[bottleType]);
}

void processResponse(const char* line) {
  if (state != WAIT_AI) return; // No response can move an idle/held/test machine.
  int type = -2;
  if (strcmp(line, "RESULT,0") == 0) type = 0;
  else if (strcmp(line, "RESULT,1") == 0) type = 1;
  else if (strcmp(line, "RESULT,2") == 0) type = 2;
  else if (strcmp(line, "RESULT,-1") == 0) type = -1;
  if (type == -2) {
    Serial.println(F("Malformed AI response ignored."));
    return;
  }
  bottleType = type;
  Serial.print(F("AI category: "));
  Serial.println(type);
  if (type == -1) {
    setState(HOLD_UNKNOWN);
    Serial.println(F("Bottle held at 4. Adjust view; R rescans this same bottle."));
  } else {
    startSortingResult();
  }
}

void checkESP32Communication() {
  if (state == WAIT_AI &&
      (uint32_t)((uint32_t)millis() - scanStartedMs) >= SCAN_TIMEOUT_MS) {
    referencesSet = false;
    setState(FAULT);
    Serial.println(F("AI timeout: no release. Reset BOTH boards, clear bottle, realign."));
  }
  // Bounded work per loop. Ignore CR; discard a whole corrupt/oversized line.
  byte budget = 32;
  while (budget-- && Serial1.available()) {
    const char c = (char)Serial1.read();
    if (c == '\n') {
      if (!rxDiscardLine && rxIndex > 0) {
        rxBuffer[rxIndex] = '\0';
        processResponse(rxBuffer);
      }
      rxIndex = 0;
      rxDiscardLine = false;
    } else if (c != '\r' && !rxDiscardLine) {
      if (c == '\0' || rxIndex >= sizeof(rxBuffer) - 1) rxDiscardLine = true;
      else rxBuffer[rxIndex++] = c;
    }
  }
}

void startCycle() {
  if (state != READY || !referencesSet || testMode || motorActive) return;
  bottleStation = 0; // Operator asserts exactly ONE bottle at station 0.
  bottleType = -1;
  clearIncomingAI();
  setState(FEED_TO_CAMERA);
  startFeederStep();
}

void serviceStateMachine() {
  if (motorActive) return;
  const uint32_t elapsed = (uint32_t)((uint32_t)millis() - stateSinceMs);
  switch (state) {
    case FEED_TO_CAMERA:
      finishFeederStep();
      ++bottleStation;
      Serial.print(F("Bottle commanded to fixed station "));
      Serial.println(bottleStation);
      if (bottleStation < 4) startFeederStep();
      else setState(CAMERA_SETTLING);
      break;
    case CAMERA_SETTLING:
      if (elapsed >= CAMERA_SETTLE_MS) requestScan();
      break;
    case SORT_TO_BIN:
      setState(SORT_SETTLING);
      break;
    case SORT_SETTLING:
      if (elapsed >= SORT_SETTLE_MS) {
        if (!binAllowsRelease()) setState(HOLD_BIN);
        else {
          // The only automatic path to the fifth feeder step is through here.
          setState(FEED_TO_DROP);
          startFeederStep();
        }
      }
      break;
    case FEED_TO_DROP:
      finishFeederStep();
      bottleStation = 5;
      setState(DROP_WAIT);
      Serial.println(F("Station 5 reached by command; gravity drop is unmeasured."));
      break;
    case DROP_WAIT:
      if (elapsed >= DROP_WAIT_MS) {
        ++completedCycles;
        bottleStation = -1;
        // Discard queued start/test keys: never automatically launch another bottle.
        while (Serial.available()) Serial.read();
        setState(READY);
        Serial.println(F("Timed cycle complete. Verify clear, then load ONE next bottle."));
      }
      break;
    case TEST_FEED:
      finishFeederStep();
      while (Serial.available()) Serial.read();
      setState(TEST_READY);
      break;
    case TEST_SORT:
      while (Serial.available()) Serial.read();
      setState(TEST_READY);
      break;
    default: break;
  }
}

void softwareStop() {
  // Software stop only; no ENA cutoff or hardware emergency-stop circuit.
  digitalWrite(FEED_PUL_PIN, LOW);
  digitalWrite(SORT_PUL_PIN, LOW);
  motorActive = false;
  pulseHigh = false;
  motorOwner = NO_MOTOR;
  referencesSet = false; // A truncated pulse makes position uncertain.
  setState(FAULT);
  Serial.println(F("STOP LOCKED. Clear mechanism, reset boards, realign; Z cannot unlock."));
}

void printStatus() {
  Serial.print(F("State=")); Serial.println(stateName(state));
  Serial.print(F("Rotor phase=")); Serial.println(feedPhase);
  Serial.print(F("Tracked bottle station=")); Serial.println(bottleStation);
  Serial.print(F("Feeder commanded steps within rev=")); Serial.println(feedPositionSteps);
  Serial.print(F("Sorter commanded signed steps=")); Serial.println(sortPositionSteps);
  Serial.print(F("AI type=")); Serial.println(bottleType);
  Serial.print(F("Timed cycles=")); Serial.println(completedCycles);
  Serial.print(F("PET distance cm=")); Serial.println(distanceCM);
}

void printHelp() {
  Serial.println(F("USB 115200: Z confirm EMPTY feeder alignment + chute at MIDDLE."));
  Serial.println(F("S / D22: start ONE bottle at station 0 (normal READY only)."));
  Serial.println(F("R: rescan UNKNOWN / recheck PET bin while bottle stays at station 4."));
  Serial.println(F("X: software stop + reset-required lock; not a hardware emergency stop."));
  Serial.println(F("T: enter/leave EMPTY test mode; F feeder +60; 1 left,2 middle,3 right."));
  Serial.println(F("P status; H help. Busy commands are ignored except X."));
  Serial.println(F("D2/D3 FEED; D4/D5 SORT. UART Serial1 D18/D19 9600."));
}

void serviceUSB() {
  byte budget = 16;
  while (budget-- && Serial.available()) {
    char c = (char)Serial.read();
    if (c >= 'a' && c <= 'z') c -= 'a' - 'A';
    if (c == 'X') { softwareStop(); continue; }
    // No log printing or test/start queue while moving.
    if (motorActive) continue;
    if (c == 'Z') confirmReferences();
    else if (c == 'S') startCycle();
    else if (c == 'R') {
      if (state == HOLD_UNKNOWN) requestScan();
      else if (state == HOLD_BIN) startSortingResult();
    } else if (c == 'T' && referencesSet) {
      if (state == READY) { testMode = true; setState(TEST_READY); }
      else if (state == TEST_READY) { testMode = false; setState(READY); }
    } else if (state == TEST_READY && c == 'F') {
      setState(TEST_FEED);
      startFeederStep();
    } else if (state == TEST_READY && c >= '1' && c <= '3') {
      setState(TEST_SORT);
      startSorterBin((byte)(c - '1'));
    } else if (c == 'P') printStatus();
    else if (c == 'H') printHelp();
  }
}

void serviceButton() {
  const bool pressed = digitalRead(START_BUTTON_PIN) == LOW;
  const uint32_t now = (uint32_t)millis();
  if (pressed != buttonRaw) { buttonRaw = pressed; buttonChangedMs = now; }
  if (pressed != buttonStable &&
      (uint32_t)(now - buttonChangedMs) >= 30UL) {
    buttonStable = pressed;
    if (pressed) startCycle(); // A held button cannot start another cycle.
  }
}

void updateOLED() {
  if (!oledReady || motorActive) return;
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(0, 0); display.println("BOTTLE SORTER V2");
  display.setCursor(0, 12); display.println(stateName(state));
  display.setCursor(0, 24); display.print("Station: "); display.println(bottleStation);
  display.setCursor(0, 36); display.print("AI type: "); display.println(bottleType);
  display.setCursor(0, 48); display.print("PET: ");
  if (!USE_PLASTIC_SENSOR) display.println("GUARD OFF");
  else if (!sensorOK) display.println("SENSOR ERR");
  else if (plasticFull || distanceCM <= FULL_DISTANCE_CM) display.println("FULL");
  else display.println("AVAILABLE");
  display.display();
  lastDisplayMs = (uint32_t)millis();
}

void setup() {
  digitalWrite(FEED_PUL_PIN, LOW); digitalWrite(FEED_DIR_PIN, LOW);
  digitalWrite(SORT_PUL_PIN, LOW); digitalWrite(SORT_DIR_PIN, LOW);
  pinMode(FEED_PUL_PIN, OUTPUT); pinMode(FEED_DIR_PIN, OUTPUT);
  pinMode(SORT_PUL_PIN, OUTPUT); pinMode(SORT_DIR_PIN, OUTPUT);
  pinMode(START_BUTTON_PIN, INPUT_PULLUP);
  pinMode(TRIG_PIN, OUTPUT); pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);
  Serial.begin(115200);
  Serial1.begin(9600);
  Wire.begin();
  if (USE_OLED) oledReady = display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  configurationOK = validateConfiguration();
  setState(configurationOK ? NEED_REFERENCE : FAULT);
  printHelp();
  if (!configurationOK) Serial.println(F("Invalid angles/type mapping; edit configuration."));
  updateContainerStatus();
  updateOLED();
}

void loop() {
  serviceMotor();
  serviceUSB();
  serviceMotor();
  serviceButton();
  serviceMotor();
  checkESP32Communication();
  serviceMotor();
  serviceStateMachine();
  // Slow I2C/pulseIn calls run only with BOTH motors stationary.
  if (!motorActive) {
    if ((uint32_t)((uint32_t)millis() - lastSensorMs) >= 500UL)
      updateContainerStatus();
    if ((uint32_t)((uint32_t)millis() - lastDisplayMs) >= 250UL)
      updateOLED();
  }
}
