"""Workspace management: bare clone cache plus a small worktree slot pool.

Each repo is cloned once as a bare repo under results/repos/<name>.git.
Runs execute in worktrees under results/slots/<n> (default pool of 2),
pinned to the task's base SHA. After a run, capture_and_reset() writes the
diff artifacts to the run's results dir and scrubs the worktree back to a
pristine checkout, preserving dependency caches (node_modules, .venv,
target) listed in the corpus per-repo `preserve` field.

Nothing in this module ever touches paths outside the results dir.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class WorkspaceError(RuntimeError):
    """Raised when a workspace cannot be prepared or verified clean."""


def _git(*args: str, cwd: Path | str | None = None) -> str:
    """Run a git command, returning stdout. Raises WorkspaceError on failure."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise WorkspaceError(
            f"git {' '.join(args)} failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def bare_clone_path(results_dir: Path | str, name: str) -> Path:
    return Path(results_dir) / "repos" / f"{name}.git"


def slot_path(results_dir: Path | str, slot: int) -> Path:
    return Path(results_dir) / "slots" / str(slot)


def ensure_bare_clone(results_dir: Path | str, name: str, url: str, sha: str) -> Path:
    """Clone the repo bare if missing; fetch only when the pinned SHA is absent."""
    clone = bare_clone_path(results_dir, name)
    if not clone.exists():
        clone.parent.mkdir(parents=True, exist_ok=True)
        _git("clone", "--bare", url, str(clone))
    try:
        _git("cat-file", "-e", f"{sha}^{{commit}}", cwd=clone)
    except WorkspaceError:
        _git("fetch", "origin", cwd=clone)
        _git("cat-file", "-e", f"{sha}^{{commit}}", cwd=clone)
    return clone


def _slot_belongs_to(slot_dir: Path, clone: Path) -> bool:
    """True if slot_dir is an existing worktree of the given bare clone."""
    if not (slot_dir / ".git").exists():
        return False
    try:
        common = _git("rev-parse", "--git-common-dir", cwd=slot_dir).strip()
    except WorkspaceError:
        return False
    return Path(common).resolve() == clone.resolve()


def prepare(
    results_dir: Path | str,
    slot: int,
    name: str,
    url: str,
    base_sha: str,
    preserve: tuple[str, ...] = ("node_modules", ".venv", "target"),
) -> Path:
    """Create or reset the slot worktree at the pinned SHA. Returns the slot dir."""
    # Resolve up front: git commands below run with cwd=clone, where a relative
    # results_dir would silently resolve to the wrong place.
    results_dir = Path(results_dir).resolve()
    clone = ensure_bare_clone(results_dir, name, url, base_sha)
    slot_dir = slot_path(results_dir, slot)
    slot_dir.parent.mkdir(parents=True, exist_ok=True)

    if _slot_belongs_to(slot_dir, clone):
        _git("checkout", "--detach", "--force", base_sha, cwd=slot_dir)
        _clean(slot_dir, preserve)
    else:
        if slot_dir.exists():
            # Slot holds a different repo (or junk): drop it and start fresh.
            try:
                _git("worktree", "remove", "--force", str(slot_dir), cwd=clone)
            except WorkspaceError:
                import shutil

                shutil.rmtree(slot_dir, ignore_errors=True)
        _git("worktree", "prune", cwd=clone)
        _git("worktree", "add", "--detach", "--force", str(slot_dir), base_sha, cwd=clone)
    return slot_dir


def _clean(slot_dir: Path, preserve: tuple[str, ...]) -> None:
    _git("checkout", ".", cwd=slot_dir)
    args = ["clean", "-fdx"]
    for entry in preserve:
        args += ["-e", entry]
    _git(*args, cwd=slot_dir)


def capture_and_reset(
    slot_dir: Path | str,
    run_results_dir: Path | str,
    preserve: tuple[str, ...] = ("node_modules", ".venv", "target"),
) -> dict[str, str]:
    """Capture the run's diff artifacts, then scrub the worktree pristine.

    Writes to run_results_dir:
      diff.patch       git diff (tracked changes)
      name_only.txt    git diff --name-only
      untracked.txt    untracked, non-ignored files (one per line)

    Then `git checkout . && git clean -fdx -e <preserve...>` and verifies
    `git status --porcelain` is empty (ignoring preserved entries).
    Returns the artifact contents keyed by name.
    """
    slot_dir = Path(slot_dir)
    run_results_dir = Path(run_results_dir)
    run_results_dir.mkdir(parents=True, exist_ok=True)

    diff_text = _git("diff", cwd=slot_dir)
    name_only = _git("diff", "--name-only", cwd=slot_dir)
    untracked = _git("ls-files", "--others", "--exclude-standard", cwd=slot_dir)

    (run_results_dir / "diff.patch").write_text(diff_text, encoding="utf-8")
    (run_results_dir / "name_only.txt").write_text(name_only, encoding="utf-8")
    (run_results_dir / "untracked.txt").write_text(untracked, encoding="utf-8")

    _clean(slot_dir, preserve)

    leftovers = []
    for line in _git("status", "--porcelain", cwd=slot_dir).splitlines():
        path = line[3:].strip().strip('"')
        if any(path == p or path.startswith(f"{p}/") for p in preserve):
            continue
        leftovers.append(line)
    if leftovers:
        raise WorkspaceError(f"worktree not clean after reset: {leftovers[:10]}")

    return {"diff": diff_text, "name_only": name_only, "untracked": untracked}
