# Methodology

How loco-musa produces scores it is willing to defend.

## The measurement problem

"Ideation quality" has no ground truth. Two failure modes dominate naive attempts:

1. **Absolute scoring** ("rate this brainstorm 1–10") — judges drift, centralise
   scores, and punish/harsh differently across runs. Published evaluations
   (MT-Bench §"limitations", Arena-Hard's ablations, WildBench's human-validation
   sections) all converge on the same fix: **ask for preferences, not ratings**.
2. **Self-preference and position bias** — a judge prefers its own style, and
   prefers whichever answer it reads first.

loco-musa's design answers each failure mode explicitly.

## Tier 1: auto — deterministic

Tasks with a checkable property (constraints, formats, determinate answers) are
scored by code in `runner/checkers.py`. Scores are fractional (fraction of items
complying, fraction of constraint-letter matches), so near-misses still carry
signal. Auto tasks are ~40% of the pool and anchor the leaderboard in something
no judge can hallucinate.

## Tier 2 & 3: judged / dialogue — pairwise, blind, swapped

For each pair of models on each task:

1. **Blind** — the judge sees "Response A / Response B", never model names.
2. **Position swap** — the pair is judged twice, positions reversed. If the two
   calls disagree, the record becomes a **tie**. A model must win in both
   positions to win the record. This is the standard mitigation for position bias.
3. **Rubric-anchored** — every task carries dimensions and a rubric in its YAML,
   so the judge evaluates the task's intent ("did it reframe?", "did it ask
   before dumping?") rather than generic good-writing vibes.
4. **Deterministic judge settings** — temperature 0 for the judge.

Judge output is strict JSON (`winner: A|B|tie` + ≤120-word reasoning), parsed and
stored per call in the judgements file, so disagreements can be audited later.

## Anchors: calibration against frontier models

`anchors.yaml` lists frontier models run through the identical pipeline. All
pairwise records feed a **Bradley–Terry** fit (Zermelo iterations, pure Python in
`runner/build_leaderboard.py`); strengths are rescaled so the **mean anchor
rating is 100**. A local model at 63 means "about 63% of frontier-calibrated
quality by this pool's pairwise preference" — a statement that survives judge
quirks far better than an absolute number, because both compared models suffer
the same judge.

With no anchors configured, ratings normalise to pool mean 100 and are only
valid *within* that pool.

## Humans: validating the judge

`runner.human_votes make-packet` samples blind A/B packets from run
directories; the model↔position mapping is kept in `human/packet-key.json`
(gitignored). Humans vote `a/b/tie` in `human/votes.yaml`.

`runner.human_votes score` then reports:

- **agreement** — fraction of human votes matching the judge's reconciled winner
- **Cohen's kappa** (non-tie votes) — agreement corrected for chance

These land in `results/human/agreement.json` and are published on the
leaderboard as `human_judge_agreement`. Interpretation guide:

| kappa | reading |
|---|---|
| ≥ 0.6 | judge trustworthy; leaderboard order is meaningful |
| 0.4–0.6 | use with caution; treat <5% gaps as noise |
| < 0.4 | fix the rubric or the judge before trusting anything |

Aim for 20–30 human votes per calibration round across ≥2 voters.

## Known biases we do NOT fully fix

- **Verbosity bias** — judges tend to prefer longer answers. Rubrics that reward
  restraint (e.g. `clarify-first`) partially counteract this.
- **Self-preference** — if the judge model family is also a candidate, exclude
  that pair from anchors or at least flag it.
- **Style/temperature sensitivity of candidates** — candidates run at
  temperature 0.7, single sample. Re-run finals and average if a decision matters.
- **Small pool** — ~15 tasks, 3 tiers. Gaps under ~5 bt-points are noise.
  This bench is for coarse, opinionated comparisons, not decimal places.

## Run protocol (suggested)

1. Run all candidates + anchors (same day, same task set).
2. `check_auto` each candidate run.
3. `judge` all run pairs.
4. `build_leaderboard` → commit `results/`, `leaderboard.json`.
5. Quarterly: fresh `make-packet`, collect 20+ human votes, re-validate.
