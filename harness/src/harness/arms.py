"""Experimental arm rendering.

An arm decides how the task's intent artifacts reach the agent. The prompt
handed to `claude -p` is identical across arms (task.prompt verbatim); arms
differ only in what extra context is materialized into the workspace:

  vanilla   nothing; the prompt is the only channel.
  claudemd  the same intent rendered into a CLAUDE.md at the workspace root,
            which Claude Code auto-discovers.
  pylgrim   Wave 2: the enforcement layer. Not implemented yet.
"""

from __future__ import annotations

from pathlib import Path

from harness.taskcards import TaskCard

ARMS = ("vanilla", "claudemd", "pylgrim")


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


def render(arm: str, task: TaskCard, workspace_dir: Path | str) -> str:
    """Materialize the arm into the workspace. Returns the final prompt string.

    The prompt is intentionally the same across arms: the experimental
    manipulation is the context channel, never the prompt text.
    """
    workspace_dir = Path(workspace_dir)
    if arm == "vanilla":
        pass
    elif arm == "claudemd":
        (workspace_dir / "CLAUDE.md").write_text(render_claude_md(task), encoding="utf-8")
    elif arm == "pylgrim":
        raise NotImplementedError("Wave 2")
    else:
        raise ValueError(f"unknown arm: {arm!r}")
    return task.prompt
