"""Trigger testing: do the skills activate when they should, and only then?

Each of the 36 probes in tasks/skills/triggers.yaml runs as a single fresh
`claude -p` in a rich-clean workspace with all three skills installed but the
prompt left completely natural (no explicit invocation). The activation
signal, verified live: a tool_use named "Skill" whose input carries
{"skill": "<name>"}. should-trigger prompts score hit rate; should-not
prompts score false-fire rate (weighted worse in the report). Results land
one JSON per probe under results/triggers/, so an interrupted sweep resumes
by skipping completed probes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

from harness import headless
from harness import transcripts as transcripts_mod
from harness.skill_runner import install_skills, prepare_workspace, pylgrim_repo_sha
from harness.skill_runner import DEFAULT_SKILLS_SOURCE

PYLGRIM_SKILLS = ("pylgrim-map", "pylgrim-plan", "pylgrim-decide")
TRIGGER_FIXTURE = "rich-clean"
DEFAULT_TRIGGER_TIMEOUT_S = 10 * 60


@dataclass
class TriggerProbe:
    """One trigger prompt with its expectation for one skill."""

    id: str
    skill: str
    expect: str  # should | should_not
    prompt: str


def load_triggers(path: Path) -> tuple[list[TriggerProbe], list[str]]:
    """Load triggers.yaml; validates ids, skills, and expectations."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    probes: list[TriggerProbe] = []
    errors: list[str] = []
    for item in data.get("prompts") or []:
        if not isinstance(item, dict):
            errors.append(f"not a mapping: {item!r}")
            continue
        probe = TriggerProbe(
            id=str(item.get("id", "")),
            skill=str(item.get("skill", "")),
            expect=str(item.get("expect", "")),
            prompt=str(item.get("prompt", "")),
        )
        if not probe.id or not probe.prompt:
            errors.append(f"probe missing id or prompt: {item!r}")
            continue
        if probe.skill not in PYLGRIM_SKILLS:
            errors.append(f"{probe.id}: unknown skill {probe.skill!r}")
            continue
        if probe.expect not in ("should", "should_not"):
            errors.append(f"{probe.id}: expect must be should|should_not")
            continue
        probes.append(probe)
    ids = [p.id for p in probes]
    for dup in {i for i in ids if ids.count(i) > 1}:
        errors.append(f"duplicate trigger id {dup!r}")
    return probes, errors


def activated_skills(events: Iterable[dict[str, Any]]) -> list[str]:
    """Every pylgrim skill the transcript activated via the Skill tool."""
    fired: list[str] = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        content = (event.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use" \
                    and block.get("name") == "Skill":
                skill = str((block.get("input") or {}).get("skill") or "")
                if skill in PYLGRIM_SKILLS and skill not in fired:
                    fired.append(skill)
    return fired


def detect_activation(events: Iterable[dict[str, Any]], skill_name: str) -> bool:
    """The verified activation signal: Skill tool_use with input.skill == name."""
    return skill_name in activated_skills(events)


def probe_dir(results_dir: Path, probe_id: str) -> Path:
    return Path(results_dir) / "triggers" / probe_id


def is_done(results_dir: Path, probe_id: str) -> bool:
    return (probe_dir(results_dir, probe_id) / "result.json").exists()


def run_probe(
    probe: TriggerProbe,
    results_dir: Path | str,
    zoo_dir: Path | str | None = None,
    model: str = "haiku",
    skills_source: Path = DEFAULT_SKILLS_SOURCE,
    timeout_s: int = DEFAULT_TRIGGER_TIMEOUT_S,
) -> dict[str, Any]:
    """One single-shot probe run. Raises headless.RateLimited on rate limits."""
    results_dir = Path(results_dir)
    zoo_dir = Path(zoo_dir) if zoo_dir else results_dir / "zoo"
    out_dir = probe_dir(results_dir, probe.id)
    out_dir.mkdir(parents=True, exist_ok=True)
    workspace = out_dir / "workspace"

    prepare_workspace(TRIGGER_FIXTURE, zoo_dir, workspace)
    install_skills(workspace, skills_source)

    cli_result = headless.invoke_claude(probe.prompt, model, workspace, timeout_s)
    session_id = cli_result.get("session_id") or ""
    transcript = headless.copy_transcript(workspace, session_id,
                                          out_dir / "transcript.jsonl")
    fired = (activated_skills(transcripts_mod.iter_events(transcript))
             if transcript else [])

    target_fired = probe.skill in fired
    record = {
        "probe": {"id": probe.id, "skill": probe.skill, "expect": probe.expect,
                  "prompt": probe.prompt},
        "model": model,
        "pylgrim_repo_sha": pylgrim_repo_sha(skills_source),
        "session_id": session_id,
        "fired_skills": fired,
        "target_fired": target_fired,
        "correct": target_fired if probe.expect == "should" else not target_fired,
        "result_text": str(cli_result.get("result") or "")[:2000],
        "duration_ms": cli_result.get("duration_ms"),
    }
    (out_dir / "result.json").write_text(
        json.dumps(record, indent=2, default=str), encoding="utf-8"
    )
    return record


def load_results(results_dir: Path) -> list[dict[str, Any]]:
    """All completed probe results, sorted by probe id."""
    out = []
    base = Path(results_dir) / "triggers"
    if not base.is_dir():
        return out
    for path in sorted(base.glob("*/result.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return out


def score(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-skill hit rates (should) and false-fire rates (should_not)."""
    stats: dict[str, dict[str, Any]] = {}
    for record in results:
        probe = record.get("probe") or {}
        skill = probe.get("skill", "?")
        bucket = stats.setdefault(
            skill, {"should_total": 0, "should_hit": 0,
                    "should_not_total": 0, "false_fires": 0})
        if probe.get("expect") == "should":
            bucket["should_total"] += 1
            if record.get("target_fired"):
                bucket["should_hit"] += 1
        else:
            bucket["should_not_total"] += 1
            if record.get("target_fired"):
                bucket["false_fires"] += 1
    return stats
