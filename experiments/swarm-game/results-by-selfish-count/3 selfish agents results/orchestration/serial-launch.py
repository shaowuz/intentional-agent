"""Persistent, single-cohort launcher; never records credentials."""
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from dotenv import dotenv_values

record = Path(__file__).resolve().parent
receipt_path = record / "launch.json"
receipt = json.loads(receipt_path.read_text())
root = Path(receipt["checkout"])


def save():
    temporary = receipt_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(receipt, indent=2) + "\n")
    temporary.replace(receipt_path)


environment = os.environ.copy()
if len(sys.argv) == 2:
    credential_file = Path(sys.argv[1]).expanduser().resolve(strict=True)
    configured = dotenv_values(credential_file)
    if not environment.get("OPENROUTER_API_KEY"):
        environment["OPENROUTER_API_KEY"] = configured.get("OPENROUTER_API_KEY") or ""
    receipt["credential_source"] = str(credential_file)
if not environment.get("OPENROUTER_API_KEY"):
    raise SystemExit("OPENROUTER_API_KEY is not configured; no cohort was launched.")
environment["PYTHONUNBUFFERED"] = "1"

assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() == receipt["source_commit"]
assert not subprocess.check_output(["git", "diff", "HEAD", "--name-only"], cwd=root, text=True).strip()
for relative, field in (("configs/computer-2-luna.json", "config_sha256"), ("uv.lock", "uv_lock_sha256")):
    assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == receipt[field]
assert not Path(receipt["output"]).exists(), "Inspect existing output and resume with saved spec.json."

receipt["session_supervisor_pid"] = os.getpid()
receipt["started_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
with Path(receipt["log"]).open("a", buffering=1) as log:
    log.write("Launching computer 2 Luna cohort at source " + receipt["source_commit"] + "\n")
    process = subprocess.Popen(receipt["execute_command"], cwd=root, env=environment,
                               stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
    receipt["uv_pid"] = process.pid
    receipt["status"] = "starting"
    save()
    sleep_guard = subprocess.Popen(["/usr/bin/caffeinate", "-i", "-w", str(process.pid)],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)
    receipt["sleep_guard_pid"] = sleep_guard.pid
    save()
    return_code = process.wait()
    sleep_guard.wait()
    receipt = json.loads(receipt_path.read_text())
    receipt["return_code"] = return_code
    receipt["finished_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt["status"] = "completed" if return_code == 0 else "interrupted_or_failed"
    save()
    log.write("Runner exit code: " + str(return_code) + "\n")
raise SystemExit(return_code)
