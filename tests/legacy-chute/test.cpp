#include <cassert>
#include <iostream>
#include <string>
#include "../../legacy/chute-v2/BottleSorter_Mega_V2/BottleSorter_Mega_V2.ino"
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
  key('S'); untilState(WAIT_AI);
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
int main(int argc,char**argv) {
  assert(argc==2); std::string scenario=argv[1];
  setup();
  if(scenario=="references") {
    key('S'); key('1'); assert(!motorActive && state==NEED_REFERENCE);
    reference(); key('Z'); assert(state==READY);
    key('1'); assert(!motorActive);
    assert(angleToSteps(-30)==-133 && angleToSteps(0)==0 && angleToSteps(30)==133);
    key('T'); key('1'); untilState(TEST_READY);
    assert(sortPositionSteps==-133 && riseCount[4]==133 && pinValue[5]==LOW);
    key('3'); untilState(TEST_READY);
    assert(sortPositionSteps==133 && riseCount[4]==399 && pinValue[5]==HIGH);
    key('3'); untilState(TEST_READY); assert(riseCount[4]==399);
    key('2'); untilState(TEST_READY); assert(sortPositionSteps==0 && riseCount[4]==532);
    checkPulseDurations();
  } else if(scenario=="feeder_phase") {
    reference(); key('T');
    long expected[6]={267,266,267,267,266,267};
    for(int k=0;k<60;++k) {
      long before=riseCount[2]; key('F'); untilState(TEST_READY);
      assert(riseCount[2]-before==expected[k%6]);
      assert(pinValue[3]==FEED_FORWARD_LEVEL);
    }
    assert(riseCount[2]==16000 && feedPhase==0 && feedPositionSteps==0);
    checkPulseDurations();
  } else if(scenario=="cycle") {
    reference(); startAndReachCamera();
    assert(riseCount[2]==1067 && riseCount[4]==0 && Serial1.output=="SCAN\n");
    reply("RESULT,2\r\n"); assert(state==SORT_TO_BIN);
    long feedBefore=riseCount[2];
    untilState(SORT_SETTLING);
    assert(sortPositionSteps==133 && riseCount[2]==feedBefore);
    runFor(100); assert(state==SORT_SETTLING && riseCount[2]==feedBefore);
    untilState(FEED_TO_DROP);
    assert(sortPositionSteps==133 && !pulseHigh && bottleStation==4);
    untilState(READY);
    assert(riseCount[2]==1333 && feedPhase==5 && completedCycles==1 && bottleStation==-1);
    // New bottle begins at fixed station 0; rotor rounding phase must NOT restart.
    startAndReachCamera();
    assert(riseCount[2]==2400 && feedPhase==3);
    long sorterBefore=riseCount[4];
    reply("RESULT,2\n"); untilState(READY);
    assert(riseCount[4]==sorterBefore && riseCount[2]==2667 && feedPhase==4);
    // Close the five-revolution boundary over six single-bottle cycles.
    for(int i=0;i<4;++i) {
      startAndReachCamera(); reply("RESULT,1\n"); untilState(READY);
    }
    assert(completedCycles==6 && riseCount[2]==8000 && feedPhase==0);
    checkPulseDurations();
  } else if(scenario=="unknown") {
    reference(); reply("RESULT,2\n"); assert(riseCount[4]==0);
    startAndReachCamera(); reply("RESULT,-1\n");
    assert(state==HOLD_UNKNOWN && bottleStation==4 && riseCount[2]==1067);
    key('S'); key('F'); key('3'); runFor(500); assert(state==HOLD_UNKNOWN);
    reply("RESULT,2\n"); assert(state==HOLD_UNKNOWN);
    key('R'); assert(state==WAIT_AI && bottleStation==4);
    reply("RESULT,1\n"); untilState(READY); assert(riseCount[2]==1333);
  } else if(scenario=="pet_guard") {
    reference(); startAndReachCamera();
    echoTime=300; reply("RESULT,0\n");
    assert(state==HOLD_BIN && riseCount[2]==1067 && riseCount[4]==0);
    runFor(1600); assert(plasticFull);
    echoTime=0; key('R'); assert(state==HOLD_BIN && !sensorOK);
    echoTime=1200; runFor(1600); assert(!plasticFull && sensorOK);
    key('R'); untilState(SORT_SETTLING); assert(sortPositionSteps==-133);
    // Bin becomes full AFTER sorter motion: release must still be blocked.
    echoTime=300; untilState(HOLD_BIN);
    assert(riseCount[2]==1067 && bottleStation==4);
    echoTime=1200; runFor(1600); key('R'); untilState(READY);
    assert(riseCount[2]==1333);
  } else if(scenario=="uart") {
    reference(); startAndReachCamera();
    reply(std::string(50,'x')+"RESULT,2\n"); assert(state==WAIT_AI);
    reply(std::string("RESULT,2")+std::string(1,'\0')+"junk\n"); assert(state==WAIT_AI);
    reply("RESULT,20\n"); assert(state==WAIT_AI);
    reply("RESULT,"); assert(state==WAIT_AI);
    reply("1\r\n"); untilState(READY);
    assert(riseCount[2]==1333 && riseCount[4]==0);
  } else if(scenario=="timeout") {
    reference(); startAndReachCamera();
    nowUs+=SCAN_TIMEOUT_MS*1000ULL;
    reply("RESULT,2\n");
    assert(state==FAULT && !referencesSet && riseCount[2]==1067 && riseCount[4]==0);
    key('R'); key('S'); key('Z'); assert(state==FAULT && !motorActive);
  } else if(scenario=="stop") {
    reference(); key('S'); runFor(100);
    long before=riseCount[2]; assert(motorActive);
    key('X'); assert(state==FAULT && !motorActive && !referencesSet);
    assert(pinValue[2]==LOW && pinValue[4]==LOW);
    runFor(500); assert(riseCount[2]<=before+1);
    key('Z'); key('R'); key('S'); key('T'); assert(state==FAULT);
  } else if(scenario=="button") {
    reference();
    startButton=true; runFor(10); startButton=false; runFor(40);
    assert(state==READY && riseCount[2]==0); // Short contact bounce ignored.
    startButton=true; untilState(WAIT_AI); reply("RESULT,1\n");
    // A continuously held button cannot trigger a second cycle.
    untilState(READY); runFor(100); assert(state==READY && completedCycles==1);
    startButton=false; runFor(40); startButton=true; untilState(WAIT_AI);
    assert(completedCycles==1 && bottleStation==4);
  } else if(scenario=="busy") {
    reference(); key('S');
    Serial.feed("S123FTRZ"); runFor(100);
    assert(state==FEED_TO_CAMERA && !testMode && bottleStation<4);
    untilState(WAIT_AI); reply("RESULT,1\n"); untilState(DROP_WAIT);
    Serial.feed("SSS"); runFor(10); untilState(READY); runFor(100);
    assert(state==READY && completedCycles==1);
  } else if(scenario=="wrap") {
    reference();
    nowUs=(1ULL<<32)-10000; // micros rollover during motion.
    startAndReachCamera(); reply("RESULT,1\n"); untilState(READY);
    nowUs=((1ULL<<32)-100ULL)*1000ULL; // millis rollover during another cycle.
    startAndReachCamera(); reply("RESULT,2\n"); untilState(READY);
    assert(completedCycles==2 && riseCount[2]==2667);
  } else assert(false);
  std::cout<<"PASS "<<scenario<<"\n";
}
