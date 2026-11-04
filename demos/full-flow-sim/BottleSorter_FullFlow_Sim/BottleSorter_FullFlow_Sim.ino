/*
  FULL FLOW SIMULATION ONLY - Arduino Mega 2560 - NO real AI.
  Separate fork of BottleSorter V2; original files are not modified.
  D2/D3 feeder; D4/D5 sorter; 1600 pulses/rev; bins -30 / 0 / +30.
  USB 115200: align empty feeder and chute to MIDDLE, then Z.
  S: feed FOUR slots, then wait at station 4 for keyboard classification.
  At WAIT SIM 1/2/3: 1=PET(left), 2=AluCan(middle), 3=Other(right).
  Sorter completes and settles BEFORE feeder moves the FIFTH slot to drop.
  Human input wait has NO timeout. No ESP32 request or result is used.
  OLED and PET full-bin guard are disabled. Empty-machine testing first.
  U simulates unknown (hold at 4), R retries the held simulation input.
  X is a software stop + reset-required lock, not a hardware emergency stop.
  Optional T/F/1/2/3 retain V2's individual empty-machine tests.
  One bottle at a time; no physical homing, position or drop feedback.
*/
#include <Arduino.h>
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
const byte START_BUTTON_PIN = 22;       // Button to GND.
const byte TRIG_PIN = 24;
const byte ECHO_PIN = 25;
const bool USE_PLASTIC_SENSOR = false; // SIMULATION: no PET bin sensor required.
const float FULL_DISTANCE_CM = 10.0f;
const float CLEAR_DISTANCE_CM = 13.0f;
static_assert(FEED_PULSES_PER_REV >= 6 && FEED_PULSES_PER_REV <= 1000000L,
              "Invalid feeder pulses per output revolution");
static_assert(SORT_PULSES_PER_REV > 0 && SORT_PULSES_PER_REV <= 1000000L,
              "Invalid sorter pulses per output revolution");

enum SystemState : byte {
  NEED_REFERENCE, READY, FEED_TO_CAMERA, CAMERA_SETTLING, WAIT_SIM,
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
    case CAMERA_SETTLING: return "FEED SETTLE";
    case WAIT_SIM: return "WAIT SIM 1/2/3";
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
  // Reject keys sent before the prompt, but never discard a queued stop.
  while (Serial.available()) {
    const char c = (char)Serial.read();
    if (c == 'X' || c == 'x') { softwareStop(); return; }
  }
  bottleType = -1;
  setState(WAIT_SIM);
  Serial.println(F("SIMULATION ONLY: no ESP32/AI; PET full-bin guard is OFF."));
  Serial.println(F("At station 4. Send 1=PET LEFT, 2=CAN MIDDLE, 3=OTHER RIGHT."));
  Serial.println(F("Waiting for you without timeout. U=unknown hold; X=stop."));
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
  if (state != WAIT_SIM) return; // No response can move an idle/held/test machine.
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
  Serial.print(F("SIMULATED category: "));
  Serial.println(type);
  if (type == -1) {
    setState(HOLD_UNKNOWN);
    Serial.println(F("SIM unknown: bottle held at 4. R returns to manual result input."));
  } else {
    startSortingResult();
  }
}

void checkESP32Communication() {
  // Real ESP32 data NEVER selects a bin in this dedicated simulation sketch.
  // Bounded discard keeps the serial buffer clear without delaying pulse service.
  byte budget = 32;
  while (budget-- && Serial1.available()) Serial1.read();
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
  Serial.println(F("STOP LOCKED. Clear mechanism, press Mega RESET, realign; Z cannot unlock."));
}

void printStatus() {
  Serial.print(F("State=")); Serial.println(stateName(state));
  Serial.print(F("Rotor phase=")); Serial.println(feedPhase);
  Serial.print(F("Tracked bottle station=")); Serial.println(bottleStation);
  Serial.print(F("Feeder commanded steps within rev=")); Serial.println(feedPositionSteps);
  Serial.print(F("Sorter commanded signed steps=")); Serial.println(sortPositionSteps);
  Serial.print(F("Simulated type=")); Serial.println(bottleType);
  Serial.print(F("Timed cycles=")); Serial.println(completedCycles);
  Serial.println(F("SIM ONLY. Camera, OLED and PET bin guard are not used."));
}

void printHelp() {
  Serial.println(F("=== FULL FLOW SIMULATION - NOT REAL AI ==="));
  Serial.println(F("USB 115200. ESP32/OLED/ultrasonic NOT required; PET bin guard OFF."));
  Serial.println(F("Z: confirm EMPTY feeder alignment + chute at MIDDLE."));
  Serial.println(F("S / D22: feed FOUR slots, then wait for manual classification."));
  Serial.println(F("At WAIT SIM: 1=PET LEFT(-30), 2=CAN MIDDLE(0), 3=OTHER RIGHT(+30)."));
  Serial.println(F("After sorter settles, feeder moves FIFTH slot automatically."));
  Serial.println(F("No input timeout. U=simulate unknown; R=retry held input."));
  Serial.println(F("Optional T: individual motor tests; F feeder; 1/2/3 bins."));
  Serial.println(F("X: STOP AND LOCK. To recover, press board RESET and realign; Z alone cannot unlock."));
  Serial.println(F("P=status; H=help. D2/D3 FEED; D4/D5 SORT."));
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
    else if (state == WAIT_SIM && c >= '1' && c <= '3') {
      // This simulates the CLASS RESULT, not a direct manual motor command.
      // It enters V2's normal result -> sorter -> settle -> release path.
      if (c == '1') processResponse("RESULT,0");
      else if (c == '2') processResponse("RESULT,1");
      else processResponse("RESULT,2");
    } else if (state == WAIT_SIM && c == 'U') {
      processResponse("RESULT,-1");
    } else if (c == 'R') {
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
  // This standalone simulation has no display/library dependency.
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
  Serial1.begin(9600); // Incoming real AI data is discarded, never acted on.
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
  // Sensor code is retained but disabled in this simulation fork.
  if (!motorActive) {
    if ((uint32_t)((uint32_t)millis() - lastSensorMs) >= 500UL)
      updateContainerStatus();
    if ((uint32_t)((uint32_t)millis() - lastDisplayMs) >= 250UL)
      updateOLED();
  }
}
