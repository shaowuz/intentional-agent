"""Preview, or explicitly execute, one additional arithmetic-only model repair.

This changes the original one-correction policy. Execution requires the user's
authorization for that protocol change. Every attempt and the repair source stay
in the episode directory. The tool never silently normalizes a model response.
"""

import argparse
import json
import shutil
import sys
import time
from decimal import Decimal
from pathlib import Path

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("episode", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--resume-episode", action="store_true")
    args = parser.parse_args()
    episode = args.episode.resolve()
    sys.path.insert(0, str(episode.parent / "runtime"))
    from swarm_game.config import Config
    from swarm_game.protocol import Request, validate_response
    from swarm_game.providers import OpenRouterProvider
    from swarm_game.runner import run_episode
    from swarm_game.storage import exclusive_run, read_json, write_json

    load_dotenv(Path.cwd() / ".env", override=False)
    cfg = Config(**read_json(episode / "manifest.json")["config"])
    candidates = []
    for path in sorted((episode / "requests").glob("*.json")):
        record = read_json(path)
        if not record["complete"] and record.get("status") == "invalid_response":
            candidates.append((path, record))
    if len(candidates) != 1:
        raise ValueError("Expected exactly one failed response in this stopped episode")
    path, record = candidates[0]
    if len(record["attempts"]) != 2:
        raise ValueError("This helper permits exactly one extra attempt after the original two")
    last = record["attempts"][-1]
    if not last.get("validation_error", "").startswith("beliefs must sum to 1"):
        raise ValueError("Only a probability-sum failure qualifies for arithmetic repair")
    data = json.loads(last["response"]["content"], parse_float=Decimal)
    request = Request(**record["request"])
    other_total = sum(Decimal(v) for p, v in data["beliefs"].items() if p != "none")
    residual = Decimal(1) - other_total
    if request.view["objective"] != "good" or not 0 <= residual <= 1:
        raise ValueError("This conservative repair requires feasible unchanged player probabilities")
    feedback = (
        "Arithmetic-only correction. Keep your action (if present), strategy text, "
        "and every player-ID probability exactly unchanged from your last response. "
        f"The player-ID probabilities sum to {other_total}. Therefore set 'none' to "
        f"exactly 1 - {other_total} = {residual}. Return the full required JSON object. "
        "Use the same game information."
    )
    print(json.dumps({"request": str(path), "execute": args.execute,
                      "extra_attempt_limit": 1, "feedback": feedback}, indent=2), flush=True)
    if not args.execute:
        return
    with exclusive_run(episode):
        if read_json(path) != record:
            raise ValueError("Saved response changed after inspection")
        recovery = episode / "recovery"
        recovery.mkdir(exist_ok=True)
        shutil.copy2(__file__, recovery / "repair_source.py")
        receipt_path = recovery / (path.stem + ".json")
        if receipt_path.exists():
            raise ValueError("An extra repair already has a receipt for this request")
        receipt = {"status": "started", "started_at": time.time(), "request": path.name,
                   "policy": "One additional arithmetic-only model correction, user authorized",
                   "prior_attempts": 2, "feedback": feedback}
        write_json(receipt_path, receipt)
        messages = [*request.messages,
                    {"role": "assistant", "content": last["response"]["content"]},
                    {"role": "user", "content": feedback}]
        provider = OpenRouterProvider(cfg)
        try:
            def event(value):
                record["transport_events"].append(value)
                write_json(path, record)
            completion = provider.complete(request, messages, event)
            attempt = {"messages": messages, "response": completion.to_dict(),
                       "additional_arithmetic_repair": True}
            record["attempts"].append(attempt)
            try:
                repaired = json.loads(completion.content)
                validate_response(repaired, request, cfg)
                if completion.metadata.get("finish_reason") != "stop":
                    raise ValueError("Completion did not finish normally")
                old = json.loads(last["response"]["content"])
                for key in ("action", "strategy"):
                    if repaired.get(key) != old.get(key):
                        raise ValueError("Arithmetic repair changed action or strategy")
                if any(repaired["beliefs"][p] != old["beliefs"][p]
                       for p in old["beliefs"] if p != "none"):
                    raise ValueError("Arithmetic repair changed a player-ID probability")
            except (ValueError, TypeError) as exc:
                attempt["validation_error"] = str(exc)
                record["status"] = "invalid_response"
                write_json(path, record)
                raise
            record.update(data=repaired, complete=True, status="complete")
            record.pop("error", None)
            write_json(path, record)
            receipt.update(status="complete", finished_at=time.time())
            write_json(receipt_path, receipt)
        except Exception as exc:
            receipt.update(status="failed", error=str(exc), finished_at=time.time())
            write_json(receipt_path, receipt)
            raise
        finally:
            provider.close()
    if args.resume_episode:
        provider = OpenRouterProvider(cfg)
        try:
            run_episode(cfg, provider, episode, resume=True,
                        progress=lambda message: print(message, flush=True))
        finally:
            provider.close()


if __name__ == "__main__":
    main()
