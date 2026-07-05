# Corpus candidates (awaiting founder ratification)

Researched 2026-07-05 via the GitHub REST API (licenses from `license.spdx_id`, activity from live issue/PR queries; nothing cloned). LOC figures are estimates (language bytes / 35). Ratifying a repo means: pin a SHA in `corpus.yaml`, verify the test suite green on the eval host, then author its task cards. Per `docs/10-evaluation-plan.md` (venture repo) §4: ~10 repos, permissive licenses only, ~6/10 TS/JS, strata small/medium/large ≈ 3/4/3, domain diversity, contamination recorded honestly.

## Recommended pin (10)

| Repo | Lang | License | Stratum | Est. LOC | Linked issue→PR pairs | Test | Windows risk |
|---|---|---|---|---|---|---|---|
| pmndrs/zustand | TS | MIT | S | ~8k | 121 (17%) | vitest | minor (no Win CI) |
| sql-formatter-org/sql-formatter | TS | MIT | S | ~22k | 73 (15%) | jest | minor (no Win CI) |
| pallets/click | Py | BSD-3 | S | ~24k | 375 (22%) | pytest | none (Win CI) |
| sharkdp/fd | Rust | Apache-2.0/MIT | S | ~7.5k | 153 (18%) | cargo test | none (Win CI) |
| spf13/cobra | Go | Apache-2.0 | S | ~13k | 128 (13%) | go test | none (Win CI) |
| honojs/hono | TS | MIT | M | ~71k | 514 (34%) | vitest (scope to node project) | none (Win CI) |
| colinhacks/zod | TS | MIT | M | ~69k | 333 (11%) | vitest (light pnpm ws) | minor |
| prettier/prettier | JS | MIT | M/L | ~107k | 1,344 (22%) | jest (Yarn 4/corepack) | none (Win CI) |
| Textualize/rich | Py | MIT | M | ~49k | 198 (15%) | pytest | none (Win CI) |
| eslint/eslint | JS | MIT | L | ~322k | 1,905 (18%) | mocha (scope per rule) | none (Win CI) |
| nushell/nushell | Rust | MIT | L | ~385k | 2,143 (37%) | cargo test (slow first build) | none (Win first-class) |
| gohugoio/hugo | Go | Apache-2.0 | L | ~176k | 1,972 (25%) | go test (skip CGO extras) | minor |

That table lists 12: pick 10 by dropping two of {prettier, hugo, zod} for balance, or keep 12 and trim tasks per repo. Domains all distinct: state mgmt, SQL formatting, CLI framework (Py), file-search CLI, CLI framework (Go), web framework, schema validation, code formatter, terminal rendering, linter, shell, static site generator.

## Bench (spares, with reasons)

- **fastify** (MIT, M, 479 pairs): strong, but overlaps hono's domain; swap-in if hono misbehaves.
- **pydantic** (MIT, L, 1,596 pairs, 31%): excellent linkage; vendored Rust core makes it the heaviest install (Rust toolchain + maturin). Large-Python alternate.
- **cheeriojs/cheerio** (MIT, S/M borderline): medium-stratum backfill.
- **crate-ci/typos** (Apache-2.0): real-code medium, but language-bytes LOC misleading (generated dictionaries).
- **python-attrs/attrs** (MIT, S): lowest-contamination Python spare if click's Pallets fame is a concern.
- **ajv-validator/ajv** (MIT): validation-domain overlap with zod; slower moving.
- **tj/commander.js**, **markdown-it/markdown-it**: healthy projects, but linked-PR pools too thin to source 5 T-real tasks (37 and 19 lifetime pairs).

## Dropped with cause

eemeli/yaml (ISC license), mkdocs (stale ~9 months), httpx (activity anomaly), dayjs (1,280 open issues, sporadic triage).

## Contamination notes to carry into task cards

prettier/eslint/hugo/nushell/zod are famous enough that memorization is likely (The SWE-Bench Illusion, arXiv:2506.12286); record issue/fix dates vs model cutoff per task and prefer 2025-26 issues. sql-formatter has the best contamination profile in the set. Drift metrics (M1-M3) are structurally more contamination-resistant than resolution metrics, which is part of why they are primary.

## Pilot suggestion (2 repos, 4 tasks each, for WI-E04)

**zustand** (small TS, fast vitest, clean install) + **click** (small Python, pytest, Win CI, 22% linkage). Both install in seconds and keep pilot iteration cheap.
