#include <cassert>
#include <iostream>
#include <string>
#include "../../demos/full-flow-sim/BottleSorter_FullFlow_Sim/BottleSorter_FullFlow_Sim.ino"
void tick(uint32_t us=250) { nowUs+=us; loop(); }
void untilState(SystemState target, uint32_t limitMs=60000) {
  uint64_t deadline=nowUs+(uint64_t)limitMs*1000ULL;
  while(state!=target && nowUs<deadline) tick();
  if(state!=target) { std::cerr<<"Expected "<<stateName(target)<<" got "<<stateName(state)<<"\n"; assert(false); }
}
void key(char c) { Serial.feed(std::string(1,c)); tick(); }
void reply(const std::string &s) { Serial1.feed(s); for(int i=0;i<8;++i) tick(); }
void runFor(uint32_t ms) { uint64_t end=nowUs+(uint64_t)ms*1000ULL; while(nowUs<end) tick(); }
void reference() { key('Z'); assert(state==READY && referencesSet && sortPositionSteps==0); }
void startAndReachCamera() {
  key('S'); untilState(WAIT_SIM);
  assert(bottleStation==4 && !motorActive);
}
void checkPulseDurations() {
  for(int pin: {2,4}) {
    bool high=false;
    uint64_t raised=0, lowered=0;
    bool previousPulse=false;
    for(const auto &e:edges) if(e.pin==pin) {
      if(e.value==HIGH) {
        assert(!high);
        if(previousPulse) assert(e.us-lowered>=HALF_PULSE_US);
        high=true; raised=e.us;
      } else {
        assert(high);
        assert(e.us-raised>=HALF_PULSE_US);
        high=false; lowered=e.us; previousPulse=true;
      }
    }
    assert(!high);
  }
}
