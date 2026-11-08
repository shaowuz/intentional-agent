import json
from pathlib import Path

from .config import Config
from .game import commit_phase, initial_state
from .protocol import make_request, validate_response
from .storage import code_hash, exclusive_run, provenance, read_json, write_json


class EpisodeError(RuntimeError):
    pass


def collect_response(request, config, provider, path, *, correction_attempts=1):
    """Save accepted responses before updating game state, making resume idempotent."""
    path = Path(path)
    record = (
        read_json(path)
        if path.exists()
        else {
            "request": request.to_dict(),
            "attempts": [],
            "transport_events": [],
            "complete": False,
        }
    )
    if record["request"] != request.to_dict():
        raise EpisodeError("Saved request differs from reconstructed player view")
    if record["complete"]:
        return validate_response(record["data"], request, config)

    def on_event(event):
        record["transport_events"].append(event)
        write_json(path, record)

    while len(record["attempts"]) < correction_attempts + 1:
        messages = list(request.messages)
        if record["attempts"]:
            last = record["attempts"][-1]
            messages += [
                {"role": "assistant", "content": last["response"]["content"]},
                {
                    "role": "user",
                    "content": "Correct the output format only. "
                    + last["validation_error"]
                    + ". Use the same game information.",
                },
            ]
        record["status"] = "requesting"
        write_json(path, record)
        try:
            completion = provider.complete(request, messages, on_event)
        except Exception as exc:
            record["status"] = "provider_error"
            record["error"] = str(exc)
            write_json(path, record)
            raise
        attempt = {"messages": messages, "response": completion.to_dict()}
        record["attempts"].append(attempt)
        try:
            data = json.loads(completion.content)
            if completion.metadata.get("finish_reason") not in (None, "stop"):
                raise ValueError("Completion did not finish normally")
            validate_response(data, request, config)
        except (ValueError, TypeError) as exc:
            attempt["validation_error"] = str(exc)
            record["status"] = "invalid_response"
            write_json(path, record)
            continue
        record.update(data=data, complete=True, status="complete")
        record.pop("error", None)
        write_json(path, record)
        return data
    raise EpisodeError(
        f"Invalid response after {len(record['attempts'])} attempts: "
        f"{request.player} round {request.round} {request.phase}"
    )


def run_episode(config, provider, output, *, resume=False, progress=lambda text: None):
    output = Path(output)
    if not resume:
        output.mkdir(parents=True, exist_ok=False)
    elif not (output / "manifest.json").is_file():
        raise ValueError("Resume requires an existing episode manifest")
    with exclusive_run(output):
        if resume:
            manifest = read_json(output / "manifest.json")
            if manifest["config"] != config.to_dict():
                raise ValueError("Resume configuration differs from the saved episode")
            if manifest["provenance"]["code_sha256"] != code_hash():
                raise ValueError(
                    "Runner code changed; use the original version to resume this episode"
                )
            state = read_json(output / "checkpoint.json")
        else:
            manifest = {"config": config.to_dict(), "provenance": provenance()}
            write_json(output / "manifest.json", manifest)
            state = initial_state(config)
            write_json(output / "checkpoint.json", state)
        try:
            while not state["completed"]:
                progress(f"round {state['round']}/{config.rounds}: {state['phase']}")
                for player in state["players"]:
                    if player in state["pending"]:
                        continue
                    request = make_request(state, config, player)
                    call_id = f"{state['round']:04d}-{state['phase']}-{player}"
                    response = collect_response(
                        request, config, provider, output / "requests" / f"{call_id}.json"
                    )
                    state["pending"][player] = response
                    write_json(output / "checkpoint.json", state)
                commit_phase(state, config)
                write_json(output / "checkpoint.json", state)
        except Exception as exc:
            write_json(
                output / "error.json",
                {
                    "type": type(exc).__name__,
                    "error": str(exc),
                    "round": state["round"],
                    "phase": state["phase"],
                },
            )
            raise
        error_path = output / "error.json"
        if error_path.exists():
            error_path.unlink()
        from .analysis import analyze_episode

        return analyze_episode(output)


def load_config(output):
    return Config(**read_json(Path(output) / "manifest.json")["config"])
