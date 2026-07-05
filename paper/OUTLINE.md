# Paper outline

**Working title:** Enforced Intent: A Controlled Evaluation of Injection, Deny Rules, and CI Gating for AI Coding Agents on Real Repositories

**Venue:** arXiv cs.SE preprint. Methodology source of truth: `docs/10-evaluation-plan.md` in the venture repo; the frozen version is `preregistration/prereg-v1.md` here.

## 1. Introduction

- The prevalence anchor: developer-constraint violation is the #1 misalignment symptom in real coding-agent sessions, 38.3% of 20,574 episodes (Tang et al., arXiv:2605.29442), and 91.5% of resolutions required explicit developer pushback.
- The open tension: passive context files (AGENTS.md/CLAUDE.md) are followed but do not improve outcomes and add ~20% inference cost (arXiv:2602.11988), while compiled guardrails improved compliance on synthetic constraint files (ContextCov, arXiv:2603.00822). Does enforcement of real, work-item-shaped intent pay?
- Contributions: (1) first controlled evaluation of enforced intent (session injection + deterministic deny + CI gate) on real repositories with real work items; (2) the T-bait instrument for measuring disciplined refusal; (3) drift-attributed token economy under enforcement; (4) pre-registered, fully reproducible, subscription-scale harness.

## 2. Related work

- Outcome benchmarks and their limits: SWE-bench Verified deprecation (OpenAI), contamination/memorization (arXiv:2506.12286), SWE-bench Live/Pro, Terminal-Bench.
- Instruction adherence: OctoBench (arXiv:2601.10343, compliance inside fixed scaffolds, no enforcement), AgentIF (arXiv:2505.16944), ODCV-Bench (arXiv:2512.20798, judge panels).
- Enforcement systems: ContextCov (closest; differentiate: synthetic constraints, no work-item scope, no CI gate, no token analysis).
- Field evidence and rigor templates: Tang et al.; METR RCT (arXiv:2507.09089, perceived productivity inadmissible).

## 3. System under test

pylgrim's loop (remember / steer / review) summarized; product laws as design constraints on the evaluation itself (facts gate, opinions advise; nothing unratified injected; never writes code; no per-person scores).

## 4. Methodology

Pre-registration; corpus (§4 of the eval plan); task cards incl. T-real and T-bait; arms A/B/C with the stated-constraints prompt design; metrics M1-M6; arm-blind final-diff judging with founder calibration (Cohen's kappa); statistics (paired Wilcoxon, cluster bootstrap by repo, Holm-Bonferroni, pre-registered non-inferiority margins).

## 5. Results

- 5.1 Drift in the wild (Wave 1 descriptive: vanilla agents on real tasks)
- 5.2 Passive injection (A vs B: the AGENTS.md replication on real constraints)
- 5.3 Enforcement (B vs C, C vs A: H1)
- 5.4 Token economy (H2, drift-attributed tokens)
- 5.5 Model-tier effects (H5, exploratory)
- 5.6 Skills artifact quality (H4)
- Bridge analysis (Wave 1 vs Wave 2 arm A temporal stability)

## 6. Threats to validity

Same-family judge and self-preference; temporal drift between waves; contamination (recorded per task); honeypot artificiality (T-real vs T-bait never pooled silently); author-curated tasks (freeze rule + public artifacts); single host/subscription; one vendor.

## 7. Limitations and future work

Cross-vendor agents post-beta; team/multi-agent settings; longitudinal ratchet effects (does the ledger compound?).

## Appendices

Task-card schema; per-repo rule sets; judge prompts and rubric; calibration agreement tables; per-repo result tables; amendments log.

## Writing rules

No em-dashes. Every number traces to the results database or a §11 primary source. Null results publish. "pylgrim ensures alignment"; it never "fixes".
