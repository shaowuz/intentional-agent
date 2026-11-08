"""Resume independent episodes using a matrix's unmodified, frozen game runtime."""

import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import signal
import sys
import threading
import time
import uuid


class DrainRequested(BaseException):
    """Stop at a phase boundary after accepted responses have been checkpointed."""


MARGINAL_BOUNDS_ERROR = 'marginal beliefs must imply between 1 and 5 selfish players'


def rounding_validator(original):
    """Apply only the six-decimal sum tolerance to a frozen legacy validator."""
    def validate(data, request, config):
        try:
            return original(data, request, config)
        except ValueError as exc:
            if str(exc) != MARGINAL_BOUNDS_ERROR or not config.marginal_beliefs:
                raise
            beliefs = data['beliefs']
            tolerance = max(1e-6, len(beliefs) * 0.5e-6)
            if not 1 - tolerance <= math.fsum(beliefs.values()) <= 5 + tolerance:
                raise
            expected = 1 if request.view['objective'] == 'selfish' else 0
            if beliefs[request.player] != expected:
                raise ValueError('self probability must match the known own objective') from None
            return data
    return validate


def recover_rounded_records(output, manifest, validate):
    """Revalidate the last saved response; archive original records without new calls."""
    from swarm_game.config import Config
    from swarm_game.protocol import make_request
    from swarm_game.storage import read_json, write_json

    recovery = output / 'recoveries' / str(uuid.uuid4())
    changes = []
    for entry in manifest['plan']:
        episode = output / 'episodes' / entry['episode_id']
        cp = episode / 'checkpoint.json'
        if not cp.exists():
            continue
        state = read_json(cp)
        config = Config(**entry['config'])
        for path in sorted((episode / 'requests').glob('*.json')):
            raw = path.read_bytes()
            record = json.loads(raw)
            if record.get('complete') or not record.get('attempts'):
                continue
            last = record['attempts'][-1]
            if last.get('validation_error') != MARGINAL_BOUNDS_ERROR:
                continue
            if last['response']['metadata'].get('finish_reason') not in (None, 'stop'):
                continue
            request = make_request(state, config, record['request']['player'])
            if request.to_dict() != record['request']:
                raise ValueError('Recovery request differs from the saved player view')
            data = json.loads(last['response']['content'])
            try:
                validate(data, request, config)
            except ValueError:
                continue
            relative = path.relative_to(output)
            backup = recovery / 'original_requests' / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open('xb') as file:
                file.write(raw)
                file.flush()
                os.fsync(file.fileno())
            record.update(complete=True, status='complete', data=data,
                          validation_recovery={'id': recovery.name, 'reason': 'six-decimal marginal rounding'})
            record.pop('error', None)
            write_json(path, record)
            changes.append({'request': str(relative), 'original_sha256': hashlib.sha256(raw).hexdigest(),
                            'recovered_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'accepted_attempt': len(record['attempts']),
                            'belief_sum': math.fsum(data['beliefs'].values())})
    if changes:
        write_json(recovery / 'receipt.json', {'at': datetime.now(timezone.utc).isoformat(),
                                             'new_model_calls': 0, 'records': changes})
    return {'receipt': str(recovery / 'receipt.json') if changes else None,
            'recovered_requests': len(changes), 'new_model_calls': 0}


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
    parser.add_argument('--allow-marginal-rounding', action='store_true',
                        help='Record a validation-only six-decimal rounding fix for the frozen runtime')
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
        # Validate manifests and game states before changing recovery metadata.
        analyze_matrix(output)
        override = None
        recovery = None
        override_path = output / 'validation_override.json'
        if override_path.exists() and not args.allow_marginal_rounding:
            raise ValueError('Resume this recovered run with --allow-marginal-rounding')
        if args.allow_marginal_rounding:
            from swarm_game import protocol, runner
            override = {'name': 'six-decimal-marginal-rounding',
                        'original_validator_sha256': hashlib.sha256(
                            inspect.getsource(protocol.validate_response).encode()).hexdigest(),
                        'replacement_wrapper_sha256': hashlib.sha256(
                            inspect.getsource(rounding_validator).encode()).hexdigest(),
                        'tolerance_per_marginal': 0.5e-6, 'minimum_tolerance': 1e-6}
            if override_path.exists() and read_json(override_path) != override:
                raise ValueError('Recorded validation override differs; inspect recovery provenance')
            validate = rounding_validator(protocol.validate_response)
            runner.validate_response = protocol.validate_response = validate
            write_json(override_path, override)
            recovery = recover_rounded_records(output, manifest, validate)
            log(f"Rounding recovery: {recovery['recovered_requests']} saved responses accepted; no model calls")
        if recovery and recovery['recovered_requests']:
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
            'validation_override': override, 'recovery': recovery,
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
