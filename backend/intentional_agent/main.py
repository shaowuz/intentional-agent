"""Local API and experiment coordinator. Start with one Uvicorn worker."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

from .auth import hash_password, token_hash, verify_password
from .engine import advance_round, create_experiment
from .models import ExperimentConfig
from .runtime import DemoRuntime, OpenRouterRuntime
from .sandbox import docker_available
from .storage import Store

PROJECT_ROOT = Path(__file__).resolve().parents[2]
bearer = HTTPBearer(auto_error=False)


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=256)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.lower()


class KeyInput(BaseModel):
    api_key: str = Field(max_length=512)


class ControlInput(BaseModel):
    action: Literal["start", "pause", "step", "stop"]


class ReconcileInput(BaseModel):
    confirmed_cost_usd: float = Field(ge=0, le=100000, allow_inf_nan=False)
    note: str = Field(min_length=3, max_length=1000)


def create_app(data_dir: Path | None = None) -> FastAPI:
    root = Path(data_dir or os.environ.get("IA_DATA_DIR", PROJECT_ROOT / ".data")).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    store = Store(root / "experiments.sqlite3")
    keys: dict[str, str] = {}
    tasks: dict[tuple[str, str], asyncio.Task] = {}
    active: dict[tuple[str, str], dict] = {}
    controls: dict[tuple[str, str], str] = {}
    control_lock = asyncio.Lock()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.recover_interrupted()
        yield
        for identity in list(tasks):
            controls[identity] = "pause"
        if tasks:
            _, pending = await asyncio.wait(list(tasks.values()), timeout=3)
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)
        keys.clear()

    app = FastAPI(title="Intentional Agent", version="0.1.0", lifespan=lifespan)
    app.state.store = store
    app.state.keys = keys
    app.state.tasks = tasks
    app.state.runtime_factory = OpenRouterRuntime
    app.state.demo_factory = DemoRuntime

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Pydantic's default errors echo input, including passwords and API keys.
        safe_errors = [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": safe_errors})

    @app.middleware("http")
    async def local_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
        if not credentials:
            raise HTTPException(401, "Sign in to continue.")
        user = store.session_user(token_hash(credentials.credentials), time.time())
        if not user:
            raise HTTPException(401, "Your session expired. Please sign in again.")
        return user

    def owned(user_id: str, experiment_id: str) -> dict:
        state = active.get((user_id, experiment_id)) or store.get_experiment(user_id, experiment_id)
        if state is None:
            raise HTTPException(404, "Experiment not found.")
        return state

    def new_session(user: dict) -> dict:
        token = secrets.token_urlsafe(40)
        store.add_session(token_hash(token), user["id"], time.time() + 24 * 3600)
        return {"token": token, "user": {"id": user["id"], "username": user["username"]}}

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "docker_available": await asyncio.to_thread(docker_available), "version": "0.1.0"}

    @app.post("/api/auth/register", status_code=201)
    async def register(body: Credentials):
        if os.environ.get("IA_ALLOW_REGISTRATION", "true").lower() != "true":
            raise HTTPException(403, "Account registration is disabled.")
        user = {"id": uuid.uuid4().hex, "username": body.username}
        digest = await asyncio.to_thread(hash_password, body.password)
        try:
            store.create_user(user["id"], user["username"], digest)
        except sqlite3.IntegrityError:
            raise HTTPException(409, "That username is already registered.") from None
        return new_session(user)

    @app.post("/api/auth/login")
    async def login(body: Credentials):
        user = store.find_user(body.username)
        if not user or not await asyncio.to_thread(verify_password, body.password, user["password_hash"]):
            raise HTTPException(401, "Incorrect username or password.")
        return new_session(user)

    @app.get("/api/auth/me")
    async def me(user: dict = Depends(current_user)):
        return user

    @app.post("/api/auth/logout")
    async def logout(user: dict = Depends(current_user), credentials: HTTPAuthorizationCredentials = Depends(bearer)):
        store.delete_session(token_hash(credentials.credentials))
        return {"ok": True}

    @app.get("/api/settings")
    async def settings(user: dict = Depends(current_user)):
        return {"key_configured": bool(keys.get(user["id"]))}

    @app.put("/api/settings/key")
    async def set_key(body: KeyInput, user: dict = Depends(current_user)):
        value = body.api_key.strip()
        if value and (len(value) < 12 or any(char.isspace() for char in value)):
            raise HTTPException(422, "Enter a valid OpenRouter API key.")
        if value:
            keys[user["id"]] = value
        else:
            keys.pop(user["id"], None)
        return {"key_configured": bool(value)}

    @app.get("/api/config/defaults")
    async def defaults(user: dict = Depends(current_user)):
        return ExperimentConfig().model_dump()

    @app.get("/api/models")
    async def models(user: dict = Depends(current_user)):
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get("https://openrouter.ai/api/v1/models")
                response.raise_for_status()
                catalog = response.json()["data"]
            fields = ("id", "name", "context_length", "supported_parameters", "pricing")
            return {"models": [{key: item.get(key) for key in fields} for item in catalog
                               if "tools" in (item.get("supported_parameters") or [])]}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return {"models": [], "error": "The OpenRouter model catalog is unavailable. Enter an explicit tool-capable model ID."}

    @app.get("/api/experiments")
    async def list_runs(user: dict = Depends(current_user)):
        return {"experiments": store.list_experiments(user["id"])}

    @app.post("/api/experiments", status_code=201)
    async def create_run(config: ExperimentConfig, user: dict = Depends(current_user)):
        return store.create_experiment(user["id"], create_experiment(config))

    @app.get("/api/experiments/{experiment_id}")
    async def get_run(experiment_id: str, user: dict = Depends(current_user)):
        return owned(user["id"], experiment_id)

    async def run_worker(owner_id: str, state: dict, single_step: bool, key: str | None):
        identity = (owner_id, state["id"])

        async def checkpoint():
            store.save_experiment(owner_id, state)
            if controls.get(identity):
                raise RuntimeError("Run control requested at a checkpoint.")

        async def persist_runtime():
            # A paid response must reach the engine's action checkpoint before pausing.
            store.save_experiment(owner_id, state)

        runtime = None
        interrupted = False
        try:
            if state["config"]["mode"] == "demo":
                runtime = app.state.demo_factory()
            else:
                runtime = app.state.runtime_factory(api_key=key, workspace_root=root / "workspaces" / owner_id, on_update=persist_runtime)
            while state["status"] == "running":
                if controls.get(identity):
                    break
                await advance_round(state, runtime, on_update=checkpoint)
                store.save_experiment(owner_id, state)
                if single_step or state["status"] in {"paused", "stopped", "completed"}:
                    break
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            interrupted = True
            state["status"] = "paused"
            state["error"] = "Server stopped during a run. Review the last checkpoint before resuming."
        except Exception as exc:
            state["status"] = "paused"
            # Never expose an arbitrary provider exception or researcher key.
            message = str(exc).replace(key, "[redacted]") if key else str(exc)
            state["error"] = message[:600] if isinstance(exc, RuntimeError) else "The run paused after an internal error. Inspect the last recorded event."
        finally:
            requested = controls.pop(identity, None)
            if requested:
                state["status"] = "stopped" if requested == "stop" else ("completed" if state["status"] == "completed" else "paused")
                if not interrupted:
                    state["error"] = None
            elif state["status"] == "running":
                state["status"] = "paused"
            state.pop("control_requested", None)
            store.save_experiment(owner_id, state)
            try:
                if runtime and hasattr(runtime, "aclose"):
                    await runtime.aclose()
            except Exception:
                state["error"] = state.get("error") or "Runtime cleanup did not finish normally. Review local processes before continuing."
                store.save_experiment(owner_id, state)
            finally:
                active.pop(identity, None)
                tasks.pop(identity, None)

    @app.post("/api/experiments/{experiment_id}/control")
    async def control(experiment_id: str, body: ControlInput, user: dict = Depends(current_user)):
        identity = (user["id"], experiment_id)
        async with control_lock:
            state = owned(*identity)
            task = tasks.get(identity)
            if body.action in {"start", "step"}:
                if state["status"] in {"stopped", "completed"}:
                    raise HTTPException(409, "Create a new experiment to run again.")
                if task and not task.done():
                    raise HTTPException(409, "This experiment is already running.")
                key = keys.get(user["id"])
                if state["config"]["mode"] == "openrouter" and not key:
                    raise HTTPException(409, "Configure your OpenRouter API key in API Settings first.")
                state["status"] = "running"
                state["error"] = None
                store.save_experiment(user["id"], state)
                active[identity] = state
                tasks[identity] = asyncio.create_task(run_worker(user["id"], state, body.action == "step", key))
            elif task and not task.done():
                controls[identity] = body.action
                state["control_requested"] = body.action
                store.save_experiment(user["id"], state)
            elif state["status"] not in {"completed", "stopped"}:
                state["status"] = "stopped" if body.action == "stop" else "paused"
                store.save_experiment(user["id"], state)
            return state

    @app.get("/api/experiments/{experiment_id}/export")
    async def export(experiment_id: str, format: Literal["json", "csv"] = "json", user: dict = Depends(current_user)):
        state = owned(user["id"], experiment_id)
        if format == "json":
            output = json.dumps(state, indent=2, ensure_ascii=False, allow_nan=False)
            media = "application/json"
        else:
            buffer = io.StringIO()
            fields = ["round", "a", "b", "action_a", "action_b", "payoff_a", "payoff_b"]
            writer = csv.DictWriter(buffer, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(state["matches"])
            output, media = buffer.getvalue(), "text/csv"
        return Response(output, media_type=media, headers={
            "Content-Disposition": f'attachment; filename="experiment-{experiment_id}.{format}"',
        })

    @app.post("/api/experiments/{experiment_id}/usage/reconcile")
    async def reconcile_usage(experiment_id: str, body: ReconcileInput, user: dict = Depends(current_user)):
        identity = (user["id"], experiment_id)
        async with control_lock:
            state = owned(*identity)
            if state["status"] == "running" or identity in tasks:
                raise HTTPException(409, "Pause the experiment before reconciling usage.")
            usage = state["usage"]
            if not usage.get("unknown_cost_requests"):
                raise HTTPException(409, "There are no unconfirmed charges to reconcile.")
            if body.confirmed_cost_usd < usage.get("cost_usd", 0):
                raise HTTPException(422, "Verified total cannot be lower than already confirmed costs.")
            from .engine import record_event
            record_event(state, "usage_reconciled", {
                "source": "researcher_verification", "researcher_id": user["id"],
                "previous_confirmed_cost_usd": usage.get("cost_usd", 0),
                "previous_unknown_cost_requests": usage["unknown_cost_requests"],
                "confirmed_cost_usd": body.confirmed_cost_usd, "note": body.note,
            })
            usage["cost_usd"] = body.confirmed_cost_usd
            usage["unknown_cost_requests"] = 0
            usage["reserved_usd"] = 0
            store.save_experiment(user["id"], state)
            return state

    @app.get("/{path:path}")
    async def frontend(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Endpoint not found.")
        dist = PROJECT_ROOT / "frontend" / "dist"
        candidate = (dist / path).resolve()
        if dist.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        if (dist / "index.html").is_file():
            return FileResponse(dist / "index.html")
        return Response("Intentional Agent API is running. Build the frontend with npm run build in frontend/ or use the Vite development server.", media_type="text/plain")

    return app


app = create_app()
