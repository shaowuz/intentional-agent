"""Four independent fixtures, at most four generation requests and no retries."""

from dataclasses import replace
from pathlib import Path

from .game import commit_phase, initial_state
from .protocol import make_request
from .providers import ScriptedProvider
from .runner import collect_response
from .storage import provenance, write_json


def run_smoke(provider, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    config = replace(provider.config, communication="public", selfish_count=1, rounds=2)
    state = initial_state(config)
    good = next(p for p in state["players"] if state["roles"][p] == "good")
    selfish = next(p for p in state["players"] if state["roles"][p] == "selfish")
    fixtures = [
        ("good_action", make_request(state, config, good)),
        ("selfish_action", make_request(state, config, selfish)),
    ]
    scripted = ScriptedProvider(replace(config, backend="scripted"))

    def advance():
        import json

        state["pending"] = {
            p: json.loads(scripted.complete(make_request(state, config, p)).content)
            for p in state["players"]
        }
        commit_phase(state, config)

    advance()
    fixtures.append(("public_message", make_request(state, config, good)))
    advance()
    advance()
    fixtures.append(("final_beliefs", make_request(state, config, good)))
    write_json(
        output / "smoke_manifest.json",
        {
            "config": config.to_dict(),
            "provenance": provenance(),
            "purpose": "Independent API fixtures; not an episode",
        },
    )
    results = []
    try:
        catalog = provider.catalog_entry()
        write_json(output / "catalog.json", catalog)
        for name, request in fixtures:
            collect_response(
                request,
                config,
                provider,
                output / "requests" / f"{name}.json",
                correction_attempts=0,
            )
            results.append({"fixture": name, "status": "passed"})
    except Exception as exc:
        write_json(
            output / "smoke_summary.json",
            {"status": "failed", "results": results, "error": str(exc)},
        )
        raise
    from .analysis import usage_totals

    summary = {"status": "passed", "results": results, "usage": usage_totals(output)}
    write_json(output / "smoke_summary.json", summary)
    return summary
