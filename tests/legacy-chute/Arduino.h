#pragma once
#include <string>
#include <deque>
#include <vector>
#include <sstream>
#include <cstdint>
using byte=unsigned char;
#define HIGH 1
#define LOW 0
#define OUTPUT 1
#define INPUT 0
#define INPUT_PULLUP 2
#define F(x) x
uint64_t nowUs=1000000ULL;
unsigned long echoTime=1200;
bool startButton=false;
long riseCount[64]={};
int pinValue[64]={};
struct Edge { uint64_t us; int pin; int value; };
std::vector<Edge> edges;
struct FakeSerial {
  std::deque<char> input;
  std::string output;
  void begin(long) {}
  int available() { return (int)input.size(); }
  int read() { char c=input.front(); input.pop_front(); return (unsigned char)c; }
  void feed(const std::string &s) { for(char c:s) input.push_back(c); }
  template<class T> void print(T v) { std::ostringstream s; s<<v; output+=s.str(); }
  void print(unsigned char v) { print((int)v); }
  template<class T> void print(T v,int) { print(v); }
  void println() { output+="\n"; }
  template<class T> void println(T v) { print(v); println(); }
} Serial, Serial1;
void pinMode(int,int) {}
void digitalWrite(int pin,int value) {
  if(pinValue[pin]!=value) {
    if(value==HIGH) ++riseCount[pin];
    edges.push_back({nowUs,pin,value});
  }
  pinValue[pin]=value;
}
int digitalRead(int pin) { return pin==22 && startButton ? LOW : HIGH; }
void delayMicroseconds(unsigned int us) { nowUs+=us; }
unsigned long millis() { return (uint32_t)(nowUs/1000ULL); }
unsigned long micros() { return (uint32_t)nowUs; }
unsigned long pulseIn(int,int,unsigned long timeout) {
  nowUs+=echoTime ? echoTime : timeout;
  return echoTime;
}
