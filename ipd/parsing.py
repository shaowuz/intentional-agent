"""Robust parsing of model outputs.

Models are asked to emit single-line JSON, but real models occasionally wrap the
JSON in prose or code fences.  These helpers extract the action / belief value
and report a parse status so that failures are visible in the raw data.
"""

from __future__ import annotations

import json
import re
from typing import Optional, Tuple

_ACTION_WORDS = {
    "c": "C",
    "cooperate": "C",
    "cooperation": "C",
    "coop": "C",
    "d": "D",
    "defect": "D",
    "defection": "D",
    "deceive": "D",
}


def _extract_json_objects(text: str):
    """Yield candidate JSON objects found in ``text`` (best-effort)."""
    # Direct parse.
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            yield json.loads(stripped)
        except json.JSONDecodeError:
            pass
    # Fenced code blocks.
    for block in re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL):
        try:
            yield json.loads(block.strip())
        except json.JSONDecodeError:
            pass
    # Any brace-delimited span (non-greedy), from last to first.
    for match in re.finditer(r"\{.*?\}", text, flags=re.DOTALL):
        try:
            yield json.loads(match.group(0))
        except json.JSONDecodeError:
            continue


def _normalise_action(value) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip().strip('"').lower()
    if s in _ACTION_WORDS:
        return _ACTION_WORDS[s]
    # e.g. "C (Cooperate)" or "action: D"
    if s[:1] in ("c", "d") and len(s) <= 2:
        return s[:1].upper()
    return None


def parse_action(text: str, default: str = "C") -> Tuple[str, dict]:
    """Parse an action from model output.

    Returns ``(action, meta)`` where ``meta`` contains ``reasoning`` and
    ``parse_status`` (``ok`` / ``fallback`` / ``failed``).
    """
    reasoning = ""
    for obj in _extract_json_objects(text):
        if not isinstance(obj, dict):
            continue
        for key in ("action", "Action", "choice", "decision", "move"):
            if key in obj:
                action = _normalise_action(obj[key])
                if action is not None:
                    reasoning = str(
                        obj.get("reasoning", obj.get("explanation", obj.get("rationale", "")))
                    )
                    return action, {"reasoning": reasoning, "parse_status": "ok"}

    # Regex for "action": "C" style fragments.
    m = re.search(
        r'"?(?:action|choice|decision|move)"?\s*[:=]\s*"?\s*(C|D|cooperate|defect|cooperate|defection)\b',
        text,
        flags=re.IGNORECASE,
    )
    if m:
        action = _normalise_action(m.group(1))
        if action is not None:
            return action, {"reasoning": text.strip()[:400], "parse_status": "fallback"}

    # Last resort: look for explicit cooperate/defect tokens, then bare C/D.
    m = re.search(r"\b(cooperate|defect)\b", text, flags=re.IGNORECASE)
    if m:
        action = _normalise_action(m.group(1))
        if action is not None:
            return action, {"reasoning": text.strip()[:400], "parse_status": "fallback"}

    m = re.search(r"\b([CD])\b", text)
    if m:
        return m.group(1), {"reasoning": text.strip()[:400], "parse_status": "fallback"}

    return default, {"reasoning": text.strip()[:400], "parse_status": "failed"}


def parse_belief(text: str) -> Tuple[Optional[float], dict]:
    """Parse a probability in ``[0, 1]`` from model output.

    Returns ``(value, meta)``; ``value`` is ``None`` if nothing could be parsed.
    """
    reasoning = ""
    candidates = []
    for obj in _extract_json_objects(text):
        if not isinstance(obj, dict):
            continue
        for key in (
            "defect_probability",
            "probability",
            "belief",
            "defect_prob",
            "prob",
            "estimate",
        ):
            if key in obj:
                reasoning = str(
                    obj.get("reasoning", obj.get("explanation", ""))
                )
                val = _to_probability(obj[key])
                if val is not None:
                    return val, {"reasoning": reasoning, "parse_status": "ok"}
                candidates.append(obj[key])

    # Percentage form.
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if m:
        val = float(m.group(1)) / 100.0
        return max(0.0, min(1.0, val)), {
            "reasoning": text.strip()[:400],
            "parse_status": "fallback",
        }

    # Any decimal / integer in range.
    for m in re.finditer(r"\b(\d*\.?\d+)\b", text):
        val = _to_probability(m.group(1))
        if val is not None:
            return val, {"reasoning": text.strip()[:400], "parse_status": "fallback"}

    return None, {"reasoning": text.strip()[:400], "parse_status": "failed"}


def _to_probability(value) -> Optional[float]:
    try:
        if isinstance(value, str):
            value = value.strip().rstrip("%")
            if value.endswith("%"):
                value = value[:-1]
            val = float(value)
            # A bare "40" likely means 40%.
            if val > 1.0 and val <= 100.0:
                val = val / 100.0
        else:
            val = float(value)
            if val > 1.0 and val <= 100.0:
                val = val / 100.0
    except (TypeError, ValueError):
        return None
    if 0.0 <= val <= 1.0:
        return val
    return None
