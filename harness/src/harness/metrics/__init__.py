"""Deterministic outcome metrics.

Every metric here is a pure function over the run's captured artifacts:
the git diff text, the name-only changed file list, the untracked file list,
and the task card. No network, no subprocess (except tests_outcome, which
runs the task's own test command inside the workspace). This keeps metrics
recomputable at any time from stored artifacts via `harness extract`.
"""

from __future__ import annotations

import fnmatch


def norm_path(path: str) -> str:
    """Normalize a repo-relative path to posix form for glob matching."""
    path = path.replace("\\", "/").strip().strip('"')
    while path.startswith("./"):
        path = path[2:]
    return path


def matches_any(path: str, globs: list[str]) -> bool:
    """fnmatch-based glob matching over posix-normalized paths.

    Note: fnmatch's `*` matches across `/` (there is no special-cased `**`),
    so `src/*` matches `src/a/b.py`. Task cards are written with this in mind.
    """
    path = norm_path(path)
    return any(fnmatch.fnmatch(path, g) for g in globs)


def churn_by_file(diff_text: str) -> dict[str, tuple[int, int]]:
    """Parse unified diff text into {path: (lines_added, lines_deleted)}.

    Paths are taken from the `+++ b/...` header (or `--- a/...` for pure
    deletions). +/- lines are counted per file section, excluding headers.
    """
    churn: dict[str, tuple[int, int]] = {}
    current: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            current = None
        elif line.startswith("+++ "):
            target = line[4:].strip()
            if target != "/dev/null":
                current = norm_path(target[2:] if target.startswith("b/") else target)
                churn.setdefault(current, (0, 0))
        elif line.startswith("--- "):
            source = line[4:].strip()
            if source != "/dev/null" and current is None:
                current = norm_path(source[2:] if source.startswith("a/") else source)
                churn.setdefault(current, (0, 0))
        elif current is not None and line.startswith("+") and not line.startswith("+++"):
            added, deleted = churn[current]
            churn[current] = (added + 1, deleted)
        elif current is not None and line.startswith("-") and not line.startswith("---"):
            added, deleted = churn[current]
            churn[current] = (added, deleted + 1)
    return churn
