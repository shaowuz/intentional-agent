"""Run saved matrix episodes concurrently without changing the frozen protocol."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def run_parallel(output, workers=60, *, progress=print, provider_factory=None):
    from swarm_game.config import Config
    from swarm_game.matrix import SCHEMA_VERSION, episode_plan, make_provider, normalize_spec, preview
    from swarm_game.matrix_analysis import analyze_matrix
    from swarm_game.protocol import tokenizer
    from swarm_game.runner import run_episode
    from swarm_game.storage import exclusive_run, provenance, read_json, scrub, write_json

    output = Path(output).resolve()
    spec = normalize_spec(read_json(output / "spec.json"))
    manifest = read_json(output / "matrix_manifest.json")
    expected = {
        "schema_version": SCHEMA_VERSION, "spec": spec, "plan": episode_plan(spec),
        "provenance": provenance(), "counts": preview(spec),
    }
    if expected != manifest:
        raise ValueError("Saved specification or frozen runtime provenance does not match")
    if not 1 <= workers <= len(manifest["plan"]):
        raise ValueError("Worker count must be between one and the planned episode count")
    provider_factory = provider_factory or make_provider
    state_lock = threading.Lock()
    states = {entry["episode_id"]: {"status": "queued"} for entry in manifest["plan"]}
    state = {
        "status": "running", "pid": os.getpid(), "workers": workers,
        "started_at": utc_now(), "runtime_provenance": provenance(), "episodes": states,
        "orchestration_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "execution_order": "concurrent episode dispatch in saved manifest order",
    }

    def update(name, status, **extra):
        with state_lock:
            states[name] = {"status": status, "updated_at": utc_now(), **extra}
            write_json(output / "parallel_status.json", state)

    def emit(message):
        with state_lock:
            progress(message)

    def worker(entry):
        name = entry["episode_id"]
        episode = output / "episodes" / name
        provider = None
        update(name, "running")
        try:
            config = Config(**entry["config"])
            provider = provider_factory(config)
            with (output / "parallel-logs" / (name + ".log")).open("a", buffering=1) as log:
                def phase(message):
                    log.write(utc_now() + " " + message + "\n")
                    emit(name + ": " + message)

                run_episode(config, provider, episode, resume=episode.exists(), progress=phase)
            update(name, "completed")
            emit(name + ": completed")
            return True
        except Exception as exc:
            error = {"type": type(exc).__name__, "error": scrub(str(exc)), "at": utc_now()}
            write_json(output / "parallel-logs" / (name + ".error.json"), error)
            update(name, "failed", **error)
            emit(name + ": FAILED " + error["type"] + ": " + error["error"])
            return False
        finally:
            if provider is not None and hasattr(provider, "close"):
                provider.close()

    with exclusive_run(output):
        tokenizer()
        (output / "parallel-logs").mkdir(exist_ok=True)
        write_json(output / "parallel_status.json", state)
        try:
            if spec["game"]["backend"] == "openrouter":
                catalog = []
                for model in spec["models"]:
                    provider = provider_factory(Config(**spec["game"], model=model,
                                                       selfish_count=spec["selfish_counts"][0]))
                    try:
                        catalog.append(provider.catalog_entry())
                    finally:
                        provider.close()
                write_json(output / "parallel_catalog.json", catalog)
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="episode") as pool:
                futures = [pool.submit(worker, entry) for entry in manifest["plan"]]
                results = [future.result() for future in as_completed(futures)]
            analyze_matrix(output)
            state["status"] = "completed" if all(results) else "finished_with_errors"
            state["finished_at"] = utc_now()
            write_json(output / "parallel_status.json", state)
            return state
        except BaseException as exc:
            state["status"] = "interrupted_or_failed"
            state["error"] = {"type": type(exc).__name__, "message": scrub(str(exc))}
            state["finished_at"] = utc_now()
            write_json(output / "parallel_status.json", state)
            raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=60)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--execute", action="store_true", required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    sys.path.insert(0, str(output / "runtime"))
    import swarm_game
    from dotenv import load_dotenv
    from swarm_game.storage import scrub

    if Path(swarm_game.__file__).parent.resolve() != output / "runtime/swarm_game":
        raise RuntimeError("The saved frozen runtime was not loaded")
    if args.env_file:
        load_dotenv(args.env_file, override=False)
    guard = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(os.getpid())],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
    try:
        result = run_parallel(output, args.workers, progress=lambda message: print(message, flush=True))
        return 0 if result["status"] == "completed" else 1
    except Exception as exc:
        print(type(exc).__name__ + ": " + scrub(str(exc)), file=sys.stderr, flush=True)
        return 1
    finally:
        guard.terminate()
        guard.wait()


if __name__ == "__main__":
    raise SystemExit(main())
