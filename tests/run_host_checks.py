from pathlib import Path
import argparse,subprocess,shutil,json,sys
p=argparse.ArgumentParser();p.add_argument('--cxx',default=shutil.which('g++'));a=p.parse_args()
if not a.cxx: p.error('Install g++ or pass --cxx with the compiler path')
root=Path(__file__).resolve().parent.parent
build=root/'build'/'host';build.mkdir(parents=True,exist_ok=True)
suites={
 'legacy-chute':['references','feeder_phase','cycle','unknown','pet_guard','uart','timeout','stop','button','busy','wrap'],
 'full-flow-sim':['references','left','middle','right','manual_wait','unknown','phase_and_repeat','early_busy','stop_motion','stop_wait','individual','button_wrap']}
results={}
for suite,cases in suites.items():
 q=root/'tests'/suite;exe=build/(suite+('.exe' if sys.platform=='win32' else ''))
 subprocess.run([a.cxx,'-std=c++11','-Wall','-Wextra','-Werror','-I',str(q),str(q/'test.cpp'),'-o',str(exe)],check=True)
 for name in cases:
  result=subprocess.run([str(exe),name],capture_output=True,text=True)
  results[suite+'/'+name]={'exit_code':result.returncode,'output':result.stdout+result.stderr}
  print(suite+'/'+name+': '+('PASS' if result.returncode==0 else 'FAIL'),flush=True)
  (build/'results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
  result.check_returncode()
print('Host scenarios passed: '+str(len(results))+'. No physical testing performed.')
