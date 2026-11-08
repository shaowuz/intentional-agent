"""Read completed checkpoints and summarize encounters without new model calls.

Run with an existing Python environment containing matplotlib and numpy.
Inputs remain immutable; all derivatives go beside this script.
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics


HERE = Path(__file__).resolve().parent
OUTPUT = None
MODES = ['none', 'public', 'opponent', 'good_leader', 'selfish_leader']
LABELS = ['No communication', 'Full communication', 'Opponent only', 'Good leader', 'Selfish leader']


def rate(rows):
    return sum(r['action'] == 'C' for r in rows) / len(rows) if rows else None


def main():
    manifest_raw = (OUTPUT / 'matrix_manifest.json').read_bytes()
    manifest = json.loads(manifest_raw)
    execution = json.loads((OUTPUT / 'execution.json').read_text())
    assert execution['status'] == 'complete'
    assert execution['validation']['status'] == 'valid'
    actions, encounters, leader_beliefs = [], [], []
    states, hashes, seed_matching = {}, {}, {}
    for entry in manifest['plan']:
        config = entry['config']
        mode, seed = config['communication'], config['seed']
        raw = (OUTPUT / 'episodes' / entry['episode_id'] / 'checkpoint.json').read_bytes()
        state = json.loads(raw)
        assert state['completed'] and len(state['final_reports']) == 10
        assert len(state['encounters']) == 50
        assert config['selfish_count'] == 5 and config['model'] == 'openai/gpt-6-luna'
        assert sum(r == 'selfish' for r in state['roles'].values()) == 5
        match = (state['roles'], state['schedule'])
        assert seed not in seed_matching or seed_matching[seed] == match
        seed_matching[seed] = match
        states[seed, mode] = state
        hashes[entry['episode_id']] = hashlib.sha256(raw).hexdigest()
        leader = (state.get('leader_assignment') or {}).get('leader')
        seen = {}
        cumulative = dict.fromkeys(state['players'], 0)
        for encounter in state['encounters']:
            players = encounter['players']
            pair = tuple(sorted(players))
            repeated = pair in seen
            assert repeated == (encounter['round'] == 10)
            roles = [state['roles'][p] for p in players]
            pair_type = ''.join(sorted('G' if r == 'good' else 'S' for r in roles))
            order = [1, 0] if roles == ['selfish', 'good'] else [0, 1]
            outcome = ''.join(encounter['actions'][i] for i in order)
            assert encounter['payoffs'] == {
                ('C', 'C'): [3, 3], ('C', 'D'): [0, 5],
                ('D', 'C'): [5, 0], ('D', 'D'): [1, 1],
            }[tuple(encounter['actions'])]
            encounters.append({'seed': seed, 'mode': mode, 'round': encounter['round'],
                               'pair_type': pair_type, 'outcome': outcome,
                               'repeat': repeated, **encounter})
            for i, player in enumerate(players):
                cumulative[player] += encounter['payoffs'][i]
                actions.append({
                    'seed': seed, 'mode': mode, 'round': encounter['round'],
                    'player': player, 'role': roles[i], 'opponent': players[1-i],
                    'opponent_role': roles[1-i], 'action': encounter['actions'][i],
                    'opponent_action': encounter['actions'][1-i],
                    'payoff': encounter['payoffs'][i], 'repeat': repeated,
                    'is_leader': player == leader,
                })
            seen[pair] = encounter
        assert cumulative == state['payoffs']
        if leader:
            expected_role = 'good' if mode == 'good_leader' else 'selfish'
            assert state['roles'][leader] == expected_role
            for record in state['belief_records']:
                player = record['player']
                if state['roles'][player] != 'good' or player == leader:
                    continue
                prior = any(player in e['players'] and leader in e['players']
                            and (e['round'] < record['round'] or record['phase'] == 'final')
                            for e in state['encounters'])
                leader_beliefs.append({'seed': seed, 'mode': mode, 'player': player,
                                      'phase': record['phase'], 'round': record['round'],
                                      'prior_personal_encounter': prior,
                                      'probability_leader_selfish': record['beliefs'][leader]})
    assert len(states) == 60 and len(encounters) == 3000 and len(actions) == 6000

    summaries, round_rows, paired = {}, [], {}
    for mode in MODES:
        rows = [r for r in actions if r['mode'] == mode]
        good = [r for r in rows if r['role'] == 'good']
        selfish = [r for r in rows if r['role'] == 'selfish']
        summary = {'good_payoff_per_encounter': statistics.mean(r['payoff'] for r in good),
                   'selfish_payoff_per_encounter': statistics.mean(r['payoff'] for r in selfish),
                   'selfish_cooperative_actions': sum(r['action'] == 'C' for r in selfish),
                   'selfish_actions': len(selfish),
                   'exploitation_encounters': sum(r['action'] == 'C' and r['opponent_action'] == 'D'
                                                  and r['opponent_role'] == 'selfish' for r in good)}
        for opponent_role in ['good', 'selfish']:
            subset = [r for r in good if r['opponent_role'] == opponent_role]
            summary['good_vs_' + opponent_role] = {
                'actions': len(subset), 'cooperative_actions': sum(r['action'] == 'C' for r in subset),
                'cooperation_rate': rate(subset),
                'mean_payoff': statistics.mean(r['payoff'] for r in subset),
                'first_meeting_cooperation_rate': rate([r for r in subset if not r['repeat']]),
                'rematch_cooperation_rate': rate([r for r in subset if r['repeat']]),
            }
            for round_number in range(1, 11):
                selected = [r for r in subset if r['round'] == round_number]
                round_rows.append({'mode': mode, 'opponent_role': opponent_role,
                                   'round': round_number, 'actions': len(selected),
                                   'cooperative_actions': sum(r['action'] == 'C' for r in selected),
                                   'cooperation_rate': rate(selected)})
        summary['encounter_outcomes'] = dict(Counter(
            e['pair_type'] + '_' + e['outcome'] for e in encounters if e['mode'] == mode))
        for phase, round_number in [('action', 1), ('final', 10)]:
            values = [r['probability_leader_selfish'] for r in leader_beliefs
                      if r['mode'] == mode and r['phase'] == phase and r['round'] == round_number]
            if values:
                summary['leader_belief_' + phase] = {
                    'good_audience_members': len(values), 'mean_probability_selfish': statistics.mean(values),
                    'at_least_80_percent': sum(v >= .8 for v in values),
                }
        summaries[mode] = summary
        if mode != 'none':
            differences = []
            for seed in range(12):
                a, b = states[seed, 'none'], states[seed, mode]
                good_players = [p for p, role in a['roles'].items() if role == 'good']
                differences.append(sum(b['payoffs'][p] - a['payoffs'][p] for p in good_players) / 50)
            paired[mode] = {'per_seed_good_payoff_difference': differences,
                            'positive_seeds': sum(v > 0 for v in differences),
                            'ties': sum(v == 0 for v in differences),
                            'negative_seeds': sum(v < 0 for v in differences)}

    result = {
        'created_at': datetime.now(timezone.utc).isoformat(), 'input': str(OUTPUT),
        'matrix_manifest_sha256': hashlib.sha256(manifest_raw).hexdigest(),
        'checkpoint_sha256': hashes, 'validated_export_snapshot': execution['validation']['snapshot_id'],
        'sample': {'episodes': 60, 'matched_seeds': 12, 'encounters': 3000, 'player_decisions': 6000,
                   'model': 'openai/gpt-6-luna', 'selfish_players': 5, 'players': 10, 'rounds': 10},
        'conditions': summaries, 'rounds': round_rows, 'matched_seed_comparisons': paired,
        'leader_beliefs': leader_beliefs,
        'interpretation_notes': [
            'All rounds 1-9 pair players for the first time; all round 10 encounters are rematches.',
            'Round 10 confounds rematching with the final round.',
            'Rates pool observed actions, with 266 good-vs-good and 334 good-vs-selfish decisions per condition.',
            'The 12 matched seeds, rather than individual actions, are independent experimental units.',
            'Public messages include encounter reports and occasional voluntary role/action disclosures.',
        ],
    }
    (HERE / 'encounter_trends.json').write_text(json.dumps(result, indent=2) + '\n')
    for name, rows in [('actions', actions), ('rounds', round_rows), ('leader_beliefs', leader_beliefs)]:
        with (HERE / f'{name}.csv').open('w', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps({'conditions': summaries, 'paired': paired}, indent=2), flush=True)
    plot(round_rows)


def plot(round_rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter

    colors = ['#555555', '#0072B2', '#E69F00', '#009E73', '#CC79A7']
    markers = ['o', 's', '^', 'D', 'v']
    styles = ['--', '-', ':', '-.', '--']
    plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.1), sharey=True)
    for ax, opponent_role, title in zip(axes, ['good', 'selfish'],
                                       ['Good players facing good opponents', 'Good players facing selfish opponents']):
        for mode, label, color, marker, style in zip(MODES, LABELS, colors, markers, styles):
            rows = [r for r in round_rows if r['mode'] == mode and r['opponent_role'] == opponent_role]
            ax.plot([r['round'] for r in rows], [100 * r['cooperation_rate'] for r in rows],
                    color=color, marker=marker, linestyle=style, markersize=4.5, linewidth=1.7, label=label)
        ax.axvspan(9.5, 10.5, color='#eeeeee', zorder=-1)
        ax.set(xlim=(.8, 10.2), ylim=(-3, 103), xticks=range(1, 11), xlabel='Round', title=title)
        ax.yaxis.set_major_formatter(PercentFormatter(100))
        ax.grid(axis='y', color='#dddddd', linewidth=.6)
    axes[0].set_ylabel('Cooperate (C) decisions by good players')
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.5, .9), ncol=5, frameon=False, fontsize=10)
    fig.suptitle('Full communication supports selective cooperation', y=.99, fontsize=15)
    fig.text(.5, .045, 'Luna · 5 selfish / 10 players · 12 matched seeds per condition\n'
             'Pooled observed rates. Shaded round 10 is both the final round and a rematch; rounds 1–9 use new opponents.',
             ha='center', va='center', fontsize=9.5, color='#444444')
    fig.subplots_adjust(left=.075, right=.985, top=.76, bottom=.2, wspace=.12)
    for suffix in ['png', 'pdf']:
        fig.savefig(HERE / f'encounter_trends.{suffix}', dpi=180, facecolor='white')
    plt.close(fig)
    print('Wrote', HERE / 'encounter_trends.png', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True, help='Restored complete run directory')
    parser.add_argument('--output', type=Path, default=HERE, help='Directory for derived analysis files')
    args = parser.parse_args()
    OUTPUT = args.run.resolve()
    HERE = args.output.resolve()
    HERE.mkdir(parents=True, exist_ok=True)
    main()
