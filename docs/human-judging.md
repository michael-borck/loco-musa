# Human judging guide

You are the calibration layer: your votes tell everyone how much to trust the
automated judge. Aim for ~10 packets, 15–30 minutes.

## The flow

1. The maintainer gives you `human/packet/NNN-<task>.md` files and a copy of
   `human/votes.example.yaml` (rename to `votes.yaml`).
2. For each packet: read the original prompt, the judging criteria, then both
   responses (A and B). **Model names are hidden on purpose** — don't try to
   guess by style; vote on the content against the criteria.
3. In `votes.yaml`, record for each `packet_id`: `winner: a`, `b`, or `tie`.
   - `tie` means genuinely comparable quality — but don't hide behind it. If
     one response would actually help *you* think better next, pick it.

## What "better thinking partner" means

You are not scoring essays. For each packet, ask:

- **Would this change my next thought?** — did it surface something you hadn't
  considered, reframe the question, or sharpen a vague idea?
- **Does it build or restart?** (multi-turn packets) — does each answer use
  what you said before, or could it have been written cold?
- **Does it respect you?** — pushes back where you're shaky without lecturing;
  doesn't flatter; doesn't pad.
- **Would you repeat it?** — is there a line you'd tell someone about later?
  That's usually the winner.

## After voting

Hand back `votes.yaml`. The maintainer runs:

```bash
python -m runner.human_votes score human/votes.yaml
```

and you'll see agreement per packet. Disagreements aren't errors — they're the
measurement. A pattern of disagreements on one task usually means the task's
rubric is broken, not you.
