# E-coord scenarios (file format — a freeze input)

Scenario CONTENT rules live in `preregistration/design-e-coord-draft-3.md`
§3 (existence proof, pressure floor, symmetry, wall-time floor, anti-leak
process rules). Draft 3 does not pin a FILE format, so the episode runner
(`harness/src/harness/episode.py`, module docstring choice 1) pins what it
accepts here. This is a freeze input: prereg-v6-coord (or later) must
ratify ONE canonical shape. Scenario authoring is owned by the
scenario-authoring workstream; the pilot set lives in `scenarios/pilot/`.

## Accepted scenario shapes

`episode.load_scenario` accepts and normalizes two equivalent shapes.
Files are discovered recursively under `scenarios/` (subdirectories like
`pilot/` included; `config.yaml` and non-YAML files skipped).

### Authored pilot shape (the shape committed in scenarios/pilot/)

```yaml
scenario_id: ecoord-pilot-cl01
study: e-coord                  # informational
status: pilot                   # pilot | confirmatory (default confirmatory);
                                # pilots run identically, §6 excludes them at analysis
repo: click                     # a repo name from tasks/corpus.yaml
pinned_sha: <40-char lowercase hex>
pressure:
  stratum: low                  # low | medium | high (§3 rule 2)
  rationale: >-                 # informational
    ...
cards:                          # exactly 2; list order is agent a, agent b
  - id: ecoord-cl01-a
    kind: coord                 # validated under the authored-card rules
    title: "..."
    base_sha: <must equal pinned_sha>
    prompt: |
      ...
    intent:
      constraints: [...]
      work_item:
        criteria: [...]
        scope_paths: [...]
        out_of_scope: [...]
    rules: [...]                # optional, tasks/*.yaml rule ids
    outcome:
      test_command: "..."       # <=120 s per tree on the pinned VM (§3 rule 4)
      deterministic_checks: []
    source: { authored: true }
  - id: ecoord-cl01-b
    ...
```

### Runner stub shape (equivalent)

Top-level `base_sha` instead of `pinned_sha`, a plain `pressure` stratum
string, and `work_items: {a: <card>, b: <card>}` instead of the 2-card
list. Same card schema.

Validation (enforced by `harness plan-episodes` / `episode.load_scenario`):
each card must pass `harness.taskcards.validate` (with `kind: coord`
treated as an authored card, i.e. `source.authored: true` required); both
cards' `base_sha` must equal the scenario pin; exactly two work items;
`pressure`/`pressure.stratum` one of low/medium/high.

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
the file is absent. `harness plan-episodes --status pilot` schedules the
pilot set alone (§6: 6 scenarios x 3 arms x 2 reps — set `reps: 2` in
config for the pilot plan).
