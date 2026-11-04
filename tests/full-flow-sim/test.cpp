#include "helpers.inc"
int main(int argc,char**argv) {
  assert(argc==2);
  std::string scenario=argv[1];
  setup();
  assert(!USE_PLASTIC_SENSOR);
  if(scenario=="references") {
    key('S'); key('1'); assert(state==NEED_REFERENCE && !motorActive);
    reference();
    key('1'); key('2'); key('3');
    assert(state==READY && riseCount[2]==0 && riseCount[4]==0);
    key('Z'); assert(state==READY);
  } else if(scenario=="left" || scenario=="middle" || scenario=="right") {
    reference(); startAndReachCamera();
    assert(riseCount[2]==1067 && riseCount[4]==0 && Serial1.output.empty());
    int type=scenario=="left"?0:scenario=="middle"?1:2;
    long target=type==0?-133:type==1?0:133;
    // Full-bin hardware is intentionally absent/ignored in this simulation.
    sensorOK=false; plasticFull=true; echoTime=0;
    key((char)('1'+type));
    untilState(SORT_SETTLING);
    assert(bottleType==type && sortPositionSteps==target);
    assert(riseCount[2]==1067 && bottleStation==4);
    runFor(100); assert(state==SORT_SETTLING && riseCount[2]==1067);
    untilState(FEED_TO_DROP);
    assert(sortPositionSteps==target && bottleStation==4);
    untilState(READY);
    assert(completedCycles==1 && riseCount[2]==1333 && bottleStation==-1);
    assert(riseCount[4]==(target==0?0:133));
    assert(Serial1.output.empty());
    checkPulseDurations();
  } else if(scenario=="manual_wait") {
    reference(); startAndReachCamera();
    runFor(60000);
    assert(state==WAIT_SIM && referencesSet && riseCount[2]==1067);
    reply("RESULT,0\nRESULT,1\nRESULT,2\n");
    assert(state==WAIT_SIM && riseCount[4]==0 && Serial1.output.empty());
    key('0'); key('4'); key('S'); key('T'); key('F');
    assert(state==WAIT_SIM);
    key('2'); untilState(READY);
  } else if(scenario=="unknown") {
    reference(); startAndReachCamera();
    key('U'); assert(state==HOLD_UNKNOWN && bottleStation==4);
    key('1'); key('S'); assert(state==HOLD_UNKNOWN && riseCount[4]==0);
    key('R'); assert(state==WAIT_SIM && riseCount[2]==1067);
    key('1'); untilState(READY); assert(riseCount[2]==1333);
  } else if(scenario=="phase_and_repeat") {
    reference();
    for(int cycle=0;cycle<6;++cycle) {
      startAndReachCamera();
      key('3'); untilState(READY);
      assert(riseCount[4]==133); // Same chosen bin: no repeated sort motion.
    }
    assert(completedCycles==6 && riseCount[2]==8000);
    assert(feedPhase==0 && feedPositionSteps==0 && Serial1.output.empty());
    checkPulseDurations();
  } else if(scenario=="early_busy") {
    reference(); key('S');
    Serial.feed("123123S"); runFor(100);
    untilState(CAMERA_SETTLING);
    Serial.feed("321"); tick(); // Input before the prompt is NOT remembered.
    untilState(WAIT_SIM); runFor(1000);
    assert(state==WAIT_SIM && riseCount[4]==0 && riseCount[2]==1067);
    Serial.feed("13"); tick(); // First accepted choice wins.
    untilState(DROP_WAIT); Serial.feed("S123"); runFor(10);
    untilState(READY); runFor(1000);
    assert(state==READY && bottleType==0 && sortPositionSteps==-133);
    assert(completedCycles==1);
  } else if(scenario=="stop_motion" || scenario=="stop_wait") {
    reference(); key('S');
    if(scenario=="stop_wait") untilState(WAIT_SIM);
    else runFor(100);
    key('X');
    assert(state==FAULT && !motorActive && !referencesSet);
    assert(pinValue[2]==LOW && pinValue[4]==LOW);
    long count=riseCount[2];
    key('Z'); key('S'); key('T'); key('1'); key('R'); runFor(1000);
    assert(state==FAULT && riseCount[2]==count);
  } else if(scenario=="individual") {
    reference(); key('T');
    long expected[6]={267,266,267,267,266,267};
    for(int i=0;i<6;++i) {
      long before=riseCount[2]; key('F'); untilState(TEST_READY);
      assert(riseCount[2]-before==expected[i]);
    }
    key('1'); untilState(TEST_READY); assert(sortPositionSteps==-133);
    key('3'); untilState(TEST_READY); assert(sortPositionSteps==133);
    key('2'); untilState(TEST_READY); assert(sortPositionSteps==0);
    key('T'); assert(state==READY && feedPhase==0);
    checkPulseDurations();
  } else if(scenario=="button_wrap") {
    reference();
    nowUs=(1ULL<<32)-10000;
    startButton=true; untilState(WAIT_SIM); key('2'); untilState(READY);
    runFor(100); assert(state==READY && completedCycles==1);
    startButton=false; runFor(40);
    nowUs=((1ULL<<32)-100ULL)*1000ULL;
    key('S'); untilState(WAIT_SIM); key('3'); untilState(READY);
    assert(completedCycles==2 && riseCount[2]==2667);
  } else assert(false);
  std::cout<<"PASS "<<scenario<<"\n";
}
