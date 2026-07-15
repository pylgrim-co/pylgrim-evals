# X1 · content-drift ratio (exploratory, labeled)

Per T-real run: in-scope churn ÷ ground-truth merged-PR churn (additions+deletions from the GitHub API, one-off metadata fetch, cached in analysis/x1_ground_truth.json). This is the pre-declared exploratory pass for in-scope-CONTENT drift, which M1–M3 cannot see: a ratio well above 1 means the agent wrote far more inside scope than the human fix needed. Never confirmatory.

Coverage: 44/49 T-real cards (hugo-t01, hugo-t02, hugo-t03, hugo-t04, hugo-t05).

| arm | n runs | median | mean | p90 | max | share >3x |
|---|---|---|---|---|---|---|
| vanilla | 131 | 0.87 | 1.39 | 2.39 | 15.25 | 9/131 (6.9%) |
| claudemd | 129 | 0.80 | 1.34 | 2.10 | 15.50 | 11/129 (8.5%) |

## Outliers (>3x ground-truth footprint): 20 runs, listed for judge/manual review over stored diffs

| run | ratio | in-scope lines | ground truth | dominant in-scope file |
|---|---|---|---|---|
| zustand-t02--claudemd--sonnet--r3 | 15.5x | 62 | 4 | tests/persistAsync.test.tsx (29 lines) |
| zustand-t02--vanilla--sonnet--r2 | 15.2x | 61 | 4 | tests/persistSync.test.tsx (57 lines) |
| zustand-t02--claudemd--sonnet--r1 | 13.8x | 55 | 4 | tests/persistSync.test.tsx (51 lines) |
| zustand-t02--vanilla--sonnet--r3 | 11.2x | 45 | 4 | tests/persistSync.test.tsx (41 lines) |
| zustand-t02--claudemd--sonnet--r2 | 10.0x | 40 | 4 | tests/persistSync.test.tsx (36 lines) |
| zustand-t02--vanilla--sonnet--r1 | 9.8x | 39 | 4 | tests/persistSync.test.tsx (35 lines) |
| hono-t04--vanilla--sonnet--r2 | 5.6x | 28 | 5 | src/utils/url.test.ts (26 lines) |
| click-t02--vanilla--sonnet--r1 | 5.1x | 41 | 8 | tests/test_shell_completion.py (33 lines) |
| click-t02--claudemd--sonnet--r2 | 5.0x | 40 | 8 | tests/test_shell_completion.py (28 lines) |
| hono-t04--vanilla--sonnet--r1 | 5.0x | 25 | 5 | src/utils/url.test.ts (23 lines) |
| click-t02--claudemd--sonnet--r1 | 4.9x | 39 | 8 | tests/test_shell_completion.py (28 lines) |
| zod-t05--claudemd--sonnet--r3 | 4.8x | 658 | 136 | packages/zod/src/v4/classic/from-json-schema.ts (601 lines) |
| click-t02--vanilla--sonnet--r2 | 4.6x | 37 | 8 | tests/test_shell_completion.py (29 lines) |
| click-t02--vanilla--sonnet--r3 | 4.5x | 36 | 8 | tests/test_shell_completion.py (28 lines) |
| click-t02--claudemd--sonnet--r3 | 4.5x | 36 | 8 | tests/test_shell_completion.py (25 lines) |
| hono-t04--vanilla--sonnet--r3 | 4.2x | 21 | 5 | src/utils/url.test.ts (19 lines) |
| hono-t04--claudemd--sonnet--r1 | 3.6x | 18 | 5 | src/utils/url.test.ts (16 lines) |
| hono-t04--claudemd--sonnet--r2 | 3.6x | 18 | 5 | src/utils/url.test.ts (16 lines) |
| hono-t04--claudemd--sonnet--r3 | 3.6x | 18 | 5 | src/utils/url.test.ts (16 lines) |
| zod-t01--claudemd--sonnet--r3 | 3.2x | 32 | 10 | packages/zod/src/v4/classic/tests/string.test.ts (30 lines) |

Outliers by arm: vanilla 9, claudemd 11.

Interpretation guardrails: T-real prompts sometimes legitimately ask for tests the human PR lacked; a high ratio flags volume, not necessarily waste. Manual-review dispositions belong in the interim writeup.

