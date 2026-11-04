/*
  Freenove ESP32-S3-WROOM N8R8 + OV3660
  Edge Impulse: DajimK-project-1_inferencing

  Capture VGA (640 x 480) JPEG, show the captured photo and
  exact center-cropped/resized RGB input provided to the model.

  Browser: connect to WiFi hotspot "BottleAI-Camera"
  Password: set in your untracked local_secrets.h file
  URL: http://192.168.4.1

  USB Serial Monitor: 115200 baud, M=classify, V=view bottleType.
  Optional Mega UART: GPIO42 TX -> Mega D19 RX1; Mega D18 TX1 ->
  5V-to-3.3V level shifter -> GPIO41 RX; GND -> GND.
  Mega sends SCAN\n, ESP32 replies RESULT,<type>\n.

  bottleType: 0 PET plastic; 1 aluminium can; 2 Other;
  -1 not confident / capture or inference error (motor must not move).

  NO Servo.h is needed on this board.
*/

#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include "esp_camera.h"
#include "img_converters.h"
#include "esp_heap_caps.h"
#include <DajimK-project-1_inferencing.h>
#include <string.h>

// ----- Access-point settings -----
static const char *AP_NAME = "BottleAI-Camera";
#include "local_secrets.h"
static const char *AP_PASSWORD = BOTTLE_AI_AP_PASSWORD;
WebServer server(80);

// ----- Freenove ESP32-S3 OV3660 pins -----
#define CAM_XCLK  15
#define CAM_SIOD   4
#define CAM_SIOC   5
#define CAM_D0    11
#define CAM_D1     9
#define CAM_D2     8
#define CAM_D3    10
#define CAM_D4    12
#define CAM_D5    18
#define CAM_D6    17
#define CAM_D7    16
#define CAM_VSYNC  6
#define CAM_HREF   7
#define CAM_PCLK  13
#define RGB_LED_PIN 48

// ----- Optional Mega serial -----
#define MEGA_RX_PIN 41
#define MEGA_TX_PIN 42
#define MEGA_BAUD 9600

// ----- Capture is VGA; trained AI input stays 96 x 96 -----
static const int CAM_WIDTH = 640;
static const int CAM_HEIGHT = 480;
static const float MIN_CONFIDENCE = 0.65f;  // Diagnostic, NOT safety-calibrated.
static const bool SWAP_RED_BLUE = false;    // Change only if preview proves colors wrong.

int bottleType = -1;
float bestScore = 0.0f;
String bestLabel = "None";
String lastStatus = "No image captured yet";

// Keep the latest *actual inference frame* for viewing.
uint8_t *cameraRGB = nullptr;
uint8_t *modelRGB = nullptr;
uint8_t *lastJpeg = nullptr;
size_t lastJpegLength = 0;
bool modelImageValid = false;

#if EI_CLASSIFIER_OBJECT_DETECTION == 1
#error "This sketch requires an Edge Impulse IMAGE CLASSIFICATION model."
#endif

static bool initCamera() {
  camera_config_t c = {};
  c.pin_pwdn = -1;
  c.pin_reset = -1;
  c.pin_xclk = CAM_XCLK;
  c.pin_sccb_sda = CAM_SIOD;
  c.pin_sccb_scl = CAM_SIOC;
  c.pin_d0 = CAM_D0;
  c.pin_d1 = CAM_D1;
  c.pin_d2 = CAM_D2;
  c.pin_d3 = CAM_D3;
  c.pin_d4 = CAM_D4;
  c.pin_d5 = CAM_D5;
  c.pin_d6 = CAM_D6;
  c.pin_d7 = CAM_D7;
  c.pin_vsync = CAM_VSYNC;
  c.pin_href = CAM_HREF;
  c.pin_pclk = CAM_PCLK;
  c.xclk_freq_hz = 10000000; // Previously working rate on your board
  c.ledc_timer = LEDC_TIMER_0;
  c.ledc_channel = LEDC_CHANNEL_0;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_VGA;
  c.jpeg_quality = 12;
  c.fb_count = 1;
  c.fb_location = CAMERA_FB_IN_PSRAM;
  c.grab_mode = CAMERA_GRAB_WHEN_EMPTY;

  esp_err_t err = esp_camera_init(&c);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", err);
    return false;
  }
  sensor_t *s = esp_camera_sensor_get();
  if (s && s->id.PID == OV3660_PID) {
    s->set_vflip(s, 1);
  }
  return true;
}

// communication

static void classifyBottle();


void checkMegaCommands() {
    static char command[20];
    static size_t index = 0;

    while (Serial1.available()) {
        char c = (char)Serial1.read();

        if (c == '\r') {
            continue;
        }

        if (c == '\n') {
            command[index] = '\0';

            if (strcmp(command, "SCAN") == 0) {
                Serial.println("SCAN received from Mega");

                // Clear previous classification
                bottleType = -1;

                // Capture image and run real AI
                classifyBottle();

                // Return result to Arduino Mega
                Serial1.print("RESULT,");
                Serial1.println(bottleType);

                Serial.print("Sent RESULT,");
                Serial.println(bottleType);
            }
            else if (index > 0) {
                Serial.print("Unknown Mega command: ");
                Serial.println(command);
            }

            index = 0;
        }
        else if (index < sizeof(command) - 1) {
            command[index++] = c;
        }
        else {
            index = 0;
        }
    }
}

// Bilinear resize from center square of 640x480 to model's input shape.
// IMPORTANT: this is center-crop preprocessing. If the Edge Impulse
// Image block uses "Fit" instead of "Crop", preprocessing must change
// to match the trained impulse.
static void resizeForModel() {
  const int outW = EI_CLASSIFIER_INPUT_WIDTH;
  const int outH = EI_CLASSIFIER_INPUT_HEIGHT;
  const int side = min(CAM_WIDTH, CAM_HEIGHT);
  const int left = (CAM_WIDTH - side) / 2;
  const int top  = (CAM_HEIGHT - side) / 2;

  for (int y = 0; y < outH; y++) {
    float sy = top + ((y + 0.5f) * side / outH) - 0.5f;
    if (sy < 0) sy = 0;
    if (sy > CAM_HEIGHT - 1) sy = CAM_HEIGHT - 1;
    int y0 = (int)sy;
    int y1 = min(y0 + 1, CAM_HEIGHT - 1);
    float fy = sy - y0;

    for (int x = 0; x < outW; x++) {
      float sx = left + ((x + 0.5f) * side / outW) - 0.5f;
      if (sx < 0) sx = 0;
      if (sx > CAM_WIDTH - 1) sx = CAM_WIDTH - 1;
      int x0 = (int)sx;
      int x1 = min(x0 + 1, CAM_WIDTH - 1);
      float fx = sx - x0;

      size_t p00 = ((size_t)y0 * CAM_WIDTH + x0) * 3;
      size_t p10 = ((size_t)y0 * CAM_WIDTH + x1) * 3;
      size_t p01 = ((size_t)y1 * CAM_WIDTH + x0) * 3;
      size_t p11 = ((size_t)y1 * CAM_WIDTH + x1) * 3;
      size_t dst = ((size_t)y * outW + x) * 3;

      for (int c = 0; c < 3; c++) {
        float topPixel = cameraRGB[p00 + c] * (1.0f - fx)
                       + cameraRGB[p10 + c] * fx;
        float bottomPixel = cameraRGB[p01 + c] * (1.0f - fx)
                          + cameraRGB[p11 + c] * fx;
        modelRGB[dst + c] = (uint8_t)(topPixel * (1.0f - fy)
                          + bottomPixel * fy + 0.5f);
      }
    }
  }
}

// Saves the exact source JPEG before converting that SAME frame for AI.
static bool captureAndPrepare() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    lastStatus = "Camera capture failed";
    return false;
  }
  if (fb->format != PIXFORMAT_JPEG ||
      fb->width != CAM_WIDTH || fb->height != CAM_HEIGHT) {
    lastStatus = "Unexpected camera size or format";
    esp_camera_fb_return(fb);
    return false;
  }

  uint8_t *newSnapshot = (uint8_t *)heap_caps_malloc(
    fb->len, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (newSnapshot) {
    memcpy(newSnapshot, fb->buf, fb->len);
    if (lastJpeg) heap_caps_free(lastJpeg);
    lastJpeg = newSnapshot;
    lastJpegLength = fb->len;
  } else {
    Serial.println("Warning: insufficient PSRAM to retain JPEG snapshot");
  }

  bool converted = fmt2rgb888(fb->buf, fb->len, fb->format, cameraRGB);
  esp_camera_fb_return(fb);

  if (!converted) {
    modelImageValid = false;
    lastStatus = "JPEG-to-RGB conversion failed";
    return false;
  }
  resizeForModel();
  modelImageValid = true;
  return true;
}

static int getImageData(size_t offset, size_t length, float *out) {
  size_t pixels = (size_t)EI_CLASSIFIER_INPUT_WIDTH * EI_CLASSIFIER_INPUT_HEIGHT;
  if (!modelRGB || offset > pixels || length > pixels - offset) return -1;
  for (size_t i = 0; i < length; i++) {
    size_t at = (offset + i) * 3;
    uint32_t r = modelRGB[at + 0];
    uint32_t g = modelRGB[at + 1];
    uint32_t b = modelRGB[at + 2];
    if (SWAP_RED_BLUE) {
      uint32_t tmp = r; r = b; b = tmp;
    }
    out[i] = (float)((r << 16) | (g << 8) | b);
  }
  return 0;
}

static int labelToBottleType(const char *label) {
  if (!strcmp(label, "PetBottle")) return 0;
  if (!strcmp(label, "AluCan")) return 1;
  if (!strcmp(label, "Other")) return 2; // Actual third class in impulse #5.
  return -1;
}

static void classifyBottle() {
  bottleType = -1;
  bestScore = 0.0f;
  bestLabel = "None";
  lastStatus = "Capturing...";
  if (!captureAndPrepare()) {
    Serial.println(lastStatus);
    return;
  }

  signal_t signal = {};
  signal.total_length = (size_t)EI_CLASSIFIER_INPUT_WIDTH
                      * EI_CLASSIFIER_INPUT_HEIGHT;
  signal.get_data = &getImageData;
  ei_impulse_result_t result = {};

  Serial.printf("Free internal heap: %u | Free PSRAM: %u\n",
                (unsigned)heap_caps_get_free_size(MALLOC_CAP_INTERNAL),
                (unsigned)ESP.getFreePsram());
  Serial.println("Running AI model...");
  EI_IMPULSE_ERROR err = run_classifier(&signal, &result, false);
  if (err != EI_IMPULSE_OK) {
    lastStatus = String("Inference error: ") + String((int)err);
    Serial.println(lastStatus);
    return;
  }

  Serial.println("AI predictions:");
  for (size_t i = 0; i < EI_CLASSIFIER_LABEL_COUNT; i++) {
    const char *name = result.classification[i].label;
    float score = result.classification[i].value;
    Serial.printf("  %s: %.2f%%\n", name, score * 100.0f);
    if (score > bestScore) {
      bestScore = score;
      bestLabel = String(name);
    }
  }
  if (bestScore >= MIN_CONFIDENCE) {
    bottleType = labelToBottleType(bestLabel.c_str());
  }
  lastStatus = "Inference complete";
  Serial.printf("bottleType=%d | Top prediction=%s (%.2f%%) | AI time=%d ms\n",
                bottleType, bestLabel.c_str(), bestScore * 100.0f,
                result.timing.classification);
}

// Raw JPEG response without duplicating the large image in an HTML String.
static void sendJpeg(const uint8_t *data, size_t length) {
  if (!data || !length) {
    server.send(404, "text/plain", "No image yet. Capture first.");
    return;
  }
  server.sendHeader("Cache-Control", "no-store, max-age=0");
  server.setContentLength(length);
  server.send(200, "image/jpeg", "");
  auto client = server.client();
  size_t pos = 0;
  while (pos < length && client.connected()) {
    size_t amount = min((size_t)2048, length - pos);
    size_t written = client.write(data + pos, amount);
    if (written == 0) break;
    pos += written;
    delay(0);
  }
}

static void sendModelPreview() {
  if (!modelImageValid) {
    server.send(404, "text/plain", "No model input yet. Capture first.");
    return;
  }
  uint8_t *jpg = nullptr;
  size_t jpgLength = 0;
  bool ok = fmt2jpg(
    modelRGB,
    (size_t)EI_CLASSIFIER_INPUT_WIDTH * EI_CLASSIFIER_INPUT_HEIGHT * 3,
    EI_CLASSIFIER_INPUT_WIDTH, EI_CLASSIFIER_INPUT_HEIGHT,
    PIXFORMAT_RGB888, 90, &jpg, &jpgLength
  );
  if (!ok || !jpg) {
    server.send(500, "text/plain", "Failed to encode AI-input preview.");
    return;
  }
  sendJpeg(jpg, jpgLength);
  free(jpg);
}

static void showHome() {
  String page;
  page.reserve(2300);
  page += "<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>";
  page += "<title>Bottle AI Camera</title><style>body{font-family:sans-serif;max-width:850px;margin:20px auto;padding:12px}";
  page += "img{max-width:100%;height:auto;border:1px solid #bbb}a{display:inline-block;padding:12px;margin:4px 8px 10px 0;background:#134e4a;color:white;text-decoration:none;border-radius:8px}";
  page += "small{color:#555}code{background:#eee;padding:2px 4px}</style></head><body>";
  page += "<h2>ESP32-S3 Bottle Camera + Edge Impulse</h2>";
  page += "<p><a href='/capture'>Capture preview (no AI)</a><a href='/scan'>Capture + run AI</a></p>";
  page += "<p><b>Status:</b> "; page += lastStatus; page += "</p>";
  page += "<p><b>AI prediction:</b> "; page += bestLabel;
  page += " ("; page += String(bestScore * 100.0f, 2);
  page += "%) | <b>bottleType:</b> "; page += String(bottleType); page += "</p>";
  if (lastJpeg) {
    page += "<h3>Original VGA camera frame (640 x 480)</h3>";
    page += "<p><img src='/last.jpg?t="; page += String(millis()); page += "'></p>";
    page += "<p><a href='/last.jpg'>Open original JPEG</a></p>";
  }
  if (modelImageValid) {
    page += "<h3>Exact cropped/resized AI input (";
    page += String(EI_CLASSIFIER_INPUT_WIDTH); page += " x ";
    page += String(EI_CLASSIFIER_INPUT_HEIGHT); page += ")</h3>";
    page += "<p><img src='/model.jpg?t="; page += String(millis());
    page += "' width='288' style='image-rendering:pixelated'></p>";
    page += "<p><a href='/model.jpg'>Open model-input JPEG</a></p>";
  }
  page += "<p><small>Compare both images for cropping, blur, lighting and wrong colors. "
          "The model is trained at 96x96 even though the camera captures 640x480.</small></p>";
  page += "</body></html>";
  server.send(200, "text/html", page);
}

static void redirectHome() {
  server.sendHeader("Location", "/", true);
  server.send(303, "text/plain", "See / for results");
}

static void startWebServer() {
  server.on("/", HTTP_GET, showHome);
  server.on("/last.jpg", HTTP_GET, []() {
    sendJpeg(lastJpeg, lastJpegLength);
  });
  server.on("/model.jpg", HTTP_GET, sendModelPreview);
  server.on("/capture", HTTP_GET, []() {
    if (captureAndPrepare()) {
      lastStatus = "Captured. AI not run for this photo.";
      bestLabel = "None";
      bestScore = 0;
      bottleType = -1;
    }
    redirectHome();
  });
  server.on("/scan", HTTP_GET, []() {
    classifyBottle();
    redirectHome();
  });
  server.onNotFound([]() { server.send(404, "text/plain", "Not found"); });
  server.begin();
}


void setup() {
  Serial.begin(115200);
  delay(1500);
  neopixelWrite(RGB_LED_PIN, 0, 0, 0);
  Serial.println("ESP32-S3 Bottle AI + Camera Preview");
  

Serial.println("Mega UART communication ready");

  if (!psramFound()) {
    Serial.println("ERROR: PSRAM disabled. Tools > PSRAM > OPI PSRAM");
    while (true) delay(1000);
  }
  if (!initCamera()) {
    while (true) delay(1000);
  }

  cameraRGB = (uint8_t *)heap_caps_malloc(
      (size_t)CAM_WIDTH * CAM_HEIGHT * 3,
      MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  modelRGB = (uint8_t *)heap_caps_malloc(
      (size_t)EI_CLASSIFIER_INPUT_WIDTH * EI_CLASSIFIER_INPUT_HEIGHT * 3,
      MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);

  if (!cameraRGB || !modelRGB) {
    Serial.println("ERROR: Failed to allocate camera/model image buffers in PSRAM");
    while (true) delay(1000);
  }

  Serial1.begin(MEGA_BAUD, SERIAL_8N1, MEGA_RX_PIN, MEGA_TX_PIN);
  Serial1.setTimeout(100);

  WiFi.mode(WIFI_AP);
  if (WiFi.softAP(AP_NAME, AP_PASSWORD)) {
    Serial.print("Connect to WiFi: "); Serial.println(AP_NAME);
    Serial.print("Open: http://"); Serial.println(WiFi.softAPIP());
  } else {
    Serial.println("WiFi access point could not start. USB controls still work.");
  }
  startWebServer();
  Serial.println("USB commands: M = classify, V = show bottleType");
}


void loop() {

    // Handle camera webpage requests
    server.handleClient();

    // Receive SCAN command from Arduino Mega
    checkMegaCommands();

    // Keep existing USB Serial commands
    if (Serial.available()) {

        char command = (char)Serial.read();

        if (command == 'M' || command == 'm') {
            classifyBottle();
        }

        if (command == 'V' || command == 'v') {
            Serial.printf(
                "Stored bottleType=%d | %s (%.2f%%)\n",
                bottleType,
                bestLabel.c_str(),
                bestScore * 100.0f
            );
        }
    }

    delay(2);
}
