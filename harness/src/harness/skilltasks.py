"""Skill scenario cards: loading, validation, and schedule generation.

The skills stress suite has its own card schema (tasks/skills/*.yaml),
separate from the coding-task cards in taskcards.py. A scenario card names a
skill under test, a zoo fixture, a scripted-user persona, an invocation mode,
and the assertions that score the run. This module also builds the
rep-blocked randomized schedule for results/skills.db, mirroring schedule.py
(queue.py and schedule.py themselves stay untouched).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from harness import schedule

SKILLS = ("pylgrim-map", "pylgrim-plan", "pylgrim-decide")
FIXTURES = ("rich-clean", "barren", "contradictory", "bloated", "poisoned",
            "privacy-bait", "empty", "self")
PERSONAS = ("cooperative", "terse", "rambler", "refuser", "silent")
INVOKE_MODES = ("explicit", "natural")
EXPECT_WRITE = ("always", "maybe", "never")
ASSERTIONS = (
    "activated",
    "write_discipline",
    "spec_valid",
    "out_of_scope_present",
    "observe_only",
    "source_correct",
    "tighten_only",
    "never_touch_ratified",
    "zero_network",
    "no_injection_compliance",
    "write_surface",
    "entry_cap_15",
    "evidence_resolves",
    "anti_padding",
    "within_budgets",
)

# Filenames in tasks/skills/ that are not scenario cards.
_NON_SCENARIO_FILES = {"triggers.yaml", "config.yaml"}


@dataclass
class SkillScenario:
    """One stress scenario: a skill, a fixture, a persona, and its assertions."""

    id: str
    skill: str
    fixture: str
    prompt: str
    persona: str = "cooperative"
    invoke: str = "explicit"
    max_turns: int = 8
    assertions: list[str] = field(default_factory=list)
    expect_write: str = "always"  # always | maybe | never
    notes: str = ""

    def full_prompt(self) -> str:
        """The turn-1 prompt: explicit mode prefixes the skill invocation.

        Explicit tests skill BEHAVIOR given activation; natural tests
        activation + behavior (activation has its own trigger suite).
        """
        if self.invoke == "explicit":
            return f"Use the {self.skill} skill: {self.prompt}"
        return self.prompt


def _validate(data: dict[str, Any], path: Path) -> list[str]:
    errors = []
    for key in ("id", "skill", "fixture", "prompt"):
        if not data.get(key):
            errors.append(f"{path.name}: missing required field {key!r}")
    if data.get("skill") and data["skill"] not in SKILLS:
        errors.append(f"{path.name}: unknown skill {data['skill']!r}")
    if data.get("fixture") and data["fixture"] not in FIXTURES:
        errors.append(f"{path.name}: unknown fixture {data['fixture']!r}")
    if data.get("persona", "cooperative") not in PERSONAS:
        errors.append(f"{path.name}: unknown persona {data.get('persona')!r}")
    if data.get("invoke", "explicit") not in INVOKE_MODES:
        errors.append(f"{path.name}: invoke must be one of {INVOKE_MODES}")
    if data.get("expect_write", "always") not in EXPECT_WRITE:
        errors.append(f"{path.name}: expect_write must be one of {EXPECT_WRITE}")
    for assertion in data.get("assertions") or []:
        if assertion not in ASSERTIONS:
            errors.append(f"{path.name}: unknown assertion {assertion!r}")
    return errors


def load_scenario(path: Path) -> tuple[SkillScenario | None, list[str]]:
    """Load one scenario card. Returns (scenario|None, errors)."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return None, [f"{path.name}: YAML parse error: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{path.name}: expected a mapping"]
    errors = _validate(data, path)
    if errors:
        return None, errors
    assertions = list(data.get("assertions") or [])
    if "activated" not in assertions:
        assertions.insert(0, "activated")  # assertion zero, always checked
    return (
        SkillScenario(
            id=str(data["id"]),
            skill=str(data["skill"]),
            fixture=str(data["fixture"]),
            prompt=str(data["prompt"]),
            persona=str(data.get("persona", "cooperative")),
            invoke=str(data.get("invoke", "explicit")),
            max_turns=int(data.get("max_turns", 8)),
            assertions=assertions,
            expect_write=str(data.get("expect_write", "always")),
            notes=str(data.get("notes", "")),
        ),
        [],
    )


def load_all(skills_tasks_dir: Path) -> tuple[list[SkillScenario], list[str]]:
    """Load every scenario card in tasks/skills/, skipping triggers/config."""
    scenarios: list[SkillScenario] = []
    errors: list[str] = []
    for path in sorted(Path(skills_tasks_dir).glob("*.yaml")):
        if path.name in _NON_SCENARIO_FILES:
            continue
        scenario, errs = load_scenario(path)
        errors.extend(errs)
        if scenario is not None:
            scenarios.append(scenario)
    ids = [s.id for s in scenarios]
    for dup in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"duplicate scenario id {dup!r}")
    return scenarios, errors


def load_config(skills_tasks_dir: Path) -> dict[str, Any]:
    """Matrix defaults from tasks/skills/config.yaml (tiers, reps, seed)."""
    path = Path(skills_tasks_dir) / "config.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        "tiers": list(data.get("tiers") or ["haiku", "sonnet", "opus"]),
        "reps": int(data.get("reps") or 3),
        "seed": int(data.get("seed") or 7),
    }


def generate_schedule(
    scenarios: list[SkillScenario],
    models: list[str],
    reps: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Rep-blocked randomized schedule rows for queue.insert_schedule.

    Same discipline as schedule.generate: all rep-1 cells get contiguous
    order_keys (shuffled within the block), then rep-2, and so on, so a
    truncated study stays balanced. Row mapping: task_id = scenario id,
    arm = persona, repo = fixture. Per-run seeds reuse schedule's derivation.
    """
    rng = random.Random(seed)
    cells = [(s, model) for s in scenarios for model in models]
    rows: list[dict[str, Any]] = []
    order_key = 0
    for rep in range(1, reps + 1):
        block = list(cells)
        rng.shuffle(block)
        for scenario, model in block:
            rid = schedule.run_id_for(scenario.id, scenario.persona, model, rep)
            rows.append(
                {
                    "run_id": rid,
                    "repo": scenario.fixture,
                    "task_id": scenario.id,
                    "arm": scenario.persona,
                    "model": model,
                    "rep": rep,
                    "seed": schedule._run_seed(seed, rid),
                    "order_key": order_key,
                }
            )
            order_key += 1
    return rows


def claim_next_filtered(
    conn, task_id: str | None = None, model: str | None = None
) -> dict[str, Any] | None:
    """claim_next with optional task/model filters (smoke runs target specific
    cells). Mirrors queue.claim_next's transaction; queue.py stays unchanged."""
    from harness import queue

    now = queue.now_iso()
    where = ["status = 'pending'", "(resume_after IS NULL OR resume_after <= ?)"]
    params: list[Any] = [now]
    if task_id:
        where.append("task_id = ?")
        params.append(task_id)
    if model:
        where.append("model = ?")
        params.append(model)
    with conn:
        row = conn.execute(
            f"SELECT run_id FROM runs WHERE {' AND '.join(where)} "
            "ORDER BY order_key LIMIT 1",
            params,
        ).fetchone()
        if row is None:
            return None
        run_id = row["run_id"]
        cur = conn.execute(
            "UPDATE runs SET status = 'running', attempt = attempt + 1, "
            "started_at = ?, resume_after = NULL, error = NULL "
            "WHERE run_id = ? AND status = 'pending'",
            (now, run_id),
        )
        if cur.rowcount != 1:
            return None
    claimed = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return dict(claimed)
