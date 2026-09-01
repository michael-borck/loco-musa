"""Score the auto tier of a run deterministically.

Usage:
    python -m runner.check_auto results/qwen3-8b/20260831-101500-a1b2c3
"""

import argparse
import json
from pathlib import Path

from .checkers import run_checks
from .tasks import load_tasks, task_index


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("run_dir", help="a run directory containing transcripts.json")
    ap.add_argument("--tasks-dir", default="tasks")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    transcripts = json.loads((run_dir / "transcripts.json").read_text())
    tasks = task_index(load_tasks(args.tasks_dir))

    per_task = {}
    scored = 0
    for rec in transcripts:
        task = tasks.get(rec["task_id"])
        # hybrid tasks (judged/dialogue with `checks`) score here too:
        # constraints are deterministic, substance is judged separately.
        if not task or not task.get("checks"):
            continue
        if rec.get("error") or not rec.get("messages"):
            per_task[rec["task_id"]] = {"score": 0.0, "error": rec.get("error")}
            continue
        final = rec["messages"][-1]["content"]
        score, detail = run_checks(final, task.get("checks", []))
        per_task[rec["task_id"]] = {"score": round(score, 3), "checks": detail}
        scored += 1

    auto_score = (sum(v["score"] for v in per_task.values()) / len(per_task)
                  if per_task else 0.0)
    out = {"auto_score": round(auto_score, 3), "tasks_scored": scored,
           "per_task": per_task}
    (run_dir / "auto_scores.json").write_text(json.dumps(out, indent=2))
    print(f"auto score: {auto_score:.3f} across {len(per_task)} tasks -> {run_dir / 'auto_scores.json'}")


if __name__ == "__main__":
    main()
