"""Offline-only recovery checks; never constructs an OpenRouter client."""
from pathlib import Path
import copy,hashlib,importlib.util,json,shutil,sys,tempfile
out=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(out/'runtime'))
from swarm_game.config import Config
from swarm_game.providers import Completion
from swarm_game.runner import run_episode
from swarm_game.storage import read_json
loader=importlib.util.spec_from_file_location('recovery',Path(__file__).with_name('recover_rounding.py'))
m=importlib.util.module_from_spec(loader);loader.loader.exec_module(m)
temp=Path(tempfile.mkdtemp(prefix='intentional-rounding-recovery-offline-'))
checks=[]
class FakeProvider:
 def __init__(self,data):self.data=data;self.calls=0
 def complete(self,*a,**kw):
  self.calls+=1
  return Completion(json.dumps(self.data),{'finish_reason':'stop','model':'offline-synthetic-test'})
class ProbeStop(Exception):pass
class ProbeProvider:
 def __init__(self):self.calls=[]
 def complete(self,request,*a,**kw):
  self.calls.append((request.round,request.phase,request.player))
  raise ProbeStop('offline stop before any new generation')
for name in m.TARGETS:
 source=out/'episodes'/name;ep=temp/name;ep.mkdir()
 for filename in ('manifest.json','checkpoint.json','error.json'):
  shutil.copy2(source/filename,ep/filename)
 shutil.copytree(source/'requests',ep/'requests')
 config=Config(**read_json(ep/'manifest.json')['config'])
 failed=[p for p in (ep/'requests').glob('*.json') if not read_json(p).get('complete')]
 assert len(failed)==1
 path=failed[0];original=path.read_bytes();record=json.loads(original);plan=m.repair_plan(record,config)
 m.snapshot_episode(ep)
 provider=FakeProvider(plan['expected'])
 receipt=m.repair_request(ep,path,config,provider)
 repaired=read_json(path)
 assert provider.calls==1 and len(repaired['attempts'])==3 and repaired['attempts'][:2]==record['attempts']
 assert repaired['complete'] and repaired['data']==plan['expected']
 assert not (ep/'error.json').exists()
 archive=ep/'recovery/rounding-v1/corrections'/path.stem
 assert (archive/'original-request.json').read_bytes()==original
 assert hashlib.sha256(original).hexdigest()==receipt['original_sha256']
 assert (archive/'episode-error-before-resume.json').is_file()
 probe=ProbeProvider()
 try:run_episode(config,probe,ep,resume=True)
 except ProbeStop:pass
 else:raise AssertionError('probe did not stop')
 assert len(probe.calls)==1
 assert probe.calls[0]!=(record['request']['round'],record['request']['phase'],record['request']['player'])
 assert path.read_bytes()==json.dumps(repaired,indent=2,ensure_ascii=False,allow_nan=False).encode()+b'\n'
 checks.append(name+': original bytes/attempts preserved; one correction; no replay; next checkpoint advanced')
 # No duplicate corrective call can be made for this already repaired request.
 try:m.repair_request(ep,path,config,provider)
 except ValueError:pass
 else:raise AssertionError('duplicate correction accepted')
 assert provider.calls==1
 for change in ('large_error','own_role','truncated','wrong_error','exhausted_extra'):
  bad=copy.deepcopy(record)
  data=json.loads(bad['attempts'][-1]['response']['content'])
  if change=='large_error':
   data['beliefs'][plan['adjusted_player']]+=.001
  elif change=='own_role':
   own=bad['request']['player'];data['beliefs'][own]=.5
   candidate=next(p for p,v in data['beliefs'].items() if p!=own and 0<v<.5) if name==m.TARGETS[0] else next(p for p,v in data['beliefs'].items() if p!=own and v==0)
   data['beliefs'][candidate]+=.5
  elif change=='truncated':bad['attempts'][-1]['response']['metadata']['finish_reason']='length'
  elif change=='wrong_error':bad['attempts'][-1]['validation_error']='another failure'
  else:bad['attempts'].append(copy.deepcopy(bad['attempts'][-1]))
  bad['attempts'][-1]['response']['content']=json.dumps(data)
  try:m.repair_plan(bad,config)
  except ValueError:pass
  else:raise AssertionError('ineligible correction accepted: '+change)
 # Simulated new response that changes strategy must be rejected and preserved.
 bad_ep=temp/(name+'-changed-strategy');bad_ep.mkdir();(bad_ep/'requests').mkdir()
 bad_path=bad_ep/'requests'/path.name;bad_path.write_bytes(original)
 changed=copy.deepcopy(plan['expected']);changed['strategy']+=' Changed.'
 try:m.repair_request(bad_ep,bad_path,config,FakeProvider(changed))
 except ValueError:pass
 else:raise AssertionError('strategy change accepted')
 invalid=read_json(bad_path)
 assert not invalid['complete'] and invalid['attempts'][:2]==record['attempts'] and len(invalid['attempts'])==3
checks+=['Substantive errors, own-role errors, truncation, other validation failures, exhausted extra attempts rejected','Changed strategy rejected with every attempt preserved','Repeated correction prevented']
report={'status':'passed','hosted_requests':0,'offline_output':str(temp),'checks':checks}
Path(__file__).with_name('verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
