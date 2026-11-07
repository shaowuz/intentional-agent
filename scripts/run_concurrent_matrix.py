"""Resume independent episodes using a matrix's unmodified, frozen game runtime."""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import threading
import time
import uuid


class DrainRequested(BaseException):
    """Stop at a phase boundary after accepted responses have been checkpointed."""


class StabilityGate:
    def __init__(self, seconds=180, minimum_responses=10, maximum_age=60):
        self.seconds = seconds
        self.minimum_responses = minimum_responses
        self.maximum_age = maximum_age
        self.baseline = None
        self.since = None

    def ready(self, rows, now):
        current = {r['episode_id']: r for r in rows}
        if not current or any(r['checkpoint_age_seconds'] > self.maximum_age for r in rows):
            self.baseline = self.since = None
            return False
        if (self.baseline is None or current.keys() != self.baseline.keys()
                or any(r['retry_events'] != self.baseline[k]['retry_events']
                       for k, r in current.items())):
            self.baseline, self.since = current, now
            return False
        return now - self.since >= self.seconds and all(
            r['accepted_requests'] - self.baseline[k]['accepted_requests'] >= self.minimum_responses
            for k, r in current.items()
        )


def run_pool(entries, run_one, *, workers, maximum_workers, stop, poll, poll_seconds=10):
    """Bound submissions; drain active phases before propagating any worker failure."""
    pending = iter(entries)
    exhausted = False
    failure = None
    limit = workers
    next_poll = 0
    with ThreadPoolExecutor(max_workers=maximum_workers, thread_name_prefix='episode') as executor:
        active = {}
        try:
            while active or (not exhausted and not stop.is_set()):
                while not exhausted and not stop.is_set() and len(active) < limit:
                    entry = next(pending, None)
                    if entry is None:
                        exhausted = True
                        break
                    active[executor.submit(run_one, entry)] = entry
                if time.monotonic() >= next_poll:
                    proposed = poll(list(active.values()), limit)
                    if type(proposed) is not int or not workers <= proposed <= maximum_workers:
                        raise ValueError('Scheduler requested an invalid worker limit')
                    limit = proposed
                    next_poll = time.monotonic() + poll_seconds
                if not active:
                    continue
                done, _ = wait(active, timeout=0.25, return_when=FIRST_COMPLETED)
                for future in done:
                    del active[future]
                    try:
                        future.result()
                    except DrainRequested:
                        stop.set()
                    except BaseException as exc:
                        failure = failure or exc
                        stop.set()
        except BaseException:
            stop.set()
            raise
        if failure is not None:
            raise failure


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, default=Path('.env'))
    parser.add_argument('--workers', type=int, default=5)
    parser.add_argument('--ramp-to', type=int)
    parser.add_argument('--stable-seconds', type=float, default=180)
    parser.add_argument('--minimum-responses', type=int, default=10)
    args = parser.parse_args(argv)
    maximum = args.workers if args.ramp_to is None else args.ramp_to
    if not 1 <= args.workers <= maximum <= 60:
        parser.error('Require 1 <= workers <= ramp-to <= 60')
    if args.stable_seconds < 0 or args.minimum_responses < 1:
        parser.error('Stability duration must be nonnegative and minimum-responses positive')
    output = args.output.resolve()
    runtime = output / 'runtime'
    if not (runtime / 'swarm_game/__init__.py').is_file():
        parser.error('An existing matrix with its saved runtime is required')
    if any(k == 'swarm_game' or k.startswith('swarm_game.') for k in sys.modules):
        raise RuntimeError('Launch this scheduler in a fresh Python process to load the frozen runtime')
    sys.path.insert(0, str(runtime))

    from dotenv import load_dotenv
    from swarm_game.config import Config
    from swarm_game.export_contract import validate_output
    from swarm_game.matrix import SCHEMA_VERSION, episode_plan, make_provider, normalize_spec, preview
    from swarm_game.matrix_analysis import analyze_matrix
    from swarm_game.runner import run_episode
    from swarm_game.storage import exclusive_run, provenance, read_json, write_json

    load_dotenv(args.env_file, override=False)
    stop = threading.Event()
    print_lock = threading.Lock()

    def log(message):
        with print_lock:
            print(message, flush=True)

    def request_stop(signum, frame):
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, request_stop)

    with exclusive_run(output):
        manifest_path = output / 'matrix_manifest.json'
        manifest = read_json(manifest_path)
        spec = normalize_spec(read_json(output / 'spec.json'))
        if (manifest['schema_version'] != SCHEMA_VERSION
                or manifest['spec'] != spec or manifest['plan'] != episode_plan(spec)
                or manifest['counts'] != preview(spec)
                or manifest['provenance'] != provenance()
                or read_json(runtime / 'provenance.json') != provenance()):
            raise ValueError('Saved matrix specification or frozen runtime provenance differs')
        # Validate every existing episode before any additional hosted request.
        analyze_matrix(output)
        if spec['game']['backend'] == 'openrouter':
            for model in spec['models']:
                provider = make_provider(Config(**spec['game'], model=model,
                                                selfish_count=spec['selfish_counts'][0]))
                try:
                    provider.catalog_entry()
                finally:
                    provider.close()

        entries = [e for e in manifest['plan']
                   if not (output / 'episodes' / e['episode_id'] / 'checkpoint.json').exists()
                   or not read_json(output / 'episodes' / e['episode_id'] / 'checkpoint.json')['completed']]
        started = datetime.now(timezone.utc).isoformat()
        receipt_path = output / 'executions' / f"{uuid.uuid4()}.json"
        receipt = {
            'status': 'running', 'started_at': started, 'pid': os.getpid(),
            'scheduler_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'matrix_manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            'runtime_provenance': provenance(), 'initial_workers': args.workers,
            'worker_limit': args.workers, 'maximum_workers': maximum, 'peak_active_episodes': 0,
            'stable_seconds': args.stable_seconds, 'minimum_responses_per_episode': args.minimum_responses,
            'ramp_events': [], 'active': [], 'planned_episodes': len(manifest['plan']),
        }
        gate = StabilityGate(args.stable_seconds, args.minimum_responses)

        def publish():
            receipt['updated_at'] = datetime.now(timezone.utc).isoformat()
            write_json(receipt_path, receipt)
            write_json(output / 'execution.json', receipt)

        def run_one(entry):
            name = entry['episode_id']
            episode = output / 'episodes' / name
            config = Config(**entry['config'])
            provider = make_provider(config)

            def progress(message):
                if stop.is_set():
                    raise DrainRequested()
                log(f'{name}: {message}')

            try:
                log(f'Starting {name}')
                return run_episode(config, provider, episode, resume=episode.exists(), progress=progress)
            finally:
                if hasattr(provider, 'close'):
                    provider.close()

        def poll(active, limit):
            rows = []
            completed = 0
            for entry in manifest['plan']:
                cp = output / 'episodes' / entry['episode_id'] / 'checkpoint.json'
                if cp.exists():
                    completed += bool(read_json(cp)['completed'])
            for entry in active:
                episode = output / 'episodes' / entry['episode_id']
                cp = episode / 'checkpoint.json'
                if not cp.exists():
                    continue
                state = read_json(cp)
                records = [read_json(p) for p in (episode / 'requests').glob('*.json')]
                rows.append({
                    'episode_id': entry['episode_id'], 'round': state['round'], 'phase': state['phase'],
                    'accepted_requests': sum(r.get('complete', False) for r in records),
                    'retry_events': sum(len(r.get('transport_events', [])) +
                                       sum('validation_error' in a for a in r['attempts']) for r in records),
                    'checkpoint_age_seconds': round(max(0, time.time() - cp.stat().st_mtime), 2),
                })
            if (not stop.is_set() and limit < maximum and len(rows) == args.workers
                    and gate.ready(rows, time.monotonic())):
                receipt['ramp_events'].append({'at': datetime.now(timezone.utc).isoformat(),
                                              'from': limit, 'to': maximum, 'evidence': rows})
                limit = maximum
                log(f'Stability gate passed; increasing to {limit} concurrent episodes')
            receipt.update(worker_limit=limit, active=rows, completed_episodes=completed,
                           peak_active_episodes=max(receipt['peak_active_episodes'], len(active)),
                           status='draining' if stop.is_set() else 'running')
            publish()
            return limit

        publish()
        failure = None
        try:
            run_pool(entries, run_one, workers=args.workers, maximum_workers=maximum,
                     stop=stop, poll=poll)
        except BaseException as exc:
            failure = exc
        # All episode workers have stopped before shared exports are regenerated.
        result = analyze_matrix(output)
        receipt.update(active=[], completed_episodes=result['completed_episodes'],
                       finished_at=datetime.now(timezone.utc).isoformat())
        receipt['validation'] = validate_output(output)
        receipt['status'] = 'failed' if failure else 'paused' if stop.is_set() else result['status']
        if failure:
            receipt['error'] = f'{type(failure).__name__}: {failure}'
        publish()
        if failure:
            raise failure
        log(f"Scheduler {receipt['status']}: {result['completed_episodes']}/{len(manifest['plan'])} episodes")
        return 130 if stop.is_set() else 0


if __name__ == '__main__':
    raise SystemExit(main())
