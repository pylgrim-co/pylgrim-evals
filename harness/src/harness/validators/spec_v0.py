"""spec_v0: the first planned pylgrim validator (stub).

Planned interface: a validator is constructed from a task card and evaluates
a working diff (plus changed/created path lists) against the formal intent,
returning structured findings. The pylgrim arm (arms.render, Wave 2) will
wire this into the agent's loop as an enforcement layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from harness.taskcards import TaskCard


@dataclass
class Finding:
    """One validator finding: a rule/scope breach with enough detail to act on."""

    kind: str            # e.g. "scope", "protected-path", "new-dep"
    severity: str        # "block" | "warn"
    path: str            # offending repo-relative path, if applicable
    detail: str          # human/agent-readable explanation


class SpecV0Validator:
    """Validates a working diff against a task card's intent artifacts."""

    def __init__(self, task: TaskCard) -> None:
        self.task = task

    def validate(
        self,
        diff_text: str,
        name_only: list[str],
        untracked: list[str],
    ) -> list[Finding]:
        """Return findings for the current working state. Not implemented (Wave 2)."""
        raise NotImplementedError("Wave 2")

    def render_feedback(self, findings: list[Finding]) -> str:
        """Render findings as agent-facing corrective feedback. Not implemented (Wave 2)."""
        raise NotImplementedError("Wave 2")
