"""Build analysis inputs from verified Sonnet cohort tables; no hosted requests."""
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STUDY = ROOT / 'experiments/swarm-game/studies/sonnet-5.5-1000-seeds5'
MODES = ['none', 'public', 'opponent', 'good_leader', 'selfish_leader']


def read_json(path):
    return json.loads(path.read_text())


def build():
    output = STUDY / 'analysis'
    output.mkdir(exist_ok=True)
    combined = {name: [] for name in ['episodes', 'cells', 'contrasts', 'usage']}
    cohorts = []
    common_spec = common_runtime = None
    for count in (1, 3, 5):
        folder = STUDY / f'selfish-{count}'
        spec = read_json(folder / 'spec.json')
        assert spec['models'] == ['anthropic/claude-sonnet-5.5']
        assert spec['selfish_counts'] == [count] and spec['seeds'] == list(range(5))
        assert spec['communication_modes'] == MODES
        assert spec['game']['message_tokens'] == 1000
        assert spec['game']['tokenizer'] == 'o200k_base'
        assert spec['game']['max_completion_tokens'] == 4096
        signature = {k: v for k, v in spec.items() if k != 'selfish_counts'}
        common_spec = signature if common_spec is None else common_spec
        assert signature == common_spec
        manifest = read_json(folder / 'matrix_manifest.json')
        provenance = manifest['provenance']
        runtime = {k: v for k, v in provenance.items() if k != 'python'}
        common_runtime = runtime if common_runtime is None else common_runtime
        assert runtime == common_runtime
        execution = read_json(folder / 'execution.json')
        assert execution['status'] == 'complete' and execution['completed_episodes'] == 25
        data = {}
        for table in combined:
            path = folder / (table + '.csv')
            with path.open(newline='') as stream:
                data[table] = list(csv.DictReader(stream))
            source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            for row in data[table]:
                assert int(row['selfish_count']) == count
                assert row['model'] == spec['models'][0]
                combined[table].append({**row, 'study_cohort': f'selfish-{count}',
                    'source_csv': path.relative_to(ROOT).as_posix(),
                    'source_csv_sha256': source_hash,
                    'retry_correction_limit': 5 if count == 3 else 1})
        episodes = data['episodes']
        assert len(episodes) == 25
        assert {(int(r['seed']), r['communication']) for r in episodes} == {
            (seed, mode) for seed in range(5) for mode in MODES}
        assert all(r['status'] == 'complete' and int(r['completed_model_responses']) >= 210 for r in episodes)
        assert sum(r['accepted'].lower() == 'true' for r in data['usage']) == 5250
        assert len({r['run_id'] for r in episodes}) == 1
        assert all(int(r['completed_episodes']) == 5 for r in data['cells'])
        cost = sum((Decimal(r['reported_cost_usd']) for r in data['usage']), Decimal(0))
        cohort = {'selfish_count': count, 'computer': {1: 1, 3: 2, 5: 3}[count],
            'status': 'complete', 'run_id': episodes[0]['run_id'], 'episodes': 25,
            'accepted_requests': 5250, 'response_attempts': len(data['usage']),
            'reported_cost_usd': str(cost), 'python': provenance['python'],
            'code_sha256': provenance['code_sha256'], 'prompt_sha256': provenance['prompt_sha256'],
            'source_commit_recorded': None if count == 1 else 'e4e1ac41ee41fcea7fcf96e78dead2b853c59014',
            'source_note': 'Git commit not recorded in supplied cohort; code and prompt hashes match other two cohorts.' if count == 1 else 'Recorded collection commit; later main prompt edits do not apply.',
            'retry_correction_limit': 5 if count == 3 else 1,
            'retry_policy_note': 'User-authorized extension after exhausted corrections; unchanged validation.' if count == 3 else 'Original scheduler; no retry-policy override recorded.',
            'archive': 'complete-output.tar.xz', 'archive_manifest': 'archive-manifest.json'}
        (folder / 'cohort.json').write_text(json.dumps(cohort, indent=2) + '\n')
        cohorts.append(cohort)
    keys = [(r['run_id'], r['episode_id']) for r in combined['episodes']]
    assert len(keys) == len(set(keys)) == 75
    for table, rows in combined.items():
        fields = list(dict.fromkeys(k for row in rows for k in row))
        with (output / f'{table}.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    result = {'model': 'anthropic/claude-sonnet-5.5', 'common_spec': common_spec,
        'cohorts': cohorts, 'episodes': 75, 'encounters': 3750, 'accepted_requests': 15750,
        'reported_cost_usd': str(sum((Decimal(c['reported_cost_usd']) for c in cohorts), Decimal(0))),
        'tables': {table: len(rows) for table, rows in combined.items()},
        'analysis_notes': ['Use (run_id, episode_id) as episode key.',
            'Within each selfish count, compare conditions using paired seeds; seeds are the sampling units.',
            'Do not treat 75 episodes or 15,750 requests as independent experimental replicates.',
            'Different selfish counts have different role rosters; do not assume identical roles across counts.',
            'Python versions differ; selfish-3 has a documented retry-policy extension.',
            'Original messages include Keep them brief; later main removed this only for future runs.']}
    (STUDY / 'study.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['episodes', 'encounters', 'accepted_requests', 'reported_cost_usd', 'tables']}, indent=2))


if __name__ == '__main__':
    build()
