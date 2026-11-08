from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal
from zoneinfo import ZoneInfo
import datetime,hashlib,json,math,statistics,sys
out=Path('/Users/ivan/Documents/ChatGPT/AIAF project/intentional-agent-luna-e75a825/results/computer-2-luna-selfish-3')
manifest=json.loads((out/'matrix_manifest.json').read_text());spec=manifest['spec']
assert spec['models']==['openai/gpt-6-luna'] and spec['selfish_counts']==[3] and spec['seeds']==list(range(12))
assert spec['communication_modes']==['none','public','opponent','good_leader','selfish_leader']
assert len(manifest['plan'])==60
sys.path.insert(0,str(out/'runtime'))
from swarm_game.config import Config
from swarm_game.game import initial_state
from swarm_game.matrix import episode_plan
from swarm_game.storage import provenance
assert json.loads((out/'spec.json').read_text())==spec
assert episode_plan(spec)==manifest['plan']
assert provenance()==manifest['provenance']
for k,v in {'protocol_version':'rotating-v4','players':10,'rounds':10,'backend':'openrouter','reasoning_effort':'medium','message_tokens':96}.items():assert spec['game'][k]==v
rows=[];role_schedule={};request_statuses=Counter();transport_errors=Counter();validation_errors=Counter();models=Counter();raw_attempts=0;reported_cost=Decimal(0);missing_cost=0;recovery_receipts=[];total_encounters=0
payoff_table={('C','C'):(3,3),('C','D'):(0,5),('D','C'):(5,0),('D','D'):(1,1)}
for entry in manifest['plan']:
 name=entry['episode_id'];ep=out/'episodes'/name;cfg=entry['config'];cp=json.loads((ep/'checkpoint.json').read_text());saved=json.loads((ep/'manifest.json').read_text())
 assert cp['completed'] and cp['phase']=='complete',name
 assert saved['config']==cfg and saved['provenance']==manifest['provenance']
 assert not (ep/'error.json').exists(),name
 initial=initial_state(Config(**cfg))
 for k in ('players','roles','schedule','leader_assignment'):assert cp[k]==initial[k],(name,k)
 key=cfg['seed'];matched=(cp['roles'],cp['schedule'])
 if key in role_schedule:assert role_schedule[key]==matched
 else:role_schedule[key]=matched
 assert len(cp['encounters'])==50
 assert Counter(e['round'] for e in cp['encounters'])==Counter({i:5 for i in range(1,11)})
 good={p for p,r in cp['roles'].items() if r=='good'};selfish=set(cp['roles'])-good
 assert len(good)==7 and len(selfish)==3
 action_counts=Counter();returns=Counter();per_player=Counter();pair_counts=Counter()
 for e in cp['encounters']:
  assert tuple(e['payoffs'])==payoff_table[tuple(e['actions'])]
  for p,a,v in zip(e['players'],e['actions'],e['payoffs']):
   role=cp['roles'][p];action_counts[role]+=1;action_counts[role+'_C']+=a=='C';returns[role]+=v;per_player[p]+=v
   other=next(q for q in e['players'] if q!=p)
   if role=='good':pair_counts['to_'+cp['roles'][other]]+=1;pair_counts['C_to_'+cp['roles'][other]]+=a=='C'
 assert dict(per_player)==cp['payoffs']
 total_encounters+=len(cp['encounters'])
 final=[b for b in cp['belief_records'] if b['phase']=='final' and b['player'] in good]
 assert len(final)==7
 recall=sum(b['beliefs'][p]>=.8 for b in final for p in selfish)/21
 brier=statistics.mean(statistics.mean((prob-(p in selfish))**2 for p,prob in b['beliefs'].items() if p!=b['player']) for b in final)
 good_reports=[b for b in cp['belief_records'] if b['player'] in good]
 assert len(good_reports)==77
 false_rate=sum(any(prob>=.8 and p in good and p!=b['player'] for p,prob in b['beliefs'].items()) for b in good_reports)/77
 row={'seed':cfg['seed'],'mode':cfg['communication'],'good_total_return':returns['good'],'good_payoff_per_encounter':returns['good']/70,'selfish_payoff_per_encounter':returns['selfish']/30,'good_cooperation_rate':action_counts['good_C']/70,'selfish_cooperation_rate':action_counts['selfish_C']/30,'final_identification_rate':recall,'final_brier':brier,'false_accusation_rate':false_rate,**pair_counts}
 summary=json.loads((ep/'summary.json').read_text())
 for a,b in [('good_total_return','good_total_return'),('good_payoff_per_encounter','return_per_good_encounter'),('good_cooperation_rate','good_cooperation_rate'),('final_identification_rate','final_identification_rate'),('final_brier','final_mean_brier_score'),('false_accusation_rate','false_accusation_rate')]:assert math.isclose(row[a],summary[b],rel_tol=1e-12,abs_tol=1e-12),(name,a)
 rows.append(row)
 request_paths=list((ep/'requests').glob('*.json'));assert len(request_paths)==210
 phases=Counter()
 for path in request_paths:
  d=json.loads(path.read_text());request_statuses[d['status']]+=1
  assert d['status']=='complete' and d['complete'],str(path)
  assert d['data']==json.loads(d['attempts'][-1]['response']['content']),str(path)
  assert d['request']['view']['player']==d['request']['player']
  assert not {'roles','schedule','pending'} & d['request']['view'].keys()
  phases[d['request']['phase']]+=1
  for a in d['attempts']:
   raw_attempts+=1;meta=a['response']['metadata'];models[meta.get('model')]+=1
   assert meta['model']=='openai/gpt-6-luna' or meta['model'].startswith('openai/gpt-6-luna-202')
   assert meta['provider'].lower()=='openai'
   if 'validation_error' in a:validation_errors[a['validation_error']]+=1
   cost=meta.get('reported_cost_usd')
   if cost is None:missing_cost+=1
   else:reported_cost+=Decimal(str(cost))
  for event in d.get('transport_events',[]):transport_errors[event.get('error','unknown')]+=1
 assert phases=={'pre_round':100,'action':100,'final':10}
 for receipt_path in ep.glob('recovery/rounding-v1/corrections/*/receipt.json'):
  receipt=json.loads(receipt_path.read_text());assert receipt['status']=='complete'
  archived=(receipt_path.parent/'original-request.json').read_bytes();assert hashlib.sha256(archived).hexdigest()==receipt['original_sha256']
  original=json.loads(archived);current=json.loads((ep/'requests'/receipt['request']).read_text())
  assert current['attempts'][:len(original['attempts'])]==original['attempts']
  assert len(current['attempts'])==len(original['attempts'])+1
  assert current['attempts'][-1]['additional_arithmetic_repair'] is True
  old=json.loads(original['attempts'][-1]['response']['content']);new=current['data']
  assert {k:v for k,v in old.items() if k!='beliefs'}=={k:v for k,v in new.items() if k!='beliefs'}
  changed=[p for p in new['beliefs'] if new['beliefs'][p]!=old['beliefs'][p]]
  assert changed==[receipt['adjusted_player']]
  assert changed[0]!=current['request']['player']
  assert Decimal(str(old['beliefs'][changed[0]]))==Decimal(receipt['old_value'])
  assert Decimal(str(new['beliefs'][changed[0]]))==Decimal(receipt['new_value'])
  assert abs(Decimal(receipt['new_value'])-Decimal(receipt['old_value']))<=Decimal(receipt['rounding_budget'])
  assert sum(Decimal(str(v)) for v in new['beliefs'].values())==Decimal(receipt['new_sum'])
  recovery_receipts.append({'episode':name,'seed':cfg['seed'],'request':receipt['request'],'status':receipt['status'],'original_attempts_preserved':True})
 index=ep/'recovery/rounding-v1/original-sha256.json'
 if index.exists():
  snap=json.loads(index.read_text())
  for relative,digest in snap['files'].items():assert hashlib.sha256((index.parent/'original'/relative).read_bytes()).hexdigest()==digest
assert total_encounters==3000 and request_statuses=={'complete':12600}
repaired_seeds=sorted({r['seed'] for r in recovery_receipts})
groups=defaultdict(list)
for r in rows:groups[r['mode']].append(r)
metrics=('good_payoff_per_encounter','selfish_payoff_per_encounter','good_cooperation_rate','selfish_cooperation_rate','final_identification_rate','final_brier','false_accusation_rate')
cells=[]
for mode in spec['communication_modes']:
 rs=groups[mode];assert len(rs)==12
 cells.append({'mode':mode,'episodes':12,**{k:statistics.mean(r[k] for r in rs) for k in metrics},'good_to_good_C_rate':sum(r['C_to_good'] for r in rs)/sum(r['to_good'] for r in rs),'good_to_selfish_C_rate':sum(r['C_to_selfish'] for r in rs)/sum(r['to_selfish'] for r in rs)})
lookup={(r['seed'],r['mode']):r for r in rows};comparisons=[]
for mode in spec['communication_modes'][1:]:
 differences=[lookup[(seed,mode)]['good_payoff_per_encounter']-lookup[(seed,'none')]['good_payoff_per_encounter'] for seed in spec['seeds']]
 clean=[lookup[(seed,mode)]['good_payoff_per_encounter']-lookup[(seed,'none')]['good_payoff_per_encounter'] for seed in spec['seeds'] if seed not in repaired_seeds]
 comparisons.append({'contrast':mode+' minus none','mean_delta':statistics.mean(differences),'positive_seeds':sum(x>0 for x in differences),'negative_seeds':sum(x<0 for x in differences),'tied_seeds':sum(x==0 for x in differences),'differences':differences,'excluding_repaired_seeds_n':len(clean),'excluding_repaired_seeds_mean_delta':statistics.mean(clean)})
result={'checked_at_local':datetime.datetime.now(ZoneInfo('America/Los_Angeles')).isoformat(),'source_commit':(out/'source-commit.txt').read_text().strip(),'completed_episodes':60,'rounds_per_episode':10,'encounters':3000,'accepted_requests':12600,'raw_response_attempts':raw_attempts,'validation_error_attempts':dict(validation_errors),'transport_error_events':dict(transport_errors),'reported_cost_usd':str(reported_cost),'responses_missing_cost':missing_cost,'recovery_receipts':recovery_receipts,'repaired_seeds':repaired_seeds,'all_checkpoints_and_saved_summaries_match':True,'all_seed_roles_schedules_and_leaders_match':True,'all_original_recovery_archive_hashes_pass':True,'cells':cells,'paired_comparisons':comparisons}
Path('/tmp/intentional-luna-completion-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
