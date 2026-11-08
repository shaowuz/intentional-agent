"""Strict validation and parsing of structured LLM outputs.

The experiment requires structured outputs.  For a decision we accept only a
JSON object with an ``action`` field whose value is one of ``C``/``D``.  For a
reflection we require ``change_strategy`` (boolean), ``reason`` (string) and
``strategy_for_next_round`` (non-empty string).  Prose fallbacks are *not*
accepted for the main run: the agent retries the model instead, and the raw
malformed response is recorded.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterator, Optional, Tuple

_ACTION_WORDS = {
    "c": "C",
    "cooperate": "C",
    "cooperation": "C",
    "coop": "C",
    "d": "D",
    "defect": "D",
    "defection": "D",
}


def extract_json_objects(text: str) -> Iterator[dict]:
    """Yield candidate JSON objects found in ``text`` (best effort)."""
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict):
                yield obj
        except json.JSONDecodeError:
            pass
    for block in re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL):
        try:
            obj = json.loads(block.strip())
            if isinstance(obj, dict):
                yield obj
        except json.JSONDecodeError:
            pass
    for match in re.finditer(r"\{.*?\}", text, flags=re.DOTALL):
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                yield obj
        except json.JSONDecodeError:
            continue


def normalise_action(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().strip('"').lower()
    if text in _ACTION_WORDS:
        return _ACTION_WORDS[text]
    if text in ("c", "d"):
        return text.upper()
    return None


def parse_action_strict(text: str) -> Tuple[Optional[str], dict]:
    """Parse a strictly structured action.

    Returns ``(action, meta)``.  ``action`` is ``None`` unless a JSON object
    containing a valid action field was found.
    """
    for obj in extract_json_objects(text):
        for key in ("action", "Action", "choice", "decision", "move"):
            if key in obj:
                action = normalise_action(obj[key])
                if action is not None:
                    reasoning = obj.get(
                        "reasoning",
                        obj.get("explanation", obj.get("rationale", "")),
                    )
                    return action, {
                        "reasoning": str(reasoning),
                        "parse_status": "ok",
                        "parsed_object": obj,
                    }
    return None, {
        "reasoning": "",
        "parse_status": "failed",
        "raw_response": text[:1000],
    }


def _coerce_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in ("true", "yes", "y", "1"):
            return True
        if text in ("false", "no", "n", "0"):
            return False
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    return None


def parse_reflection_strict(text: str) -> Tuple[Optional[dict], dict]:
    """Parse and validate a structured strategy reflection."""
    for obj in extract_json_objects(text):
        if "change_strategy" not in obj:
            continue
        change = _coerce_bool(obj.get("change_strategy"))
        if change is None:
            continue
        reason = obj.get("reason", obj.get("explanation", ""))
        strategy = obj.get(
            "strategy_for_next_round",
            obj.get("strategy", obj.get("next_strategy", "")),
        )
        if not isinstance(reason, str) or not isinstance(strategy, str):
            continue
        if not strategy.strip():
            continue
        return {
            "change_strategy": change,
            "reason": reason.strip(),
            "strategy_for_next_round": strategy.strip(),
            "parse_status": "ok",
        }, {"parse_status": "ok"}
    return None, {
        "parse_status": "failed",
        "raw_response": text[:1000],
    }
