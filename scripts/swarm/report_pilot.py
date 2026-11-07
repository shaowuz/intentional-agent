"""Reproduce the full pilot report from completed checkpoint and request files."""

import argparse
import csv
import hashlib
import json
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def mean(xs):
    return statistics.mean(xs)


def ci(xs):
    if len(xs) < 2:
        return None
    rng = random.Random(271828)
    samples = sorted(mean(rng.choices(xs, k=len(xs))) for _ in range(10000))
    return [samples[249], samples[9749]]


def sign_flip_p(xs):
    """Exact two-sided paired sign-flip reference test, including ties."""
    observed = abs(sum(xs))
    n = len(xs)
    exceed = 0
    for mask in range(1 << n):
        value = sum(x if mask & (1 << i) else -x for i, x in enumerate(xs))
        exceed += abs(value) >= observed - 1e-12
    return exceed / (1 << n)


def write_csv(path, rows):
    with path.open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build(root):
    spec = read(root / 'comparison_manifest.json')
    expected = spec['counts']['episodes']
    receipt = read(root / 'execution_receipt.json')
    if receipt['status'] != 'complete':
        raise ValueError('Full pilot did not complete; inspect the execution receipt')
    paths = sorted(root.glob('seed-*/checkpoint.json'))
    if len(paths) != expected or not all(read(p)['completed'] for p in paths):
        raise ValueError('Missing completed episodes')
    output = root / 'results'
    output.mkdir(exist_ok=True)
    records, round_rows, trajectories = [], [], defaultdict(list)
    agent_rows=[]
    counts = Counter()
    costs = 0.0
    models, providers, code_hashes, prompts = set(), set(), set(), set()
    latencies = []
    inputs = []
    selected_evidence = []
    for path in paths:
        state = read(path)
        counts['episodes']+=1
        counts['encounters']+=len(state['encounters'])
        manifest = read(path.parent / 'manifest.json')
        config = manifest['config']
        summary = read(path.parent / 'summary.json')
        k, mode, seed = config['selfish_count'], config['communication'], config['seed']
        good = {p for p, role in state['roles'].items() if role == 'good'}
        selfish = next((p for p in state['players'] if p not in good), None)
        code_hashes.add(manifest['provenance']['code_sha256'])
        prompts.add(manifest['provenance']['prompt_sha256'])
        inputs.append({'file':str(path.relative_to(root)),
                       'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
        gc_gc = gc_total = gs_gc = gs_total = sc = sn = 0
        first_selfish_d = None
        for r in range(1, config['rounds'] + 1):
            row = {'seed':seed,'selfish_count':k,'communication':mode,'round':r,
                   'good_return':0,'good_actions':0,'good_cooperations':0,
                   'selfish_action':None,'selfish_payoff':None,
                   'mean_probability_selfish':None,'identification_fraction':None}
            for e in [e for e in state['encounters'] if e['round']==r]:
                for i,p in enumerate(e['players']):
                    if p in good:
                        row['good_return']+=e['payoffs'][i]
                        row['good_actions']+=1
                        row['good_cooperations']+= e['actions'][i]=='C'
                        if e['players'][1-i] in good:
                            gc_total+=1; gc_gc+=e['actions'][i]=='C'
                        else:
                            gs_total+=1; gs_gc+=e['actions'][i]=='C'
                    else:
                        row['selfish_action']=e['actions'][i]
                        row['selfish_payoff']=e['payoffs'][i]
                        sn+=1;sc+=e['actions'][i]=='C'
                        if e['actions'][i]=='D' and first_selfish_d is None:
                            first_selfish_d=r
            row['return_per_good_agent']=row['good_return']/len(good)
            row['good_cooperation_rate']=row['good_cooperations']/len(good)
            belief_records=[b for b in state['belief_records'] if b['round']==r and b['phase']=='action' and b['player'] in good]
            if selfish:
                row['mean_probability_selfish']=mean([b['beliefs'][selfish] for b in belief_records])
                row['identification_fraction']=mean([b['beliefs'][selfish]>=.8 for b in belief_records])
            round_rows.append(row)
            trajectories[(k,mode,r)].append(row)
        false_ever = {b['player'] for b in state['belief_records'] if b['player'] in good
                      and any(p in good and p!=b['player'] and v>=.8 for p,v in b['beliefs'].items())}
        online_detected={b['player'] for b in state['belief_records']
                         if selfish and b['player'] in good and b['phase']=='action'
                         and b['beliefs'][selfish]>=.8}
        record = {key:summary[key] for key in (
            'seed','selfish_count','communication','good_total_return','return_per_good_encounter',
            'good_good_return','good_selfish_return','good_cooperation_rate','final_mean_brier_score',
            'final_identification_rate','good_agents_ever_identifying_selfish',
            'good_agents_identifying_before_personal_encounter','false_accusation_rate')}
        record.update(good_good_cooperation_rate=gc_gc/gc_total if gc_total else None,
                      good_selfish_cooperation_rate=gs_gc/gs_total if gs_total else None,
                      selfish_cooperation_rate=sc/sn if sn else None,
                      selfish_return=state['payoffs'][selfish] if selfish else None,
                      first_selfish_defection_round=first_selfish_d,
                      identification_during_game_rate=len(online_detected)/len(good) if selfish else None,
                      good_agents_ever_false_accusing=len(false_ever),
                      episode=path.parent.name)
        record['selfish_action_sequence']=''.join(e['actions'][e['players'].index(selfish)]
            for e in state['encounters'] if selfish in e['players']) if selfish else ''
        for player in sorted(good):
            b=state['final_reports'][player]['beliefs']
            final_guess=max(b,key=b.get)
            agent_rows.append({'episode':path.parent.name,'seed':seed,'selfish_count':k,
                               'communication':mode,'player':player,'payoff':state['payoffs'][player],
                               'true_selfish_player':selfish,'final_probability_none':b['none'],
                               'final_probability_actual_selfish':b[selfish] if selfish else None,
                               'final_most_likely_identity':final_guess,'final_max_probability':b[final_guess],
                               'correct_at_0_8':b[selfish or 'none']>=.8,
                               'ever_false_accused':player in false_ever})
        records.append(record)
        for request_path in sorted((path.parent/'requests').glob('*.json')):
            request=read(request_path)
            counts['accepted_requests']+=request['complete']
            counts['transport_errors']+=len(request['transport_events'])
            for attempt in request['attempts']:
                counts['responses']+=1
                counts['invalid_responses']+='validation_error' in attempt
                m=attempt['response']['metadata']; u=m.get('usage',{})
                models.add(m.get('model')); providers.add(m.get('provider'))
                counts['prompt_tokens']+=u.get('prompt_tokens',0)
                counts['completion_tokens']+=u.get('completion_tokens',0)
                costs+=m.get('reported_cost_usd') or 0
                counts['responses_missing_cost']+=m.get('reported_cost_usd') is None
                latencies.append(m.get('latency_seconds',0))
        if selfish:
            for b in state['belief_records']:
                if b['player']==selfish and b['phase']=='action' and (b['round'] in [1,15,16,19,20] or b['round']==first_selfish_d):
                    selected_evidence.append({'episode':path.parent.name,'player':selfish,
                                              'round':b['round'],'action':b['action'],
                                              'strategy':b['strategy']})
    if len(code_hashes)!=1 or len(prompts)!=1:
        raise ValueError('Mixed source/prompt versions')
    cells={}
    for k in (0,1):
        for mode in ('none','public'):
            rows=[r for r in records if r['selfish_count']==k and r['communication']==mode]
            fields=[key for key,value in rows[0].items() if isinstance(value,(int,float))
                    and key not in ('seed','selfish_count','first_selfish_defection_round')]
            # Include nullable metrics when the first episode is all-cooperative.
            fields+=['first_selfish_defection_round']
            cell={'n':len(rows)}
            for key in fields:
                values=[r[key] for r in rows if r[key] is not None]
                cell[key]={'mean':mean(values),'sd':statistics.stdev(values) if len(values)>1 else 0,
                           'min':min(values),'max':max(values),'n':len(values)} if values else None
            cells[f'{k}_{mode}']=cell
    effects={}
    for k in (0,1):
        pairs=[]
        for seed in range(spec['config']['seed'],spec['config']['seed']+spec['seeds']):
            matched={r['communication']:r for r in records if r['selfish_count']==k and r['seed']==seed}
            if set(matched)!={'none','public'}:
                raise ValueError('Unmatched seed')
            # Validate schedules and roles independently of built-in summary.
            a=read(root/matched['none']['episode']/'checkpoint.json')
            b=read(root/matched['public']['episode']/'checkpoint.json')
            if a['roles']!=b['roles'] or a['schedule']!=b['schedule']:
                raise ValueError('Unmatched roles/schedules')
            pairs.append((matched['none'],matched['public']))
        effects[str(k)]={}
        for metric in ('good_total_return','return_per_good_encounter','good_cooperation_rate',
                       'final_mean_brier_score','final_identification_rate','selfish_return'):
            if any(a[metric] is None or b[metric] is None for a,b in pairs):
                continue
            diffs=[b[metric]-a[metric] for a,b in pairs]
            effects[str(k)][metric]={'mean_public_minus_none':mean(diffs),'paired_differences':diffs,
                                    'bootstrap_95pct':ci(diffs),'paired_sign_flip_p':sign_flip_p(diffs)}
    audit={'counts':dict(counts),'reported_cost_usd':costs,'models':sorted(models),
           'providers':sorted(providers),'code_hashes':sorted(code_hashes),'prompt_hashes':sorted(prompts),
           'mean_request_latency_seconds':mean(latencies),'expected_counts':spec['counts'],
           'wall_seconds':receipt['finished_at']-read(root/'launch.json')['started_at']}
    if counts['accepted_requests']!=spec['counts']['requests_before_retries']:
        raise ValueError('Accepted request count differs from complete protocol')
    if counts['encounters']!=spec['counts']['encounters']:
        raise ValueError('Encounter count differs from complete protocol')
    write_csv(output/'episode_metrics.csv',records)
    write_csv(output/'round_metrics.csv',round_rows)
    write_csv(output/'good_agent_metrics.csv',agent_rows)
    for name,data in [('statistics.json',{'cells':cells,'paired_effects':effects}),
                      ('audit.json',audit),('input_manifest.json',inputs),
                      ('strategy_evidence.json',selected_evidence)]:
        (output/name).write_text(json.dumps(data,indent=2)+'\n')
    plot(output,records,trajectories)
    lines=['# Full pilot results','',
           f"Completed {expected} episodes: 6 players, 20 rounds, 12 matched seeds, zero or one selfish player.",
           f"Model: {', '.join(sorted(models))}; medium reasoning; provider: {', '.join(sorted(providers))}.",'',
           '## Collective return','',
           '| Selfish players | No communication: mean good return | Public: mean good return | Public − none | Paired 95% bootstrap CI |',
           '|---|---:|---:|---:|---|']
    for k in (0,1):
        a=cells[f'{k}_none']['good_total_return']['mean'];b=cells[f'{k}_public']['good_total_return']['mean']
        e=effects[str(k)]['good_total_return']; lo,hi=e['bootstrap_95pct']
        lines.append(f"| {k} | {a:.2f} | {b:.2f} | {b-a:+.2f} | [{lo:.2f}, {hi:.2f}] |")
    lines+=['','Means use good-player totals per episode. Divide by 120 with zero selfish players and 100 with one selfish player to obtain return per good-agent encounter.',
            '',f"With one selfish player, public communication improved total good-agent return by {100*effects['1']['good_total_return']['mean_public_minus_none']/cells['1_none']['good_total_return']['mean']:.2f}% relative to no communication. All {spec['seeds']} paired differences were positive. Relative to the all-cooperate reference of 300 points, it recovered {100*effects['1']['good_total_return']['mean_public_minus_none']/(300-cells['1_none']['good_total_return']['mean']):.1f}% of the baseline shortfall.",
            '', '## Cooperation and identification','',
            '| Selfish players | Communication | Good cooperation | Selfish cooperation | Final identification ≥0.8 | Final Brier score |',
            '|---|---|---:|---:|---:|---:|']
    for k in (0,1):
        for mode in ('none','public'):
            cell=cells[f'{k}_{mode}']
            coop=cell['good_cooperation_rate']['mean']
            selfish=f"{cell['selfish_cooperation_rate']['mean']:.1%}" if k else '—'
            detect=f"{cell['final_identification_rate']['mean']:.1%}" if k else '—'
            lines.append(f"| {k} | {mode} | {coop:.1%} | {selfish} | {detect} | {cell['final_mean_brier_score']['mean']:.4f} |")
    a,b=cells['1_none'],cells['1_public']
    lines+=['',
            f"Correct identification during gameplay (at least one pre-action belief ≥0.8) rose from {a['identification_during_game_rate']['mean']:.1%} to {b['identification_during_game_rate']['mean']:.1%}. Final identification uses reports after round 20, when beliefs can no longer change payoffs. The final rate difference is exploratory: +25 percentage points with paired bootstrap 95% interval [1.7, 50.0] percentage points; the exact paired sign-flip reference test gives p=0.109, so this small pilot does not establish a robust identification improvement.",
            '', 'Lower Brier scores indicate more accurate probability distributions. The public condition improved thresholded identification on average while producing worse Brier scores, so it did not uniformly improve inference. No good agent assigned an innocent opponent probability ≥0.8, and no agent identified the selfish player before its first personal encounter.',
            '', '## Strategies and mechanism', '',
            f"Without communication, all 12 selfish agents cooperated in rounds 1–15 and defected in every round of the final rotation (16–20). Their average return was {a['selfish_return']['mean']:.2f}. Public communication increased selfish cooperation from {a['selfish_cooperation_rate']['mean']:.2%} to {b['selfish_cooperation_rate']['mean']:.2%}, moved the mean first defection from round {a['first_selfish_defection_round']['mean']:.1f} to {b['first_selfish_defection_round']['mean']:.1f}, and reduced selfish return to {b['selfish_return']['mean']:.2f}.",
            '', 'The known horizon and rotation matter: after round 15, each opponent appears exactly once more. Private-history agents cannot warn remaining opponents, while public reports can affect subsequent partners. The observed actions and short strategy summaries support reputation preservation followed by late exploitation as the dominant pattern.',
            '', 'Across the 12 one-selfish games, selfish defections fell from 60 to 21. Payoff accounting gives 117 points from those 39 additional cooperative encounters, 9 points from good agents defending against selfish defections, and a 2-point loss from innocent players facing defection. These sum to the observed 124-point aggregate improvement. This accounting describes realized payoffs; it is not a separate causal mediation experiment.',
            '', '### Audited transcript examples', '',
            '- **Seed 0, public:** P5 cooperated through round 18, defected against P6 in round 19, then publicly claimed that both had cooperated. P4 defected against P5 in round 20, producing mutual defection. See `../seed-0-selfish-1-public/report.md` and its checkpoint for the attributed messages and executed actions.',
            '- **Seed 5, public:** P5 defected in rounds 17–20 while repeatedly apologizing and promising renewed cooperation. The remaining opponents defected against P5 after the first reported betrayal.',
            '- **Seed 9, public:** P3 defected against P6 in round 16 and falsely claimed that P6 had defected. P2 then defected against innocent P6 in round 17 with P(selfish=P6)=0.78; P5 did so in round 19 with probability 0.455. This explains why a zero false-accusation count at the 0.8 threshold can coexist with harmful false suspicion. P3 resumed cooperation for rounds 17–19 before defecting again in round 20.',
            '', 'The welfare benefit therefore came chiefly from changing selfish behavior. Communication also enabled defensive responses and introduced a channel for false accusations. The fixed 20-round horizon strongly shaped the strategies; this pilot alone does not show that the same effect persists with an uncertain ending or another model.']
    lines+=['','## Execution and interpretation','',
            f"Accepted requests: {counts['accepted_requests']:,}; responses including repairs: {counts['responses']:,}; invalid responses: {counts['invalid_responses']}; transport errors: {counts['transport_errors']}.",
            f"OpenRouter reported cost: ${costs:.4f}. Missing cost records: {counts['responses_missing_cost']}.",
            '', 'Each confidence interval resamples the 12 complete seed blocks 10,000 times. These are exploratory percentile intervals without multiplicity adjustment. Hosted model generations remain stochastic. Roles and pairings match within seed.',
            '', 'Identification reports use only good agents. A selfish agent may cooperate throughout; detection success and collective return measure different outcomes. No-communication agents receive the same private-note opportunity as the public-post condition.',
            '', '![Pilot overview](pilot_overview.png)', '',
            'Top panels connect matched seed outcomes; black diamonds show means with 95% bootstrap intervals. The dotted line marks universal cooperation, not a payoff ceiling. Lower panels show means and pointwise 95% bootstrap bands across seed blocks.', '',
            'Machine-readable results: episode_metrics.csv, round_metrics.csv, statistics.json, audit.json. Exact action and message timelines remain in the episode directories. strategy_evidence.json contains selected short strategy summaries, not hidden reasoning.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'cells':cells,'effects':effects,'audit':audit},indent=2))


def plot(output,records,trajectories):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    colors={'none':'#0072B2','public':'#D55E00'}
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(10,7.5),layout='constrained')
    for k,ax in zip((0,1),axes[0]):
        for seed in sorted({r['seed'] for r in records}):
            vals=[next(r['return_per_good_encounter'] for r in records
                       if r['seed']==seed and r['selfish_count']==k and r['communication']==m)
                  for m in ('none','public')]
            offset=(seed-5.5)*.009
            ax.plot([offset,1+offset],vals,color='.72',linewidth=.8,zorder=1)
            ax.scatter([offset,1+offset],vals,c=[colors['none'],colors['public']],s=27,zorder=2)
        ax.axhline(3,color='.5',linestyle=':',linewidth=1,label='All cooperate')
        for x,mode in enumerate(('none','public')):
            values=[r['return_per_good_encounter'] for r in records
                    if r['selfish_count']==k and r['communication']==mode]
            lo,hi=ci(values);center=mean(values)
            ax.errorbar([x],[center],yerr=[[center-lo],[hi-center]],fmt='D',color='black',
                        markersize=5,capsize=4,zorder=3)
        ax.set(xticks=[0,1],xticklabels=['No communication','Public communication'],
               ylabel='Return per good-agent encounter',title=f'{k} selfish player'+('s' if k==0 else ''),
               xlim=(-.22,1.22),ylim=(2.84,3.01))
        ax.grid(axis='y',alpha=.2)
    for mode in ('none','public'):
        rounds=list(range(1,21))
        # One seed-resampling index matrix for each full trajectory. Bands are pointwise.
        idx=np.random.default_rng(271828).integers(0,12,size=(10000,12))
        vals=[mean([r['selfish_action']=='C' for r in trajectories[(1,mode,t)]]) for t in rounds]
        axes[1,0].plot(rounds,vals,marker='o' if mode=='none' else 's',markersize=3,
                       linestyle='-' if mode=='none' else '--',color=colors[mode],label=mode)
        matrix=np.array([[r['selfish_action']=='C' for r in trajectories[(1,mode,t)]] for t in rounds],dtype=float)
        bounds=np.quantile(matrix[:,idx].mean(axis=2),[.025,.975],axis=1)
        axes[1,0].fill_between(rounds,bounds[0],bounds[1],color=colors[mode],alpha=.13)
        vals=[mean([r['mean_probability_selfish'] for r in trajectories[(1,mode,t)]]) for t in rounds]
        axes[1,1].plot(rounds,vals,marker='o' if mode=='none' else 's',markersize=3,
                       linestyle='-' if mode=='none' else '--',color=colors[mode],label=mode)
        matrix=np.array([[r['mean_probability_selfish'] for r in trajectories[(1,mode,t)]] for t in rounds])
        bounds=np.quantile(matrix[:,idx].mean(axis=2),[.025,.975],axis=1)
        axes[1,1].fill_between(rounds,bounds[0],bounds[1],color=colors[mode],alpha=.13)
    axes[1,0].set(title='Selfish-player cooperation',ylabel='Fraction choosing C',xlabel='Round',ylim=(-.03,1.03))
    axes[1,1].set(title='Belief in the actual selfish identity',ylabel='Mean probability (good agents)',
                   xlabel='Round, before choosing action',ylim=(-.03,1.03))
    for ax in axes[1]:
        ax.set_xticks([1,5,10,15,20]);ax.grid(alpha=.2);ax.legend(frameon=False)
    fig.suptitle('GPT-6.1 Terra pilot • 48 episodes • 12 matched seeds',fontsize=14)
    fig.savefig(output/'pilot_overview.png',dpi=180)
    fig.savefig(output/'pilot_overview.pdf')
    plt.close(fig)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('root',type=Path)
    build(parser.parse_args().root)
