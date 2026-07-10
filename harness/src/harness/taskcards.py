"""Task card loading and validation.

A task card is the unit of experimental material: it pins a repo SHA, gives
the agent-facing prompt, and carries the formal gold artifacts (constraints,
work item scope) that the metrics are computed against. Validation collects
errors instead of crashing so a whole corpus can be linted in one pass.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

KNOWN_KINDS = {"real", "bait"}
KNOWN_RULE_IDS = {"protected-paths", "no-new-deps", "no-ci-edits", "no-test-deletion"}

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


@dataclass
class TaskCard:
    """A validated task card. `raw` keeps the full YAML dict for metrics code."""

    id: str
    kind: str
    title: str
    base_sha: str
    prompt: str
    constraints: list[str]
    criteria: list[str]
    scope_paths: list[str]
    out_of_scope: list[str]
    honeypots: list[dict[str, str]] = field(default_factory=list)
    rules: list[dict[str, Any]] = field(default_factory=list)
    test_command: str = ""
    deterministic_checks: list[str] = field(default_factory=list)
    # Positive-control cards instruct the agent to perform the tempting
    # out-of-scope work, proving the drift instruments fire. They are
    # excluded from every confirmatory analysis.
    control: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


def _check_str(data: dict, key: str, errors: list[str], required: bool = True) -> None:
    val = data.get(key)
    if val is None:
        if required:
            errors.append(f"missing required field: {key}")
    elif not isinstance(val, str):
        errors.append(f"field {key} must be a string, got {type(val).__name__}")


def _check_str_list(container: Any, key: str, errors: list[str], where: str) -> None:
    val = container.get(key) if isinstance(container, dict) else None
    if val is None:
        errors.append(f"missing required field: {where}.{key}")
        return
    if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
        errors.append(f"field {where}.{key} must be a list of strings")


def validate(data: Any) -> list[str]:
    """Validate a parsed task-card dict. Returns a list of error strings (empty = valid)."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["task card must be a YAML mapping"]

    _check_str(data, "id", errors)
    _check_str(data, "title", errors)
    _check_str(data, "prompt", errors)

    kind = data.get("kind")
    if kind is None:
        errors.append("missing required field: kind")
    elif kind not in KNOWN_KINDS:
        errors.append(f"kind must be one of {sorted(KNOWN_KINDS)}, got {kind!r}")

    sha = data.get("base_sha")
    if sha is None:
        errors.append("missing required field: base_sha")
    elif not isinstance(sha, str) or not _SHA_RE.match(sha):
        errors.append("base_sha must be a 40-character lowercase hex string")

    control = data.get("control")
    if control is not None:
        if not isinstance(control, bool):
            errors.append(f"control must be a boolean, got {type(control).__name__}")
        elif control and kind != "bait":
            errors.append("control: true requires kind: bait (controls are authored)")

    intent = data.get("intent")
    if not isinstance(intent, dict):
        errors.append("missing or invalid required field: intent (must be a mapping)")
    else:
        _check_str_list(intent, "constraints", errors, "intent")
        work_item = intent.get("work_item")
        if not isinstance(work_item, dict):
            errors.append("missing or invalid field: intent.work_item (must be a mapping)")
        else:
            for key in ("criteria", "scope_paths", "out_of_scope"):
                _check_str_list(work_item, key, errors, "intent.work_item")

    honeypots = data.get("honeypots")
    if honeypots is not None:
        if not isinstance(honeypots, list):
            errors.append("honeypots must be a list")
        else:
            for i, hp in enumerate(honeypots):
                if not isinstance(hp, dict) or not isinstance(hp.get("path"), str):
                    errors.append(f"honeypots[{i}] must be a mapping with a string 'path'")

    rules = data.get("rules")
    if rules is not None:
        if not isinstance(rules, list):
            errors.append("rules must be a list")
        else:
            for i, rule in enumerate(rules):
                if not isinstance(rule, dict):
                    errors.append(f"rules[{i}] must be a mapping")
                    continue
                rid = rule.get("id")
                if rid not in KNOWN_RULE_IDS:
                    errors.append(
                        f"rules[{i}].id must be one of {sorted(KNOWN_RULE_IDS)}, got {rid!r}"
                    )
                params = rule.get("params", {})
                if not isinstance(params, dict):
                    errors.append(f"rules[{i}].params must be a mapping")

    outcome = data.get("outcome")
    if outcome is not None:
        if not isinstance(outcome, dict):
            errors.append("outcome must be a mapping")
        else:
            _check_str(outcome, "test_command", errors, required=False)
            checks = outcome.get("deterministic_checks")
            if checks is not None and (
                not isinstance(checks, list) or not all(isinstance(c, str) for c in checks)
            ):
                errors.append("outcome.deterministic_checks must be a list of strings")

    source = data.get("source")
    if kind == "real":
        if not isinstance(source, dict):
            errors.append("kind 'real' requires source with issue_url and ground_truth_pr")
        else:
            for key in ("issue_url", "ground_truth_pr"):
                if not isinstance(source.get(key), str):
                    errors.append(f"kind 'real' requires string source.{key}")
    elif kind == "bait":
        if not isinstance(source, dict) or source.get("authored") is not True:
            errors.append("kind 'bait' requires source.authored: true")

    return errors


def from_dict(data: dict[str, Any]) -> TaskCard:
    """Build a TaskCard from an already-validated dict."""
    intent = data.get("intent") or {}
    work_item = intent.get("work_item") or {}
    outcome = data.get("outcome") or {}
    return TaskCard(
        id=data.get("id", ""),
        kind=data.get("kind", ""),
        title=data.get("title", ""),
        base_sha=data.get("base_sha", ""),
        prompt=data.get("prompt", ""),
        constraints=list(intent.get("constraints") or []),
        criteria=list(work_item.get("criteria") or []),
        scope_paths=list(work_item.get("scope_paths") or []),
        out_of_scope=list(work_item.get("out_of_scope") or []),
        honeypots=list(data.get("honeypots") or []),
        rules=list(data.get("rules") or []),
        test_command=outcome.get("test_command", "") or "",
        deterministic_checks=list(outcome.get("deterministic_checks") or []),
        control=data.get("control") is True,
        raw=data,
    )


def load_task_card(path: Path | str) -> tuple[TaskCard | None, list[str]]:
    """Load one task card file. Returns (card, errors). Card is None when unusable."""
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return None, [f"{path.name}: cannot parse: {exc}"]
    errors = [f"{path.name}: {e}" for e in validate(data)]
    if not isinstance(data, dict):
        return None, errors
    return from_dict(data), errors


def load_all(tasks_dir: Path | str) -> tuple[list[TaskCard], list[str]]:
    """Load every task card in a directory (skips corpus.yaml). Duplicate ids are errors."""
    tasks_dir = Path(tasks_dir)
    cards: list[TaskCard] = []
    errors: list[str] = []
    seen_ids: set[str] = set()
    for path in sorted(tasks_dir.glob("*.yaml")):
        if path.name == "corpus.yaml":
            continue
        card, errs = load_task_card(path)
        errors.extend(errs)
        if card is None:
            continue
        if card.id in seen_ids:
            errors.append(f"{path.name}: duplicate task id {card.id!r}")
            continue
        seen_ids.add(card.id)
        cards.append(card)
    return cards, errors
