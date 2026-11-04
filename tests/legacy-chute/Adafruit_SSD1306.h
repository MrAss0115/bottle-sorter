
#pragma once
#define SSD1306_WHITE 1
#define SSD1306_SWITCHCAPVCC 2
struct Adafruit_SSD1306 {
  Adafruit_SSD1306(int,int,FakeWire*,int) {}
  bool begin(int,int) { return true; }
  void clearDisplay() {}
  void setTextColor(int) {}
  void setTextSize(int) {}
  void setCursor(int,int) {}
  void drawLine(int,int,int,int,int) {}
  void display() {}
  template<class T> void print(T) {}
  template<class T> void print(T,int) {}
  template<class T> void println(T) {}
};
