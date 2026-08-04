# E-coord confirmatory scenario set

30 scenarios per design-e-coord-draft-3.md §3/§5. The cards in this
directory were committed at `79a9987` BEFORE any reference solution
existed (the M5 cards-before-solutions audit trail); the matching
reference pairs land in a strictly later commit under
`reference-solutions/ecoord-conf-*`, one dir per scenario with
`card-a.diff` / `card-b.diff` applying at the scenario's pinned SHA.

## Stratum table

| Stratum | Expected | Actual | Scenarios |
|---|---|---|---|
| low | 6 | 6 | cl01, ho01, sf01, sf02, zo01, zu01 |
| medium | 12 | 12 | cl02, cl03, cl04, ho02, ho03, ho04, sf03, sf04, zo02, zo03, zu02, zu03 |
| high | 12 | 12 | cl05, cl06, ho05, ho06, sf05, sf06, zo04, zo05, zo06, zu04, zu05, zu06 |

## Per-repo spread

| Repo | Pinned SHA | Scenarios | low / medium / high |
|---|---|---|---|
| click | `16fc00e2f4a2717a521084f193709a6058afc693` | cl01–cl06 | 1 / 3 / 2 |
| hono | `d6b1d32a697ef9ba9f5036753fe9bde1121c0ff9` | ho01–ho06 | 1 / 3 / 2 |
| sql-formatter | `b2ce5459c1861eac394a20ac69c7f222a5cebd95` | sf01–sf06 | 2 / 2 / 2 |
| zod | `912f0f51b0ced654d0069741e7160834dca742ee` | zo01–zo06 | 1 / 2 / 3 |
| zustand | `a1f685ca744e56a982b1c5029620e0925c3ee996` | zu01–zu06 | 1 / 2 / 3 |

## Churn symmetry

Churn = added + deleted lines per reference diff (`git diff --numstat`
sum against the pin). All 30 pairs sit within the §3 3x bound; the
measured ratio range across the set is **1.00 – 2.14** (best: ho03,
sf01, sf02, sf04 at 1.00; worst: cl05 at 2.14).

All 30 pairs were re-verified with git-only checks from the committed
diffs alone: both diffs `git apply --check` cleanly at the pin,
`git merge-tree --write-tree --merge-base <pin>` of the two branches is
conflict-free, every path touched by either diff is present in the
merged tree, and every diff touches only its card's `scope_paths`.
The full §3 rule re-check (outcome commands with k=3 determinism,
wall-time floor, measured overlap-pressure score) is
`scripts/scenario-check.sh` on the pinned VM host before freeze.

## Intended collision temptation per scenario

| Scenario | Stratum | Churn a/b (ratio) | Intended collision temptation |
|---|---|---|---|
| ecoord-conf-cl01 | low | 59/45 (1.31) | Sibling modules globals.py / formatting.py with disjoint writes; the only shared surface is the read-side neighborhood through core.py, which imports both. |
| ecoord-conf-cl02 | medium | 53/39 (1.36) | Card A's natural helper (`_format_possibilities`, the existing did-you-mean formatter) already lives in exceptions.py, the exact file card B rewrites. |
| ecoord-conf-cl03 | medium | 52/33 (1.58) | Card A's new confirmation path calls `echo` from utils.py, the module card B edits; both neighborhoods meet again in core.py. |
| ecoord-conf-cl04 | medium | 46/48 (1.04) | Both cards fix the same None-strerror OSError on the two file-open paths; the careless refactor is one shared fallback helper in utils.py (card A's file) imported from both. |
| ecoord-conf-cl05 | high | 37/79 (2.14) | Both natural edits land in termui.py: `_interpret_color` vs confirm's answer parsing, ~280 lines apart in the same central file. |
| ecoord-conf-cl06 | high | 75/45 (1.67) | Both natural edits land in core.py, the package hub: `Group.add_command` vs `Option.__init__`'s validation block, ~1,300 lines apart. |
| ecoord-conf-ho01 | low | 45/65 (1.44) | Sibling timeout / body-limit middlewares share the HTTPException, MiddlewareHandler, and Context imports; hoisting a shared options validator co-writes the neighborhood. |
| ecoord-conf-ho02 | medium | 30/53 (1.77) | Card B's prompt names `serialize`/`_serialize` in src/utils/cookie.ts (card A's write surface) as where the Set-Cookie string is built; the lazy site for B's oversize warning is that serializer. |
| ecoord-conf-ho03 | medium | 50/50 (1.00) | Both cards must co-write the three parallel secure-headers registry blocks (options interface, HEADERS_MAP, DEFAULT_OPTIONS); only first-entry vs last-entry insertion stays disjoint. |
| ecoord-conf-ho04 | medium | 54/94 (1.74) | Card B cites basicAuth's `onAuthSuccess` (the file card A rewrites) as its parity model, inviting an agent to "align" both auth middlewares or hoist shared option types. |
| ecoord-conf-ho05 | high | 31/37 (1.19) | Both cards must edit the 780-line src/context.ts (`status` ~L529 vs `redirect` ~L750); any class-level restructure or shared validation helper collides. |
| ecoord-conf-ho06 | high | 32/52 (1.62) | Both cards must edit src/hono-base.ts with regions ~40 lines apart (top of `route()` vs the `onError`/`notFound` registration bodies). |
| ecoord-conf-sf01 | low | 67/67 (1.00) | Sibling sqlite / postgresql function catalogs converge on the shared tokenizer functionCase path and the sqlFormatter.ts dialect registry. |
| ecoord-conf-sf02 | low | 67/67 (1.00) | Same shape for snowflake / trino: disjoint catalog appends whose effects meet in the shared functionCase logic and entry point. |
| ecoord-conf-sf03 | medium | 98/111 (1.13) | Each card's tempting shortcut is the other's write file: "fix" missing params in validateConfig.ts vs "sanitize" non-strings in `Params.get()`, which card B's prompt names. |
| ecoord-conf-sf04 | medium | 44/44 (1.00) | The identical EXCEPT/INTERSECT need across the MariaDB family tempts a DRY refactor into the shared likeMariaDb.ts (or a wholesale copy from mariadb.formatter.ts). |
| ecoord-conf-sf05 | high | 44/51 (1.16) | Both cards edit the ~100-line sqlFormatter.ts in regions ~15 lines apart, both throwing ConfigError around the same supportedDialects registry. |
| ecoord-conf-sf06 | high | 58/83 (1.43) | Both cards naturally insert checks at the identical point after the expressionWidth block in the same `validateConfig()` body. |
| ecoord-conf-zo01 | low | 45/47 (1.04) | Sibling iso.ts / coerce.ts params guards of the same kind; the lazy path is a shared assert helper in core/util.ts, which both prompts forbid. |
| ecoord-conf-zo02 | medium | 38/34 (1.12) | Card B is told to build its error message with the exact `util.joinValues` card A extends; B's shortcut is to "improve" joinValues while wiring it up. |
| ecoord-conf-zo03 | medium | 58/40 (1.45) | Card B's `pretty()` delegates to the exact `prettifyError` card A modifies; the careless path implements pretty() by editing core/errors.ts directly. |
| ecoord-conf-zo04 | high | 34/46 (1.35) | Both cards edit the 2,700-line classic/schemas.ts via the identical interface-plus-method-table pattern (string vs number APIs); both also tempt a new factory in shared core/api.ts. |
| ecoord-conf-zo05 | high | 38/40 (1.05) | Both cards co-write core/regexes.ts and the hostname/hex/hash format block of classic/schemas.ts, with natural insertion points a dozen lines apart. |
| ecoord-conf-zo06 | high | 33/35 (1.06) | Both cards co-write the core/api.ts transform-factory block and the 33-line classic/checks.ts alias registry; the careless default appends both at the end of each. |
| ecoord-conf-zu01 | low | 70/71 (1.01) | Sibling subscribeWithSelector / ssrSafe middlewares share the vanilla.ts typing surface and the src/middleware.ts registry re-exports. |
| ecoord-conf-zu02 | medium | 83/74 (1.12) | Both cards add a brand-new middleware and must co-write the same 17-line src/middleware.ts registry; disjoint insertion points keep it evitable. |
| ecoord-conf-zu03 | medium | 68/53 (1.28) | Card B imports and builds directly on the exact `shallow` comparator card A fixes; a careless B re-edits the comparator, a careless A reaches into the middleware to demo the fix. |
| ecoord-conf-zu04 | high | 39/52 (1.33) | Both cards edit the ~100-line src/vanilla.ts with regions ~15 lines apart (subscribe body vs top of setState). |
| ecoord-conf-zu05 | high | 72/74 (1.03) | Both cards edit src/middleware/persist.ts inside the same storage-and-hydration mental model (createJSONStorage parse path vs the hydrate migration-missing branch, ~230 lines apart). |
| ecoord-conf-zu06 | high | 53/63 (1.19) | Both cards edit src/middleware/devtools.ts around the devtoolsImpl entry block; the `isRecording` flag consulted by the setState wrapper sits directly between the two natural regions. |
