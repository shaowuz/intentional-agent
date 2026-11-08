"""Audited, episode-scoped arithmetic recovery using the unchanged frozen runner."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

TARGETS = (
    "seed-0__openai__gpt-6-luna__selfish-3__selfish_leader",
    "seed-9__openai__gpt-6-luna__selfish-3__opponent",
)
POLICY = "one-additional-arithmetic-only-response-per-rounding-failure/v1"


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def repair_plan(record, config):
    from swarm_game.protocol import Request, validate_response

    if record.get("complete") or record.get("status") != "invalid_response":
        raise ValueError("Expected an incomplete validation failure")
    if len(record.get("attempts", [])) != 2:
        raise ValueError("Only the original two exhausted attempts qualify")
    last = record["attempts"][-1]
    if last.get("validation_error") != "marginal beliefs must imply between 1 and 5 selfish players":
        raise ValueError("Only the frozen marginal-sum failure qualifies")
    if last["response"]["metadata"].get("finish_reason") != "stop":
        raise ValueError("Truncated responses do not qualify")
    request = Request(**record["request"])
    original = json.loads(last["response"]["content"])
    values = {p: Decimal(str(v)) for p, v in original["beliefs"].items()}
    if any(not v.is_finite() or v < 0 or v > 1 or v.quantize(Decimal("0.000001")) != v
           for v in values.values()):
        raise ValueError("Expected finite probabilities with at most six decimal places")
    total = sum(values.values(), Decimal(0))
    boundary = Decimal(5) if total > 5 else Decimal(1)
    excess = total - boundary
    budget = Decimal(len(values)) * Decimal("0.0000005")
    if not Decimal("0.000001") < abs(excess) <= budget:
        raise ValueError("Violation is outside the six-decimal rounding budget")
    candidates = [p for p in sorted(values) if p != request.player
                  and 0 < values[p] < 1 and 0 <= values[p] - excess <= 1]
    if not candidates:
        raise ValueError("No non-self fractional probability can absorb the correction")
    player = candidates[0]
    corrected = values[player] - excess
    expected = copy.deepcopy(original)
    expected["beliefs"][player] = float(corrected)
    validate_response(expected, request, config)
    feedback = (
        "Arithmetic-only correction of decimal rounding. Keep your action (if present), "
        "strategy text, own probability, and every other player probability exactly unchanged. "
        f"Your probabilities sum to {total}; the permitted expected count is between 1 and 5. "
        f"Change only beliefs['{player}'] from {values[player]} to {corrected}. "
        f"This changes the total to exactly {boundary}. Return the full required JSON object "
        "with only that single numeric change. Use the same game information."
    )
    return {"request": request, "expected": expected, "feedback": feedback,
            "old_sum": str(total), "new_sum": str(boundary), "adjusted_player": player,
            "old_value": str(values[player]), "new_value": str(corrected),
            "rounding_budget": str(budget)}


def snapshot_episode(episode):
    from swarm_game.storage import write_json

    recovery = episode / "recovery/rounding-v1"
    recovery.mkdir(parents=True, exist_ok=True)
    index = recovery / "original-sha256.json"
    if index.exists():
        return
    files = [episode / name for name in ("manifest.json", "checkpoint.json", "error.json")]
    files += sorted((episode / "requests").glob("*.json"))
    hashes = {}
    for source in files:
        if not source.exists():
            continue
        relative = source.relative_to(episode)
        destination = recovery / "original" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ValueError("Partial prior snapshot needs inspection")
        shutil.copy2(source, destination)
        destination.chmod(0o444)
        hashes[str(relative)] = hashlib.sha256(source.read_bytes()).hexdigest()
    write_json(index, {"at": now(), "files": hashes})


def repair_request(episode, path, config, provider):
    from swarm_game.protocol import validate_response
    from swarm_game.storage import read_json, write_json

    record = read_json(path)
    plan = repair_plan(record, config)
    folder = episode / "recovery/rounding-v1/corrections" / path.stem
    folder.mkdir(parents=True, exist_ok=False)
    original_bytes = path.read_bytes()
    (folder / "original-request.json").write_bytes(original_bytes)
    (folder / "original-request.json").chmod(0o444)
    old_attempts = copy.deepcopy(record["attempts"])
    receipt = {"status": "started", "started_at": now(), "policy": POLICY,
               "request": path.name, "original_sha256": hashlib.sha256(original_bytes).hexdigest(),
               "prior_attempts": 2, "additional_attempt_limit": 1,
               **{k: v for k, v in plan.items() if k not in ("request", "expected")}}
    write_json(folder / "receipt.json", receipt)
    messages = [*plan["request"].messages,
                {"role": "assistant", "content": record["attempts"][-1]["response"]["content"]},
                {"role": "user", "content": plan["feedback"]}]

    def event(value):
        record["transport_events"].append(value)
        write_json(path, record)

    try:
        record["status"] = "requesting"
        write_json(path, record)
        completion = provider.complete(plan["request"], messages, event)
        attempt = {"messages": messages, "response": completion.to_dict(),
                   "additional_arithmetic_repair": True, "recovery_policy": POLICY}
        record["attempts"].append(attempt)
        try:
            repaired = json.loads(completion.content)
            if completion.metadata.get("finish_reason") != "stop":
                raise ValueError("Arithmetic correction did not finish normally")
            validate_response(repaired, plan["request"], config)
            if repaired != plan["expected"]:
                raise ValueError("Correction changed fields beyond the specified decimal adjustment")
        except (ValueError, TypeError) as exc:
            attempt["validation_error"] = str(exc)
            record["status"] = "invalid_response"
            write_json(path, record)
            raise
        assert record["attempts"][:2] == old_attempts
        record.update(data=repaired, complete=True, status="complete")
        record.pop("error", None)
        write_json(path, record)
        receipt.update(status="complete", finished_at=now(), attempts_after=3)
        write_json(folder / "receipt.json", receipt)
        if (episode / "error.json").exists():
            (episode / "error.json").replace(folder / "episode-error-before-resume.json")
        return receipt
    except Exception as exc:
        receipt.update(status="failed", finished_at=now(), error=str(exc))
        if record.get("status") == "requesting":
            record.update(status="provider_error", error=str(exc))
            write_json(path, record)
        write_json(folder / "receipt.json", receipt)
        raise


def recover(output):
    from swarm_game.config import Config
    from swarm_game.matrix_analysis import analyze_matrix
    from swarm_game.protocol import tokenizer
    from swarm_game.providers import OpenRouterProvider
    from swarm_game.runner import EpisodeError, run_episode
    from swarm_game.storage import exclusive_run, provenance, read_json, scrub, write_json

    root = output / "recovery"
    lock = threading.Lock()
    state = {"status": "running", "pid": os.getpid(), "started_at": now(), "policy": POLICY,
             "scope": list(TARGETS), "runtime_provenance": provenance(),
             "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             "episodes": {name: {"status": "queued"} for name in TARGETS}}

    def update(name, status, **extra):
        with lock:
            state["episodes"][name] = {"status": status, "at": now(), **extra}
            write_json(root / "status.json", state)
            print(name + ": " + status + " " + json.dumps(extra), flush=True)

    def worker(name):
        episode = output / "episodes" / name
        try:
            config = Config(**read_json(episode / "manifest.json")["config"])
            if read_json(episode / "manifest.json")["provenance"] != provenance():
                raise ValueError("Frozen episode provenance changed")
            with exclusive_run(episode, lock_name=".rounding-recovery.lock"):
                while True:
                    with exclusive_run(episode):
                        snapshot_episode(episode)
                        failures = [p for p in (episode / "requests").glob("*.json")
                                    if not read_json(p).get("complete")]
                        if failures:
                            if len(failures) != 1:
                                raise ValueError("Expected exactly one incomplete request")
                            update(name, "arithmetic_correction", request=failures[0].name)
                            provider = OpenRouterProvider(config)
                            try:
                                receipt = repair_request(episode, failures[0], config, provider)
                            finally:
                                provider.close()
                            update(name, "correction_accepted", request=failures[0].name,
                                   corrected_sum=receipt["new_sum"])
                    provider = OpenRouterProvider(config)
                    try:
                        update(name, "resuming")
                        with (root / (name + ".log")).open("a", buffering=1) as log:
                            def progress(message):
                                log.write(now() + " " + message + "\n")
                                update(name, "running", phase=message)
                            run_episode(config, provider, episode, resume=True, progress=progress)
                    except EpisodeError:
                        # Only a new qualifying rounding failure can pass repair_plan next loop.
                        continue
                    finally:
                        provider.close()
                    update(name, "completed")
                    return True
        except Exception as exc:
            update(name, "failed", error=scrub(str(exc)), error_type=type(exc).__name__)
            return False

    with exclusive_run(root, lock_name=".coordinator.lock"):
        tokenizer()
        write_json(root / "status.json", state)
        try:
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="recovery") as pool:
                results = [future.result() for future in as_completed([pool.submit(worker, name) for name in TARGETS])]
            state["status"] = "awaiting_matrix_lock_for_analysis"
            write_json(root / "status.json", state)
            while True:
                try:
                    with exclusive_run(output):
                        # Original coordinator has released ownership; preserve its historical status.
                        parallel = output / "parallel_status.json"
                        if parallel.exists() and not (root / "parallel_status.before-reconciliation.json").exists():
                            shutil.copy2(parallel, root / "parallel_status.before-reconciliation.json")
                        analyze_matrix(output)
                        break
                except ValueError as exc:
                    if str(exc) != "Another process is already using this output directory":
                        raise
                    time.sleep(5)
            state["status"] = "completed" if all(results) else "finished_with_errors"
            state["finished_at"] = now()
            write_json(root / "status.json", state)
            return all(results)
        except BaseException as exc:
            state["status"] = "interrupted_or_failed"
            state["error"] = {"type": type(exc).__name__, "message": scrub(str(exc))}
            state["finished_at"] = now()
            write_json(root / "status.json", state)
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    sys.path.insert(0, str(output / "runtime"))
    import swarm_game
    from dotenv import load_dotenv
    from swarm_game.config import Config
    from swarm_game.storage import read_json, scrub
    if Path(swarm_game.__file__).parent.resolve() != output / "runtime/swarm_game":
        raise ValueError("Expected the original frozen runtime")
    if args.env_file:
        load_dotenv(args.env_file, override=False)
    if not args.execute:
        for name in TARGETS:
            episode = output / "episodes" / name
            config = Config(**read_json(episode / "manifest.json")["config"])
            for path in (episode / "requests").glob("*.json"):
                record = read_json(path)
                if not record.get("complete"):
                    plan = repair_plan(record, config)
                    print(json.dumps({"episode": name, "request": path.name,
                                      **{k: v for k, v in plan.items() if k not in ("request", "expected")}}, indent=2))
        return 0
    guard = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        return 0 if recover(output) else 1
    except Exception as exc:
        print(type(exc).__name__ + ": " + scrub(str(exc)), file=sys.stderr, flush=True)
        return 1
    finally:
        guard.terminate()
        guard.wait()


if __name__ == "__main__":
    raise SystemExit(main())
