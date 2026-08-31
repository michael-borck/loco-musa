"""Pairwise, blind, position-swapped LLM-as-judge for the judged/dialogue tiers.

Every pair is judged twice with positions swapped; disagreements become ties.
Writes a timestamped judgements file under results/.

Usage:
    python -m runner.judge results/modelA/<run> results/modelB/<run> [more runs...]
        --judge-base-url https://api.anthropic.com/v1 --judge-model claude-sonnet-4-5
"""

import argparse
import json
import random
import re
import time
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

from .client import api_key_from, chat
from .tasks import load_tasks, task_index

JUDGE_SYSTEM = (
    "You are a meticulous evaluator comparing two AI responses as a thinking "
    "partner. Be discerning, not generous: most pairs have a real difference in "
    "quality. Answer only with the requested JSON."
)

JUDGE_TEMPLATE = """You are comparing two unseen responses to the same task.

## TASK GIVEN TO THE MODEL
{task_text}

## EVALUATION GUIDANCE
{rubric}
{dimensions}

## RESPONSE A
{response_a}

## RESPONSE B
{response_b}

## YOUR JOB
Which response is the better thinking partner for the person who asked? Apply the
guidance above. If both are equally good or equally weak, say "tie" — do not
default to A.

Respond with ONLY a JSON object:
{{"winner": "A", "B", or "tie", "reasoning": "at most 120 words"}}"""


def task_text(task):
    parts = [" ".join(task["prompt"].split())]
    if task.get("turns"):
        parts.append("\nFOLLOW-UP USER TURNS (fixed, same for both models):")
        parts += [f"  {i}. {' '.join(t.split())}" for i, t in enumerate(task["turns"], 1)]
    return "\n".join(parts)


def rubric_text(task):
    parts = []
    if task.get("rubric"):
        parts.append("Rubric: " + " ".join(task["rubric"].split()))
    dims = task.get("dimensions") or []
    if dims:
        parts.append("Score dimensions:")
        parts += [f"  - {d['name']}: {d.get('description', '')}" for d in dims]
    return "\n".join(parts) or "No rubric: judge general thinking-partner quality."


def transcript_text(messages, with_user=True):
    lines = []
    for m in messages:
        if m["role"] == "assistant":
            lines.append(f"ASSISTANT: {m['content']}")
        elif with_user:
            lines.append(f"USER: {m['content']}")
    return "\n\n".join(lines)


def parse_verdict(raw):
    m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not m:
        return "tie", raw
    try:
        data = json.loads(m.group(0))
        winner = str(data.get("winner", "tie")).strip().upper()
        if winner not in ("A", "B", "TIE"):
            winner = "tie"
        return winner, data.get("reasoning", "")
    except json.JSONDecodeError:
        return "tie", raw


def judge_pair(task, a_text, b_text, judge_cfg):
    prompt = JUDGE_TEMPLATE.format(
        task_text=task_text(task), rubric=rubric_text(task),
        dimensions="", response_a=a_text, response_b=b_text)
    raw = chat(judge_cfg["base_url"], judge_cfg["model"],
               [{"role": "system", "content": JUDGE_SYSTEM},
                {"role": "user", "content": prompt}],
               api_key=judge_cfg["api_key"],
               temperature=judge_cfg["temperature"], max_tokens=512)
    return parse_verdict(raw)


def load_run(run_dir):
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run.json").read_text())
    transcripts = json.loads((run_dir / "transcripts.json").read_text())
    by_task = {r["task_id"]: r for r in transcripts if not r.get("error")}
    return meta["model"], by_task


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dirs", nargs="+",
                    help="two or more run directories to compare")
    ap.add_argument("--judge-base-url", required=True)
    ap.add_argument("--judge-model", required=True)
    ap.add_argument("--api-key-env", default=None)
    ap.add_argument("--tasks-dir", default="tasks")
    ap.add_argument("--results-dir", default="results")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--no-swap", action="store_true",
                    help="judge each pair once (A/B order as given) instead of twice")
    args = ap.parse_args()

    if len(args.run_dirs) < 2:
        raise SystemExit("need at least two runs to compare")

    judge_cfg = {"base_url": args.judge_base_url, "model": args.judge_model,
                 "api_key": api_key_from(args.api_key_env),
                 "temperature": args.temperature}

    tasks = task_index(t for t in load_tasks(args.tasks_dir) if t["tier"] in ("judged", "dialogue"))
    runs = {str(p): load_run(p) for p in args.run_dirs}

    print(f"judge: {args.judge_model} | models: "
          f"{sorted({m for m, _ in runs.values()})}")
    records, calls = [], 0
    for run_a, run_b in combinations(sorted(runs), 2):
        model_a, transcripts_a = runs[run_a]
        model_b, transcripts_b = runs[run_b]
        shared = sorted(set(transcripts_a) & set(transcripts_b) & set(tasks))
        for task_id in shared:
            task = tasks[task_id]
            ta = transcript_text(transcripts_a[task_id]["messages"])
            tb = transcript_text(transcripts_b[task_id]["messages"])
            call_log = []
            orders = [("a", "b")] if args.no_swap else [("a", "b"), ("b", "a")]
            verdicts = []
            for first, second in orders:
                if first == "a":
                    pos_a, pos_b, name_a, name_b = ta, tb, model_a, model_b
                else:
                    pos_a, pos_b, name_a, name_b = tb, ta, model_b, model_a
                t0 = time.time()
                verdict, reasoning = judge_pair(task, pos_a, pos_b, judge_cfg)
                calls += 1
                call_log.append({"position_a": name_a, "position_b": name_b,
                                 "verdict": verdict, "reasoning": reasoning,
                                 "seconds": round(time.time() - t0, 1)})
                verdicts.append((verdict, name_a, name_b))
                print(f"  {task_id}: {model_a} vs {model_b} [{first} first] -> {verdict}")
            # reconcile swapped orders: disagreement = tie
            if verdicts[0][0] != verdicts[1][0]:
                winner = "tie"
            else:
                winner = "tie" if verdicts[0][0] == "TIE" else verdicts[0][1]
            records.append({"task_id": task_id,
                            "category": task.get("category"),
                            "tier": task["tier"],
                            "model_x": model_a, "model_y": model_b,
                            "winner": winner, "calls": call_log})

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out = Path(args.results_dir) / f"judgements-{stamp}.json"
    out.write_text(json.dumps({
        "judge_model": args.judge_model,
        "timestamp_utc": stamp,
        "swap": not args.no_swap,
        "records": records,
    }, indent=2))
    print(f"{len(records)} pair-judgements ({calls} judge calls) -> {out}")


if __name__ == "__main__":
    main()
