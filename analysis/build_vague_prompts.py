"""Build the frozen vague-prompt artifact for Wave 1.5 (prereg-v2-ext).

Authoring rule (mechanical, no human editing): a T-real card's vague prompt
is its source issue's (or discussion's) TITLE + BODY, fetched verbatim from the GitHub API at
`source.issue_url`, joined as "<title>\n\n<body>", truncated at 8,000
characters on the last paragraph boundary (double newline) before the
limit. Real users paste issues at coding agents; this is the realistic
prompt condition with zero authoring bias. Cards whose fetch fails are
excluded from the vague row and listed in the artifact header.

Also fetches zustand-l01 (excluded from the confirmatory set) for the
pre-freeze pipeline smoke.

Usage (from harness/):  uv run python ../analysis/build_vague_prompts.py
Writes: tasks/vague/vague-prompts-v1.yaml  (frozen once prereg-v2-ext is tagged)
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness" / "src"))

from harness import taskcards  # noqa: E402

OUT = ROOT / "tasks" / "vague" / "vague-prompts-v1.yaml"
LIMIT = 8000
SMOKE_EXTRA = {"zustand-l01"}  # excluded card, safe pre-freeze smoke target


def fetch_issue(issue_url: str) -> tuple[str, str]:
    m = re.match(r"https://github\.com/([^/]+)/([^/]+)/(issues|discussions)/(\d+)", issue_url)
    if not m:
        raise ValueError(f"unparseable issue url: {issue_url}")
    owner, repo, kind, num = m.groups()
    if kind == "issues":
        out = subprocess.run(
            ["gh", "api", f"repos/{owner}/{repo}/issues/{num}",
             "--jq", "{title: .title, body: .body}"],
            capture_output=True, text=True, check=True, encoding="utf-8",
        ).stdout
        d = json.loads(out)
    else:
        # Discussions live behind GraphQL only; same title+body rule.
        q = (
            f'query{{repository(owner:"{owner}",name:"{repo}")'
            f"{{discussion(number:{num}){{title body}}}}}}"
        )
        out = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={q}",
             "--jq", ".data.repository.discussion"],
            capture_output=True, text=True, check=True, encoding="utf-8",
        ).stdout
        d = json.loads(out)
    return d["title"] or "", d["body"] or ""


def truncate(text: str, limit: int = LIMIT) -> str:
    if len(text) <= limit:
        return text
    cut = text.rfind("\n\n", 0, limit)
    return text[: cut if cut > 0 else limit].rstrip()


def yaml_block(text: str, indent: str = "    ") -> str:
    """Literal block scalar; lines carry the indent, blank lines stay bare."""
    lines = [(indent + ln).rstrip() for ln in text.splitlines()]
    return "|-\n" + "\n".join(lines)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cards, errs = taskcards.load_all(ROOT / "tasks")
    if errs:
        raise SystemExit(errs)
    # load excluded smoke card too
    excluded_dir = ROOT / "tasks" / "excluded"
    if excluded_dir.exists():
        for p in excluded_dir.glob("*.yaml"):
            card, e = taskcards.load_task_card(p)
            if card:
                cards.append(card)
    targets = {
        c.id: c for c in cards
        if (c.kind == "real" and not c.control) or c.id in SMOKE_EXTRA
    }

    entries: dict[str, dict] = {}
    failures: list[str] = []
    for cid, card in sorted(targets.items()):
        url = (card.raw.get("source") or {}).get("issue_url")
        if not url:
            failures.append(f"{cid} (no issue_url)")
            continue
        try:
            title, body = fetch_issue(url)
        except Exception as e:  # noqa: BLE001
            failures.append(f"{cid} ({type(e).__name__})")
            print(f"FAILED {cid}: {e}")
            continue
        prompt = truncate(f"{title}\n\n{body}".strip())
        entries[cid] = {"url": url, "prompt": prompt}
        print(f"fetched {cid}: {len(prompt)} chars")

    today = datetime.date.today().isoformat()
    lines = [
        "# Vague-prompt artifact v1 (Wave 1.5, prereg-v2-ext).",
        "# Rule: source issue title + body VERBATIM from the GitHub API,",
        f"# joined title\\n\\nbody, truncated at {LIMIT} chars on the last",
        "# paragraph boundary. Mechanical; no human editing. Frozen at the",
        "# prereg-v2-ext tag; never edited after.",
        f"# Fetched: {today} via gh api.",
        f"# Excluded from the vague row (fetch failed): {', '.join(failures) if failures else 'none'}",
        "",
    ]
    for cid, e in sorted(entries.items()):
        lines.append(f"{cid}:")
        lines.append(f"  issue_url: \"{e['url']}\"")
        lines.append(f"  fetched: \"{today}\"")
        lines.append(f"  sha256: \"{hashlib.sha256(e['prompt'].encode('utf-8')).hexdigest()}\"")
        lines.append("  prompt: " + yaml_block(e["prompt"]))
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"written: {OUT} | {len(entries)} prompts | {len(failures)} failures")


if __name__ == "__main__":
    main()
