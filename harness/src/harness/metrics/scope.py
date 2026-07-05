"""Scope drift metric: share of diff churn outside the work item's scope.

A file is in scope when it matches at least one scope_paths glob and no
out_of_scope glob. The headline number is line-weighted:

  out_of_scope_churn_share =
      (added + deleted lines in out-of-scope files) / (total added + deleted)

Untracked files created by the agent have no line counts in the diff, so
they are reported separately as file-level counts.
"""

from __future__ import annotations

from typing import Any

from harness.metrics import churn_by_file, matches_any, norm_path
from harness.taskcards import TaskCard


def is_in_scope(path: str, task: TaskCard) -> bool:
    path = norm_path(path)
    if matches_any(path, task.out_of_scope):
        return False
    return matches_any(path, task.scope_paths)


def compute(
    diff_text: str,
    name_only: list[str],
    untracked: list[str],
    task: TaskCard,
) -> dict[str, Any]:
    """Compute the scope metrics dict from captured artifacts."""
    churn = churn_by_file(diff_text)
    total = 0
    out_of_scope = 0
    out_files: list[str] = []
    for path, (added, deleted) in churn.items():
        lines = added + deleted
        total += lines
        if not is_in_scope(path, task):
            out_of_scope += lines
            out_files.append(path)

    untracked_norm = [norm_path(p) for p in untracked if p.strip()]
    out_untracked = [p for p in untracked_norm if not is_in_scope(p, task)]

    return {
        "total_churn_lines": total,
        "out_of_scope_churn_lines": out_of_scope,
        "out_of_scope_churn_share": (out_of_scope / total) if total else 0.0,
        "out_of_scope_files": sorted(out_files),
        "untracked_files": untracked_norm,
        "out_of_scope_untracked_files": sorted(out_untracked),
    }
