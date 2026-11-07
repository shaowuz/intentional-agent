import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import threading

import pytest
from swarm_game.export_contract import validate_output
from swarm_game.matrix import run_matrix
from swarm_game.providers import ProviderError, ScriptedProvider
from swarm_game.storage import read_json

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/run_concurrent_matrix.py'
spec = importlib.util.spec_from_file_location('concurrent_matrix', SCRIPT)
scheduler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scheduler)


def test_stability_requires_all_workers_progress_without_retries_or_stalls():
    gate = scheduler.StabilityGate(seconds=180, minimum_responses=10)

    def rows(count=0, retries=0, age=1):
        return [{'episode_id': str(i), 'accepted_requests': count, 'retry_events': retries,
                 'checkpoint_age_seconds': age} for i in range(5)]

    assert not gate.ready(rows(), 0)
    assert not gate.ready(rows(10), 179)
    slow = rows(10)
    slow[4]['accepted_requests'] = 9
    assert not gate.ready(slow, 180)
    assert gate.ready(rows(10), 180)
    assert not gate.ready(rows(10, retries=1), 181)
    assert not gate.ready(rows(20, retries=1), 360)
    assert gate.ready(rows(20, retries=1), 361)
    assert not gate.ready(rows(30, retries=1, age=61), 400)
    assert not gate.ready(rows(30, retries=1), 500)
    changed = rows(40, retries=1)
    changed[4]['episode_id'] = 'replacement'
    assert not gate.ready(changed, 700)


@pytest.mark.parametrize('initial,maximum', [(5, 10), (10, 60)])
def test_pool_increases_concurrency_without_duplicate_jobs(initial, maximum):
    stop = threading.Event()
    lock = threading.Lock()
    initial_running = threading.Event()
    maximum_running = threading.Event()
    release = threading.Event()
    active = 0
    peak = 0
    seen = []

    def job(entry):
        nonlocal active, peak
        with lock:
            seen.append(entry)
            active += 1
            peak = max(peak, active)
            if active == initial:
                initial_running.set()
            if active == maximum:
                maximum_running.set()
        assert release.wait(5)
        with lock:
            active -= 1

    def poll(entries, limit):
        if initial_running.is_set():
            return maximum
        return limit

    errors = []

    def run():
        try:
            scheduler.run_pool(range(maximum), job, workers=initial, maximum_workers=maximum,
                               stop=stop, poll=poll, poll_seconds=0.01)
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert initial_running.wait(5)
        assert maximum_running.wait(5)
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and not errors
    assert peak == maximum and sorted(seen) == list(range(maximum))


def test_pool_stops_scheduling_and_drains_after_worker_failure():
    stop = threading.Event()
    barrier = threading.Barrier(5)
    seen = []

    def job(entry):
        seen.append(entry)
        barrier.wait(timeout=5)
        if entry == 0:
            raise RuntimeError('provider failed')
        assert stop.wait(5)
        raise scheduler.DrainRequested()

    with pytest.raises(RuntimeError, match='provider failed'):
        scheduler.run_pool(range(20), job, workers=5, maximum_workers=10,
                           stop=stop, poll=lambda entries, limit: limit)
    assert stop.is_set() and sorted(seen) == list(range(5))


def test_stop_request_drains_existing_work_without_starting_more():
    stop = threading.Event()
    seen = []

    def job(entry):
        seen.append(entry)
        assert stop.wait(5)
        raise scheduler.DrainRequested()

    def poll(entries, limit):
        stop.set()
        return limit

    scheduler.run_pool(range(20), job, workers=5, maximum_workers=10, stop=stop, poll=poll)
    assert sorted(seen) == list(range(5))


def test_poll_failure_also_drains_workers():
    stop = threading.Event()

    def job(entry):
        assert stop.wait(5)
        raise scheduler.DrainRequested()

    def poll(entries, limit):
        raise RuntimeError('observer failed')

    with pytest.raises(RuntimeError, match='observer failed'):
        scheduler.run_pool(range(20), job, workers=5, maximum_workers=10, stop=stop, poll=poll)
    assert stop.is_set()


@pytest.mark.parametrize('workers', [5, 60])
def test_frozen_runtime_resume_preserves_accepted_responses_and_exports(tmp_path, workers):
    raw = {'models': ['openai/gpt-6-luna'], 'seeds': [0, 1], 'selfish_counts': [5],
           'game': {'protocol_version': 'rotating-v4', 'players': 6, 'rounds': 2,
                    'backend': 'scripted'}}
    output = tmp_path / 'cohort'

    class Interrupt(ScriptedProvider):
        calls = 0

        def complete(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 4:
                raise ProviderError('fixture interruption')
            return super().complete(*args, **kwargs)

    with pytest.raises(ProviderError):
        run_matrix(raw, output, provider_factory=Interrupt, progress=lambda _: None)
    accepted = {p: p.read_bytes() for p in output.glob('episodes/*/requests/*.json')
                if read_json(p).get('complete')}
    manifest = (output / 'matrix_manifest.json').read_bytes()
    runtime_hashes = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in (output / 'runtime').rglob('*') if p.is_file()}
    command = [sys.executable, str(SCRIPT), '--output', str(output), '--workers', str(workers)]
    run = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    assert read_json(output / 'analysis.json')['completed_episodes'] == 10
    assert read_json(output / 'execution.json')['peak_active_episodes'] == min(workers, 10)
    assert validate_output(output)['status'] == 'valid'
    assert all(p.read_bytes() == data for p, data in accepted.items())
    assert (output / 'matrix_manifest.json').read_bytes() == manifest
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == digest
               for p, digest in runtime_hashes.items())
    records = {p: p.read_bytes() for p in output.glob('episodes/*/requests/*.json')}
    again = subprocess.run(command, capture_output=True, text=True, timeout=60)
    assert again.returncode == 0, again.stderr
    assert all(p.read_bytes() == data for p, data in records.items())


def test_scheduler_refuses_modified_frozen_runtime(tmp_path):
    output = tmp_path / 'cohort'
    raw = {'models': ['openai/gpt-6-luna'], 'communication_modes': ['none'],
           'seeds': [0], 'selfish_counts': [5],
           'game': {'protocol_version': 'rotating-v4', 'players': 6, 'rounds': 1,
                    'backend': 'scripted'}}
    run_matrix(raw, output, progress=lambda _: None)
    path = output / 'runtime/swarm_game/runner.py'
    path.write_text(path.read_text() + '\n# altered frozen code\n')
    run = subprocess.run([sys.executable, str(SCRIPT), '--output', str(output)],
                         capture_output=True, text=True, timeout=30)
    assert run.returncode != 0 and 'provenance differs' in run.stderr
    assert not (output / 'execution.json').exists()
