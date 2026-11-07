---
title: "Authoring tasks"
description: "How to add a task to the benchmark."
---

Tasks are YAML files under `tasks/<tier>/<category>/<id>.yaml`, with no code per task.
The bench is deliberately small: **add a task only if you'd vouch for it
personally**. One task you believe in beats ten you threw in.

## Common fields

```yaml
id: unique-slug            # required, stable; changing it breaks history
tier: auto | judged | dialogue
category: free-text-slug   # e.g. brainstorming, reframing, steelman
weight: 1.0                # relative weight within its tier
system: optional system prompt
prompt: |
  The task given to the model.
```

Prompts are collapsed (`" ".join(prompt.split())`) before sending. Write them
for reading; they travel as one line.

## auto tier: `checks`

A list of named checks; the task's score is the mean of check scores.

| checker | args | what it does |
|---|---|---|
| `word_count` | `min`, `max` | total words in bounds |
| `forbidden_chars` | `chars` | no listed character anywhere |
| `includes_phrases` | `phrases` | all phrases present (case-insensitive) |
| `includes_any` | `patterns` (regex), `min_hits` | at least `min_hits` patterns match; planted-flaw detection |
| `item_constraints` | `count`, `max_words`, `forbidden_letters`, `unique` | numbered-list properties |
| `line_constraints` | `count`, `max_words` | plain line properties |
| `acrostic` | `word` | first letters of lines spell the word |
| `sorted_order` | `direction: asc/desc` | numbered items sorted |
| `numeric_answer` | `answer`, `pattern` | last regex match equals answer |
| `pairs_in_sentence` | `pairs`, `window: last` | word pairs co-occur in one line |

Design notes for auto tasks:

- Constraints should be **load-bearing for creativity**: "10 names with no letter e"
  forces divergence; "write 10 names in ≤20 words" doesn't.
- Always test your task against a frontier model and a small local model before
  committing. If the frontier model scores below ~0.8, the check is probably
  miscalibrated.

## judged tier: `dimensions` + `rubric`

```yaml
dimensions:
  - name: divergence
    weight: 1.0
    description: what this dimension means, concretely
rubric: |
  Guidance addressed to the judge: what the great response does, what the
  mediocre one does, what to penalise.
```

The judge receives prompt + follow-ups (if any) + dimensions + rubric verbatim.
Good rubrics name the *mediocre* response explicitly ("the mediocre response
gives productivity tips"). That is what lifts judge-human agreement.

**Hybrid tasks**: a judged/dialogue task may also carry `checks`. The checks are
scored deterministically by `check_auto` (and count toward the model's auto
score), while the substance is judged pairwise. Use the auto layer for anything
a regex can verify (verdict lines, planted-flaw diagnosis, format contracts)
and leave judgment about quality to the judge. If the checker can pass while the
response is garbage, the checker is testing the wrong thing.

## dialogue tier: `turns`

`turns` is a list of fixed user follow-ups. Fixed turns are what make multi-turn
comparable across models: everyone gets the same conversation partners' moves.
Write follow-ups that escalate ("now steelman the opposite", "give me one weird
option", "what's the cheapest test?"). They probe whether the model builds on
context or restarts each turn.

## Acceptance checklist

- [ ] Runs clean against one frontier + one local model
- [ ] Frontier model scores ≥0.8 on auto checks (if auto)
- [ ] Rubric distinguishes two responses you personally rate differently
- [ ] No trivia, no ambiguity in auto answers
- [ ] Would you show this task to a model author as fair?
