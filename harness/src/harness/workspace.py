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

import os
import subprocess
import tempfile
from pathlib import Path


class WorkspaceError(RuntimeError):
    """Raised when a workspace cannot be prepared or verified clean."""


# Identity for harness-authored commit objects (episode branch/merge commits).
# Deterministic dates keep commit OIDs a pure function of tree + parents +
# message, so re-finalizing an episode is idempotent.
_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "pylgrim-harness",
    "GIT_AUTHOR_EMAIL": "harness@pylgrim.invalid",
    "GIT_COMMITTER_NAME": "pylgrim-harness",
    "GIT_COMMITTER_EMAIL": "harness@pylgrim.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00 +0000",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00 +0000",
}


def _git(*args: str, cwd: Path | str | None = None, env: dict[str, str] | None = None) -> str:
    """Run a git command, returning stdout. Raises WorkspaceError on failure.

    `env` entries are overlaid on the ambient environment (needed for
    GIT_INDEX_FILE scratch indexes and the harness commit identity).
    """
    full_env = None
    if env is not None:
        full_env = {**os.environ, **env}
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=full_env,
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


def _force_rmtree(path: Path) -> None:
    """rmtree that survives Windows read-only files (git objects, pnpm
    stores set them): clear the attribute and retry, and fail LOUDLY if the
    directory survives (a silent half-delete poisons the next worktree add)."""
    import os
    import shutil
    import stat

    def _onexc(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    if not path.exists():
        return
    shutil.rmtree(path, onexc=_onexc)
    if path.exists():
        raise WorkspaceError(
            f"could not remove slot dir {path}: a process may hold it open"
        )


def prepare(
    results_dir: Path | str,
    slot: int,
    name: str,
    url: str,
    base_sha: str,
    preserve: tuple[str, ...] = ("node_modules", ".venv", "target"),
) -> Path:
    """Create or reset the slot worktree at the pinned SHA. Returns the slot dir."""
    results_dir = Path(results_dir).resolve()
    return prepare_dir(results_dir, slot_path(results_dir, slot), name, url, base_sha, preserve)


def prepare_dir(
    results_dir: Path | str,
    slot_dir: Path,
    name: str,
    url: str,
    base_sha: str,
    preserve: tuple[str, ...] = ("node_modules", ".venv", "target"),
) -> Path:
    """Create or reset an arbitrary worktree dir at the pinned SHA.

    Generalization of prepare() for the episode runner's three per-episode
    slots (agent-a, agent-b, merged), which live under separate roots so an
    agent exploring its own tree can never see its sibling's."""
    # Resolve up front: git commands below run with cwd=clone, where a relative
    # results_dir would silently resolve to the wrong place.
    results_dir = Path(results_dir).resolve()
    slot_dir = Path(slot_dir).resolve()
    clone = ensure_bare_clone(results_dir, name, url, base_sha)
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
                _force_rmtree(slot_dir)
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
    base_sha: str | None = None,
) -> dict[str, str]:
    """Capture the run's diff artifacts, then scrub the worktree pristine.

    Writes to run_results_dir:
      diff.patch       git diff (tracked changes)
      name_only.txt    git diff --name-only
      untracked.txt    untracked, non-ignored files (one per line)

    base_sha: when given, diffs are taken AGAINST THE PINNED BASE, not the
    working tree vs HEAD. Agents sometimes `git commit` their work unprompted
    (observed live: haiku committed instructed drift and every diff-based
    metric read zero while the transcript estimator still fired); diffing
    against the base makes committed changes visible, and agent_committed
    records that HEAD moved. Without base_sha the legacy working-tree diff
    is preserved for old callers.

    Then resets (git reset --hard <base>, or checkout . when no base),
    cleans with -fdx -e <preserve...>, and verifies `git status --porcelain`
    is empty (ignoring preserved entries).
    Returns the artifact contents keyed by name, plus agent_committed
    ("true"/"false").
    """
    slot_dir = Path(slot_dir)
    run_results_dir = Path(run_results_dir)
    run_results_dir.mkdir(parents=True, exist_ok=True)

    agent_committed = False
    if base_sha:
        head = _git("rev-parse", "HEAD", cwd=slot_dir).strip()
        agent_committed = head != base_sha
        diff_text = _git("diff", base_sha, cwd=slot_dir)
        name_only = _git("diff", "--name-only", base_sha, cwd=slot_dir)
    else:
        diff_text = _git("diff", cwd=slot_dir)
        name_only = _git("diff", "--name-only", cwd=slot_dir)
    untracked = _git("ls-files", "--others", "--exclude-standard", cwd=slot_dir)

    (run_results_dir / "diff.patch").write_text(diff_text, encoding="utf-8")
    (run_results_dir / "name_only.txt").write_text(name_only, encoding="utf-8")
    (run_results_dir / "untracked.txt").write_text(untracked, encoding="utf-8")

    if base_sha:
        _git("reset", "--hard", base_sha, cwd=slot_dir)
    _clean(slot_dir, preserve)

    leftovers = []
    for line in _git("status", "--porcelain", cwd=slot_dir).splitlines():
        path = line[3:].strip().strip('"')
        if any(path == p or path.startswith(f"{p}/") for p in preserve):
            continue
        leftovers.append(line)
    if leftovers:
        raise WorkspaceError(f"worktree not clean after reset: {leftovers[:10]}")

    return {
        "diff": diff_text,
        "name_only": name_only,
        "untracked": untracked,
        "agent_committed": "true" if agent_committed else "false",
    }


# --- episode support: tree hashes, harness commits, merge-tree ---------------
#
# The E-coord episode runner (episode.py) checkpoints worktree state as a
# git tree hash per turn (design draft 3 §2, O1), commits each agent's final
# state as a harness-authored commit for the merge, and materializes the
# merged tree in a third slot (O5). All of that lives here because it is
# worktree lifecycle, not experiment logic.


def _stage_all_minus_preserve(
    slot_dir: Path, preserve: tuple[str, ...], env: dict[str, str]
) -> None:
    """Stage the full non-ignored content state into the scratch index, then
    drop `preserve` paths from it.

    Deliberately NOT `git add -A -- . :(exclude)p`: git 2.43 exits 1 with
    addIgnoredFile advice when an explicit pathspec's walk covers ignored
    dirs (node_modules/.venv), which killed 13/16 pilot episodes on
    2026-08-01. A bare `git add -A` never takes the explicit-pathspec
    advice path; preserve entries are then removed from the index directly,
    covering repos where they are not gitignored."""
    _git("add", "-A", cwd=slot_dir, env=env)
    for p in preserve:
        _git(
            "rm", "-r", "--cached", "--ignore-unmatch", "-q", "--", p,
            cwd=slot_dir, env=env,
        )


def worktree_tree_hash(
    slot_dir: Path | str, preserve: tuple[str, ...] = ()
) -> str:
    """Hash the working tree's full content state (tracked + untracked,
    non-ignored) as a git tree OID, without touching the real index or HEAD.

    Uses a scratch GIT_INDEX_FILE: `git add -A` stages everything (minus
    `preserve` entries, which are dependency caches whose contents must not
    perturb the checkpoint hash), then `write-tree` emits the OID. Two calls
    over identical content always agree, which is what makes this usable as
    the O1 resume gate."""
    slot_dir = Path(slot_dir)
    with tempfile.TemporaryDirectory(prefix="harness-treehash-") as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index")}
        _stage_all_minus_preserve(slot_dir, preserve, env)
        return _git("write-tree", cwd=slot_dir, env=env).strip()


def commit_worktree(
    slot_dir: Path | str,
    base_sha: str,
    message: str,
    preserve: tuple[str, ...] = (),
) -> dict[str, str]:
    """Commit the worktree's current content state on top of base_sha without
    moving HEAD or the real index. Returns {"tree": oid, "commit": oid}.

    The commit object lands in the shared object store (the bare clone all
    slots are worktrees of), so merge-tree and worktree-add can consume it."""
    slot_dir = Path(slot_dir)
    with tempfile.TemporaryDirectory(prefix="harness-committree-") as tmp:
        env = {"GIT_INDEX_FILE": str(Path(tmp) / "index"), **_COMMIT_ENV}
        _stage_all_minus_preserve(slot_dir, preserve, env)
        tree = _git("write-tree", cwd=slot_dir, env=env).strip()
        commit = _git(
            "commit-tree", tree, "-p", base_sha, "-m", message, cwd=slot_dir, env=env
        ).strip()
    return {"tree": tree, "commit": commit}


def commit_tree(
    repo_dir: Path | str, tree: str, parents: list[str], message: str
) -> str:
    """Create a commit object for an existing tree (the merged-tree slot)."""
    args = ["commit-tree", tree]
    for parent in parents:
        args += ["-p", parent]
    args += ["-m", message]
    return _git(*args, cwd=repo_dir, env=dict(_COMMIT_ENV)).strip()


def update_ref(repo_dir: Path | str, ref: str, commit: str) -> None:
    """Pin a ref on a commit so episode objects survive any future gc."""
    _git("update-ref", ref, commit, cwd=repo_dir)


def merge_tree_write_tree(
    repo_dir: Path | str, base: str, commit_a: str, commit_b: str
) -> dict[str, object]:
    """Run `git merge-tree --write-tree` from an explicit merge base.

    Returns {"clean": bool, "tree": oid, "conflicted_files": [...], "raw": str}.
    Exit 0 = clean merge, 1 = content conflicts (both are valid outcomes and
    C1 raw inputs); anything else is a git failure and raises. --name-only
    keeps the conflicted-file section parseable: first line is the toplevel
    tree OID, then conflicted filenames until the first blank line."""
    result = subprocess.run(
        [
            "git", "merge-tree", "--write-tree", "--name-only",
            "--merge-base", base, commit_a, commit_b,
        ],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode not in (0, 1):
        raise WorkspaceError(
            f"git merge-tree failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    lines = result.stdout.splitlines()
    if not lines or not lines[0].strip():
        raise WorkspaceError(f"git merge-tree produced no tree OID: {result.stdout!r}")
    tree = lines[0].strip()
    conflicted: list[str] = []
    if result.returncode == 1:
        for line in lines[1:]:
            if not line.strip():
                break
            conflicted.append(line.strip())
    return {
        "clean": result.returncode == 0,
        "tree": tree,
        "conflicted_files": conflicted,
        "raw": result.stdout,
    }


def changed_files(repo_dir: Path | str, base: str, commit: str) -> list[tuple[str, str]]:
    """(status, path) pairs for a commit vs the base (A/M/D/R...)."""
    out = _git("diff-tree", "-r", "--name-status", "--no-renames", base, commit, cwd=repo_dir)
    pairs: list[tuple[str, str]] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        status, _, path = line.partition("\t")
        pairs.append((status.strip(), path.strip()))
    return pairs


def diff_text(repo_dir: Path | str, base: str, commit: str) -> str:
    """Full patch text of a commit vs the base (the branch diff artifact)."""
    return _git("diff", base, commit, cwd=repo_dir)


def blob_oid(repo_dir: Path | str, commit: str, path: str) -> str | None:
    """Blob OID of a path at a commit, or None when absent."""
    try:
        return _git("rev-parse", f"{commit}:{path}", cwd=repo_dir).strip()
    except WorkspaceError:
        return None
