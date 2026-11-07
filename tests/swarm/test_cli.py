import json

from swarm_game.cli import main
from swarm_game.storage import read_json


def test_pilot_preview_has_no_network_or_run_directory(tmp_path, capsys):
    output = tmp_path / "pilot"
    assert main(["pilot", "--output", str(output)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["episodes"] == 48
    assert result["requests_before_retries"] == 11520
    assert not output.exists()


def test_cli_compare_resume_analyze(tmp_path, capsys):
    output = tmp_path / "comparison"
    args = [
        "compare",
        "--backend",
        "scripted",
        "--players",
        "4",
        "--rounds",
        "2",
        "--output",
        str(output),
    ]
    assert main(args) == 0
    assert read_json(output / "comparison.json")["episodes"] == 4
    assert main([*args, "--resume"]) == 0
    assert main(["analyze", str(output)]) == 0
    assert main(["resume", str(next(output.glob("*/manifest.json")).parent)]) == 0


def test_public_persona_pilot(tmp_path, capsys):
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({
        "game": {"backend": "scripted", "rounds": 2, "selfish_persona": "trump_like"},
        "seeds": 1, "communication_modes": ["public"],
    }))
    output = tmp_path / "public"
    args = ["pilot", "--config", str(spec), "--output", str(output)]
    assert main(args) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["episodes"] == 2 and preview["selfish_persona"] == "trump_like"
    assert not output.exists()
    assert main([*args, "--execute"]) == 0
    result = read_json(output / "comparison.json")
    assert result["episodes"] == 2 and result["missing_pairs"] == []
    for path in output.glob("*/manifest.json"):
        config = read_json(path)["config"]
        assert config["communication"] == "public" and config["selfish_persona"] == "trump_like"
    assert main([*args, "--execute", "--resume"]) == 0
