"""Experimental arm rendering.

An arm decides how the task's intent artifacts reach the agent AND, since
Wave 1.5, which prompt carries the ask:

  vanilla         specified prompt; nothing else. The Wave-1 baseline.
  claudemd        specified prompt + the ORACLE CLAUDE.md (harness-rendered
                  intent) at the workspace root. The Wave-1 treatment.
  export          specified prompt + the EXPORTED CLAUDE.md: a .pylgrim/
                  ledger is constructed mechanically from the card's intent
                  and rendered by the vendored real exporter
                  (vendor/export_claudemd.py). E1: the format channel.
  vanilla-vague   vague prompt (the card's source issue, verbatim, from the
                  frozen tasks/vague/vague-prompts-v1.yaml artifact); no
                  context file. E2's realistic baseline.
  claudemd-vague  vague prompt + oracle CLAUDE.md.
  export-vague    vague prompt + exported CLAUDE.md. The product cell.
  compose-vague   vague prompt + an LLM-COMPOSED CLAUDE.md: a pre-run Haiku
                  call reads the vague prompt plus the full .pylgrim ledger
                  and composes a focused context block (P-compose probe,
                  docs/10-evaluation-plan.md par.9; exploratory, publicly
                  labeled a probe). The composed artifact is persisted per
                  run; compose failure fails the run, NEVER falls back to
                  the deterministic export.
  pylgrim         Wave 2: the enforcement layer. Not implemented yet.

Wave 1's prompt-identical-across-arms rule holds WITHIN each prompt row;
the vague row is the pre-registered manipulation (prereg-v2-ext).
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

from harness.taskcards import TaskCard

ARMS = (
    "vanilla", "claudemd", "export",
    "vanilla-vague", "claudemd-vague", "export-vague",
    "stale-generic-vague", "stale-wrong-vague",
    "export-bare-vague", "export-enforce-vague",
    "compose-vague",
    "pylgrim",
)


_REPO_ROOT = Path(__file__).resolve().parents[3]
VAGUE_PROMPTS_PATH = _REPO_ROOT / "tasks" / "vague" / "vague-prompts-v1.yaml"
VENDORED_EXPORTER = Path(__file__).resolve().parent / "vendor" / "export_claudemd.py"

# Deterministic entry stamp: the ledger is a frozen function of the card,
# never of the wall clock (repro requirement).
LEDGER_STAMP = "2026-07-16"

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def render_claude_md(task: TaskCard) -> str:
    """Render the task's formal intent artifacts as CLAUDE.md content."""
    lines: list[str] = ["# Project instructions", ""]

    lines.append("## Constraints")
    lines.append("")
    for constraint in task.constraints:
        lines.append(f"- {constraint}")
    lines.append("")

    lines.append("## Work item")
    lines.append("")
    lines.append("### Acceptance criteria")
    lines.append("")
    for criterion in task.criteria:
        lines.append(f"- {criterion}")
    lines.append("")
    lines.append("### In scope")
    lines.append("")
    lines.append("Only change files matching these paths:")
    lines.append("")
    for pattern in task.scope_paths:
        lines.append(f"- `{pattern}`")
    lines.append("")
    lines.append("### Out of scope")
    lines.append("")
    lines.append("Do not touch files matching these paths:")
    lines.append("")
    for pattern in task.out_of_scope:
        lines.append(f"- `{pattern}`")
    lines.append("")
    return "\n".join(lines)


# --- the exported channel (E1) ----------------------------------------------

def _fake_ulid(seed: str, ordinal: int) -> str:
    """Deterministic 26-char Crockford ULID-shaped id. The 2-digit ordinal
    prefix pins export order (the exporter is ULID-ordered)."""
    digest = hashlib.sha256(f"{seed}:{ordinal}".encode("utf-8")).digest()
    tail = "".join(_CROCKFORD[b % 32] for b in digest[:24])
    return f"{ordinal:02d}{tail}"


def _q(s: str) -> str:
    return '"' + s.replace('"', '\\"') + '"'


def build_pylgrim_ledger(task: TaskCard, dest_root: Path, mode: str = "observe") -> None:
    """Write a .pylgrim/ ledger carrying exactly the card's intent, in the
    spec-v0 frontmatter shape the real exporter consumes. Mechanical: the
    same information as the oracle arm, through the product's own format.
    `mode` sets every constraint's mode field (E9 varies it)."""
    charter = dest_root / ".pylgrim" / "charter"
    work = dest_root / ".pylgrim" / "work"
    charter.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)

    for i, constraint in enumerate(task.constraints):
        ulid = _fake_ulid(task.id, i)
        (charter / f"{ulid}-constraint-{i:02d}.md").write_text(
            "---\n"
            "kind: constraint\n"
            f"mode: {mode}\n"
            "source: manual\n"
            "status: ratified\n"
            f"last_confirmed: {LEDGER_STAMP}\n"
            "---\n\n"
            f"{constraint}\n",
            encoding="utf-8",
        )

    ulid = _fake_ulid(task.id, len(task.constraints))
    fm = [
        "---",
        "kind: work_item",
        "status: ratified",
        "source: manual",
        f"last_confirmed: {LEDGER_STAMP}",
        "scope_paths:",
        *[f"  - {_q(p)}" for p in task.scope_paths],
        "out_of_scope:",
        *[f"  - {_q(p)}" for p in task.out_of_scope],
        "criteria:",
        *[f"  - {{ text: {_q(c)}, status: open }}" for c in task.criteria],
        "---",
        "",
        f"# {task.title}",
        "",
    ]
    (work / f"{ulid}-work-item.md").write_text("\n".join(fm), encoding="utf-8")


def render_exported_claude_md(
    task: TaskCard, mode: str = "observe", strip_mode_tags: bool = False
) -> str:
    """Build the ledger in a scratch dir and run the vendored exporter over
    it; return the CLAUDE.md content it produces.

    E9 variants: `mode` flows into the ledger (the exporter then renders
    `[observe]`/`[enforce]` tags itself, the real path); `strip_mode_tags`
    is the ONE documented synthetic edit — removing the leading mode tag
    from constraint lines to isolate the tag's authority effect
    (prereg-v4-render)."""
    import re

    with tempfile.TemporaryDirectory(prefix="pylgrim-export-") as tmp:
        root = Path(tmp)
        build_pylgrim_ledger(task, root, mode=mode)
        proc = subprocess.run(
            [sys.executable, str(VENDORED_EXPORTER), "--repo-root", str(root)],
            capture_output=True, text=True, encoding="utf-8",
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"vendored exporter failed for {task.id}: {proc.stderr or proc.stdout}"
            )
        text = (root / "CLAUDE.md").read_text(encoding="utf-8")
        if strip_mode_tags:
            text = re.sub(r"^- \[(?:observe|advise|enforce)\] ", "- ", text, flags=re.M)
        return text


# --- the staleness variants (E8) ---------------------------------------------

def build_stale_generic_ledger(task: TaskCard, dest_root: Path) -> None:
    """Charter-only ledger: the card's constraints, NO work item. Models the
    generic repo-level file most repos actually have."""
    charter = dest_root / ".pylgrim" / "charter"
    work = dest_root / ".pylgrim" / "work"
    charter.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    for i, constraint in enumerate(task.constraints):
        ulid = _fake_ulid(task.id, i)
        (charter / f"{ulid}-constraint-{i:02d}.md").write_text(
            "---\nkind: constraint\nmode: observe\nsource: manual\n"
            f"status: ratified\nlast_confirmed: {LEDGER_STAMP}\n---\n\n{constraint}\n",
            encoding="utf-8",
        )


def wrong_card_for(task: TaskCard, siblings: list[TaskCard]) -> TaskCard:
    """Deterministic staleness rule (frozen in prereg-v3-stale): the work
    item shown is the NEXT T-real card's, in sorted id order within the
    repo, cyclically. Models the file nobody updated since the last task."""
    ordered = sorted((c for c in siblings), key=lambda c: c.id)
    ids = [c.id for c in ordered]
    return ordered[(ids.index(task.id) + 1) % len(ordered)]


def render_stale_claude_md(task: TaskCard, variant: str) -> str:
    """Render the stale block through the real exporter.

    generic: the running card's constraints only, no work item (a file with
    some still-relevant rules and no current work contract).
    wrong: the ENTIRE block of the previous card (cyclic-next rule) — the
    file nobody updated since the last task; the corpus cards' constraints
    are task-scoped, so a faithful stale file is stale wholesale."""
    if variant == "generic":
        with tempfile.TemporaryDirectory(prefix="pylgrim-stale-") as tmp:
            root = Path(tmp)
            build_stale_generic_ledger(task, root)
            proc = subprocess.run(
                [sys.executable, str(VENDORED_EXPORTER), "--repo-root", str(root)],
                capture_output=True, text=True, encoding="utf-8",
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"exporter failed (generic) for {task.id}: {proc.stderr or proc.stdout}")
            return (root / "CLAUDE.md").read_text(encoding="utf-8")
    wrong = wrong_card_for(task, _repo_siblings(task))
    return render_exported_claude_md(wrong)


@lru_cache(maxsize=1)
def _all_treal_cards() -> dict[str, list[TaskCard]]:
    from harness import taskcards as _tc
    cards, errs = _tc.load_all(_REPO_ROOT / "tasks")
    if errs:
        raise RuntimeError(f"card load errors: {errs}")
    by_repo: dict[str, list[TaskCard]] = {}
    for c in cards:
        if c.kind == "real" and not c.control and c.horizon == "short":
            by_repo.setdefault(c.id.rsplit("-", 1)[0], []).append(c)
    return by_repo


def _repo_siblings(task: TaskCard) -> list[TaskCard]:
    return _all_treal_cards()[task.id.rsplit("-", 1)[0]]


# --- the vague prompt channel (E2) -------------------------------------------

@lru_cache(maxsize=1)
def _vague_prompts() -> dict[str, str]:
    """Parse the frozen artifact (card id -> verbatim issue prompt)."""
    if not VAGUE_PROMPTS_PATH.exists():
        raise FileNotFoundError(f"vague-prompt artifact missing: {VAGUE_PROMPTS_PATH}")
    prompts: dict[str, str] = {}
    current: str | None = None
    block: list[str] | None = None
    for raw in VAGUE_PROMPTS_PATH.read_text(encoding="utf-8").splitlines():
        if block is not None:
            if raw.startswith("    ") or raw == "":
                block.append(raw[4:] if raw.startswith("    ") else "")
                continue
            prompts[current] = "\n".join(block).rstrip("\n")
            block = None
        if raw.startswith("#") or not raw.strip():
            continue
        if not raw.startswith(" ") and raw.endswith(":"):
            current = raw[:-1]
        elif raw.startswith("  prompt: |-"):
            block = []
    if block is not None and current:
        prompts[current] = "\n".join(block).rstrip("\n")
    return prompts


def vague_prompt_for(task: TaskCard) -> str:
    prompts = _vague_prompts()
    if task.id not in prompts:
        raise ValueError(
            f"{task.id} has no entry in {VAGUE_PROMPTS_PATH.name}; "
            "vague arms may only be scheduled for cards in the frozen artifact"
        )
    return prompts[task.id]


# --- the composed channel (P-compose probe) ----------------------------------

COMPOSE_MODEL = "haiku"  # the probe's pre-run composer tier (frozen)
COMPOSE_TIMEOUT_S = 600  # compose is one short text call, not a coding run


def render_ledger_artifacts(task: TaskCard) -> str:
    """The card's full .pylgrim ledger as one path-labelled text blob.

    Built by build_pylgrim_ledger (the same mechanical ledger the export
    arms consume), then read back file by file so the composer sees exactly
    what the exporter sees -- raw artifacts, not the exported rendering.
    """
    with tempfile.TemporaryDirectory(prefix="pylgrim-ledger-") as tmp:
        root = Path(tmp)
        build_pylgrim_ledger(task, root)
        parts: list[str] = []
        for path in sorted((root / ".pylgrim").rglob("*.md")):
            rel = path.relative_to(root).as_posix()
            parts.append(f"=== {rel} ===\n{path.read_text(encoding='utf-8')}")
        return "\n".join(parts)


def compose_prompt_for(task: TaskCard) -> str:
    """The composer's instruction: the vague prompt the agent will receive,
    plus the full ledger, with the ask to compose a focused CLAUDE.md."""
    return "\n".join([
        "You are preparing the CLAUDE.md context file for a coding agent that",
        "is about to receive the task below in this repository. You do not",
        "solve the task yourself.",
        "",
        "Compose a focused CLAUDE.md for that agent: carry forward the",
        "constraints, acceptance criteria, and scope boundaries from the",
        "intent ledger that matter for this task, phrased so the agent acts",
        "on them. Do not invent constraints and do not drop any scope",
        "boundary. Output ONLY the CLAUDE.md content as markdown, with no",
        "preamble, no explanation, and no code fences.",
        "",
        "## The task the agent will receive",
        "",
        vague_prompt_for(task),
        "",
        "## The repository's intent ledger (.pylgrim/)",
        "",
        render_ledger_artifacts(task),
    ])


def _strip_outer_fence(text: str) -> str:
    """Drop one wrapping ``` fence if the composer added it despite the ask."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return stripped


def compose_claude_md(
    task: TaskCard, timeout_s: int = COMPOSE_TIMEOUT_S, invoke=None
) -> tuple[str, dict]:
    """Run the pre-run composer call; return (composed CLAUDE.md, cli result).

    The call goes through headless.invoke_claude (the harness's one verified
    CLI path) in a scratch cwd, so rate limits surface as RateLimited and
    gate the queue like any other call. Any other failure -- including an
    empty composition -- raises RuntimeError so the run lands in 'error';
    there is deliberately NO fallback to the deterministic export block.
    """
    from harness import headless

    invoke_fn = invoke or headless.invoke_claude
    prompt = compose_prompt_for(task)
    with tempfile.TemporaryDirectory(prefix="pylgrim-compose-") as tmp:
        cli_result = invoke_fn(prompt, COMPOSE_MODEL, Path(tmp), timeout_s)
    composed = _strip_outer_fence(str(cli_result.get("result") or ""))
    if not composed:
        raise RuntimeError(f"compose produced an empty context block for {task.id}")
    return composed + "\n", cli_result


# --- dispatch -----------------------------------------------------------------

def render(arm: str, task: TaskCard, workspace_dir: Path | str) -> str:
    """Materialize the arm into the workspace. Returns the final prompt string.

    Within a prompt row the prompt is identical across context arms; the
    vague row swaps in the frozen issue-verbatim prompt (prereg-v2-ext).
    """
    workspace_dir = Path(workspace_dir)
    if arm not in ARMS:
        raise ValueError(f"unknown arm: {arm!r}")
    if arm == "pylgrim":
        raise NotImplementedError("Wave 2")
    if arm == "compose-vague":
        raise ValueError(
            "compose-vague is rendered by the runner (it needs a model call "
            "and per-run artifact persistence); use compose_claude_md()"
        )

    base = arm[: -len("-vague")] if arm.endswith("-vague") else arm
    if base == "claudemd":
        (workspace_dir / "CLAUDE.md").write_text(render_claude_md(task), encoding="utf-8")
    elif base == "export":
        (workspace_dir / "CLAUDE.md").write_text(
            render_exported_claude_md(task), encoding="utf-8"
        )
    elif base == "stale-generic":
        (workspace_dir / "CLAUDE.md").write_text(
            render_stale_claude_md(task, "generic"), encoding="utf-8"
        )
    elif base == "stale-wrong":
        (workspace_dir / "CLAUDE.md").write_text(
            render_stale_claude_md(task, "wrong"), encoding="utf-8"
        )
    elif base == "export-bare":
        (workspace_dir / "CLAUDE.md").write_text(
            render_exported_claude_md(task, strip_mode_tags=True), encoding="utf-8"
        )
    elif base == "export-enforce":
        (workspace_dir / "CLAUDE.md").write_text(
            render_exported_claude_md(task, mode="enforce"), encoding="utf-8"
        )

    return vague_prompt_for(task) if arm.endswith("-vague") else task.prompt
