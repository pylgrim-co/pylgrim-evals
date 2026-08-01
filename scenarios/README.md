# E-coord scenarios (format stub — a freeze input)

Scenario CONTENT rules live in `preregistration/design-e-coord-draft-3.md`
§3 (existence proof, pressure floor, symmetry, wall-time floor, anti-leak
process rules). Draft 3 does not pin a FILE format, so the episode runner
(`harness/src/harness/episode.py`, module docstring choice 1) defines one
here. This stub is a freeze input: prereg-v6-coord (or later) must ratify
or amend it. Scenario authoring is owned by the scenario-authoring
workstream, not the runner — this directory holds only this README and
`config.yaml` until cards are authored.

## Scenario file: `scenarios/<scenario_id>.yaml`

```yaml
scenario_id: click-s01          # unique across scenarios/
repo: click                     # a repo name from tasks/corpus.yaml
base_sha: <40-char lowercase hex>   # the pinned SHA both agents start from
pressure: low                   # low | medium | high (§3 rule 2 stratum)
work_items:
  a: # a FULL task card, the tasks/*.yaml schema (harness.taskcards.validate)
    id: click-s01-a
    kind: real
    title: "..."
    base_sha: <must equal the scenario base_sha>
    prompt: |-
      ...
    intent:
      constraints: [...]
      work_item:
        criteria: [...]
        scope_paths: [...]
        out_of_scope: [...]
    outcome:
      test_command: "..."       # <=120 s per tree on the pinned VM (§3 rule 4)
    source: { issue_url: "...", ground_truth_pr: "..." }
  b: # same schema, the adjacent work item
    ...
```

Validation (enforced by `harness plan-episodes` / `episode.load_scenario`):
both work-item cards must pass `taskcards.validate` verbatim; both cards'
`base_sha` must equal the scenario `base_sha`; `work_items` has exactly
the keys `a` and `b`; `pressure` is one of low/medium/high.

Reference solution pairs (§3 rule 1) live OUTSIDE this directory and
outside every agent-reachable root (M5); they are not part of the scenario
file format.

## Config file: `scenarios/config.yaml`

```yaml
arms: [coord-none, coord-ledger, coord-pylgrim]
reps: 3
model: sonnet
turn_cap: 6          # R (§2); the pre-committed fallback lever is 4 (§7)
schedule_seed: 42    # §5 master seed
```

All keys optional; the values above are the defaults the runner uses when
the file is absent.
