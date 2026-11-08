"""Read-only deterministic replay of accepted calls using the saved runtime."""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
from collections import Counter
import datetime, hashlib, json, time

out=Path('/Users/ivan/Documents/ChatGPT/AIAF project/intentional-agent-luna-e75a825/results/computer-2-luna-selfish-3')
sys.path.insert(0,str(out/'runtime'))
import swarm_game
from swarm_game.config import Config
from swarm_game.game import initial_state,commit_phase
from swarm_game.protocol import make_request,validate_response,tokenizer
from swarm_game.storage import provenance
assert Path(swarm_game.__file__).parent.resolve()==out/'runtime/swarm_game'
manifest=json.loads((out/'matrix_manifest.json').read_text())
assert provenance()==manifest['provenance']
assert json.loads((out/'spec.json').read_text())==manifest['spec']
assert len(manifest['plan'])==60
assert (out/'source-commit.txt').read_text().strip()=='e75a825d12fb8b0e77f45f1e486fb02483455ea5'
tokenizer()
report_path=Path('/tmp/intentional-luna-deterministic-replay.json')
report={'status':'running','checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_commit':(out/'source-commit.txt').read_text().strip(),'method':'frozen initial_state, exact make_request comparison, validate_response, commit_phase, complete checkpoint equality','hosted_requests':0,'runtime_provenance_verified':True,'episodes':{},'replayed_episodes':0,'replayed_accepted_requests':0,'waiting_episodes':[]}
matched={}

def save():
 report['checked_at_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
 temp=report_path.with_suffix('.tmp')
 temp.write_text(json.dumps(report,indent=2)+'\n');temp.replace(report_path)

def replay(entry,expected):
 ep=out/'episodes'/entry['episode_id'];config=Config(**entry['config'])
 assert json.loads((ep/'manifest.json').read_text())=={'config':config.to_dict(),'provenance':manifest['provenance']}
 state=initial_state(config)
 initial_match=(state['roles'],state['schedule'])
 if config.seed in matched:assert matched[config.seed]==initial_match
 else:matched[config.seed]=initial_match
 filenames=set();counts=Counter()
 while not state['completed']:
  phase=state['phase'];round_number=state['round']
  for player in state['players']:
   request=make_request(state,config,player)
   filename=f'{round_number:04d}-{phase}-{player}.json'
   assert filename not in filenames
   filenames.add(filename)
   saved=json.loads((ep/'requests'/filename).read_text())
   assert saved['complete'] is True and saved['status']=='complete',(entry['episode_id'],filename,'not accepted')
   assert saved['request']==request.to_dict(),(entry['episode_id'],filename,'saved request differs from replay view/prompt/schema')
   assert saved['data']==json.loads(saved['attempts'][-1]['response']['content']),(entry['episode_id'],filename,'accepted data differs from response')
   validate_response(saved['data'],request,config)
   state['pending'][player]=saved['data']
   counts[phase]+=1
  commit_phase(state,config)
 assert len(filenames)==210
 assert counts=={'pre_round':100,'action':100,'final':10}
 assert filenames=={p.name for p in (ep/'requests').glob('*.json')}
 assert state==expected,(entry['episode_id'],'full final checkpoint differs', [k for k in state if state[k]!=expected.get(k)])
 # Finished checkpoints must remain stable for the duration of replay.
 assert json.loads((ep/'checkpoint.json').read_text())==expected
 return {'status':'passed','accepted_requests':210,'request_phase_counts':dict(counts),'full_checkpoint_equal':True,'all_saved_requests_exactly_match_reconstructed_views_prompts_and_schemas':True,'all_accepted_responses_validate':True,'checkpoint_sha256':hashlib.sha256((ep/'checkpoint.json').read_bytes()).hexdigest()}

try:
 while len(report['episodes'])<len(manifest['plan']):
  waiting=[]
  for entry in manifest['plan']:
   name=entry['episode_id']
   if name in report['episodes']:continue
   checkpoint=out/'episodes'/name/'checkpoint.json'
   state=json.loads(checkpoint.read_text()) if checkpoint.exists() else {}
   if not state.get('completed'):
    waiting.append(name);continue
   result=replay(entry,state)
   report['episodes'][name]=result
   report['replayed_episodes']=len(report['episodes'])
   report['replayed_accepted_requests']=210*len(report['episodes'])
   if len(report['episodes'])%10==0:
    save();print('Verified full deterministic replay:',len(report['episodes']),'episodes;',report['replayed_accepted_requests'],'accepted requests',flush=True)
  report['waiting_episodes']=waiting;save()
  if waiting:
   print('Waiting for completed checkpoints:',json.dumps(waiting),flush=True)
   time.sleep(30)
 assert report['replayed_episodes']==60 and report['replayed_accepted_requests']==12600
 report['status']='passed';report['matched_seed_roles_schedules']=True;save()
 print(json.dumps({k:v for k,v in report.items() if k!='episodes'},indent=2),flush=True)
except BaseException as exc:
 report['status']='failed';report['error_type']=type(exc).__name__;report['error']=str(exc);save()
 print(json.dumps({'status':'failed','verified_episodes':len(report['episodes']),'error_type':type(exc).__name__,'error':str(exc)}),flush=True)
 raise
