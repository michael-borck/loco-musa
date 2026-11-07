# loco-musa

**How good is the model to think with?**

**Site:** [locomusa.org](https://locomusa.org)

loco-musa is a small, curated benchmark for local LLMs that measures **thinking-partner
quality**: ideation, reframing, steelmanning, and multi-turn conversation. It complements
[loco-banco](https://github.com/michael-borck/loco-banco) (which measures precision
knowledge and reasoning with deterministic benchmarks) by measuring how well a local model
works as a *thinking partner*.

## The philosophy: conversation as thinking

Writing has long been understood as a form of thinking as well as a record of thought
(Langer & Applebee, *How Writing Shapes Thinking*, 1987). loco-musa extends the idea:
**conversation-with-AI as thinking**. A good local model makes *your* next thought
better, even when it gives a less precise answer. It offers a tenth idea after you had
nine, reframes the problem you brought it, and pushes back before agreeing.

So this bench scores:

- **Divergence:** does it generate a range of answers instead of one safe answer?
- **Reframing:** does it find a better question than the one you asked?
- **Pushback:** can it steelman the position you didn't take?
- **Dialogue:** across turns, does it build and escalate without restarting?

> **Name note:** unrelated to Salesforce's *LoCoBench* (long-context software
> engineering) despite the similar name. The `loco-` prefix here belongs to the
> [LocoLabo](https://locolabo.org) family.

## How it works: three tiers

| Tier | What | Scoring |
|---|---|---|
| **auto** | Tasks with checkable answers (constraints, formats, determinate puzzles) | Code. Fully automated. |
| **judged** | Open-ended single turns (brainstorming, reframing, steelmanning, socratic, persona) | **Pairwise, blind**: a frontier-model judge compares two responses; position randomized and swapped. Humans spot-check a sample to validate the judge. |
| **dialogue** | Scripted 3-4 turn conversations with fixed follow-ups | Same pairwise judging, over full transcripts. |

**Hybrid tasks**: judged/dialogue tasks may also carry `checks`. The constraints
are scored deterministically (did the review end with a verdict? did it
diagnose the planted bug?) while substance is judged pairwise. Both signals land
on the leaderboard.

Why pairwise? Research on LLM-as-judge (MT-Bench, Arena-Hard, WildBench) consistently
shows judges are unreliable at absolute 1-10 scoring but reliable at choosing A vs B.
Humans score a sample of pairs; judge-human agreement is published on the leaderboard
so you know how much to trust it.

## Calibration against frontier models

Every run should include 1-3 frontier models (via API) as **anchors**. They are judged
in the same pool, blind. This converts scores into something meaningful:

> "Qwen3-8B reaches ~70% of Claude-anchored ideation quality and beats GPT-4o-2023 on
> reframing." That is more useful than "scored 3.8/5".

Anchors are marked on the leaderboard. Anchor-relative ratings normalize the pool.

## Quick start

Requires Python 3.10+, `requests`, `pyyaml`, and any OpenAI-compatible endpoint
(ollama, llama.cpp server, LM Studio, vLLM...).

```bash
# 1. Run a local model through all tasks
python -m runner.run_model --base-url http://localhost:11434/v1 --model qwen3:8b

# 2. Run a frontier anchor (same pipeline, different endpoint)
python -m runner.run_model --base-url https://api.anthropic.com/v1 --model claude-sonnet-4-5 --api-key-env ANTHROPIC_API_KEY

# 3. Score the auto tier (deterministic)
python -m runner.check_auto results/qwen3-8b/<run-id>

# 4. Judge the judged/dialogue tiers pairwise (blind, position-swapped)
python -m runner.judge results/qwen3-8b/<run-id> results/claude-sonnet-4-5/<run-id> \
    --judge-base-url https://api.anthropic.com/v1 --judge-model claude-sonnet-4-5

# 5. Validate the judge with human votes (see docs/human-judging.md)
python -m runner.human_votes human/votes.yaml

# 6. Rebuild the leaderboard
python -m runner.build_leaderboard
```

`leaderboard.json` is the scoreboard: regenerated per run, committed with the results,
plain JSON so any site can fetch it.

## Repository layout

```
tasks/
  auto/                  # deterministic scoring; each task names a checker
  judged/                # pairwise scoring; each task carries a rubric
  dialogue/              # scripted multi-turn; pairwise on transcripts
runner/                  # harness: run, check, judge, aggregate
results/<model>/<run>/   # transcripts, scores, judgements (committed)
human/votes.yaml         # human pairwise votes (blind packets)
leaderboard.json         # the scoreboard
docs/                    # methodology, task authoring, human judging
```

## Task authoring

Tasks are plain YAML, with no code per task. A handful of generic checkers
(`forbidden_letters`, `acrostic`, `item_constraints`, `numeric_answer`, ...) cover the
auto tier. See [docs/authoring.md](docs/authoring.md). The set is deliberately small and
curated: every task should be one you'd vouch for personally.

## Design decisions (and why)

- **Pairwise over absolute:** judge reliability. See docs/methodology.md.
- **Position swap:** every pair is judged twice, A-then-B and B-then-A; disagreements become ties.
- **Small curated set (~18 seeds):** human-scoreable, re-runnable, opinionated.
- **Git as scoreboard CMS:** results and leaderboard.json are committed artifacts; no database, any frontend can fetch the JSON.
- **Complements loco-banco:** hard metrics live there; this repo never re-measures MMLU.

## Limitations

- Judge bias exists (verbosity, style, self-preference). The position swap and human
  agreement checks reduce the effect but do not remove it.
- A small task set gives wider confidence intervals. Treat score gaps under ~5% as noise.
- Single-run variance is real for small models; re-run finals 3× if a decision matters.

## Related projects

- [loco-banco](https://github.com/michael-borck/loco-banco): deterministic benchmarks by VRAM tier (the "how smart" half)
- [loco-agente](https://github.com/michael-borck/loco-agente): the conversational harness: muse measures whether raw models already think well; agente engineers it when they don't
- [MT-Bench](https://arxiv.org/abs/2306.05685), [Arena-Hard](https://github.com/lm-sys/FastChat), [WildBench](https://github.com/allenai/WildBench): the judge-based evaluation patterns this repo borrows

## License

MIT. See [LICENSE](LICENSE).
