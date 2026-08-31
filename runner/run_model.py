"""Run all tasks against a model via any OpenAI-compatible endpoint.

Usage:
    python -m runner.run_model --base-url http://localhost:11434/v1 --model qwen3:8b
"""

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .client import api_key_from, chat
from .tasks import load_tasks


def slug(name):
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in name).strip("-").lower()


def build_messages(task):
    """Initial message list for a task (dialogue tasks get extended per turn)."""
    messages = []
    if task.get("system"):
        messages.append({"role": "system", "content": task["system"]})
    messages.append({"role": "user", "content": " ".join(task["prompt"].split())})
    return messages


def run_task(task, base_url, model, api_key, temperature, max_tokens):
    messages = build_messages(task)
    turns = [messages[-1]["content"]] + [" ".join(t.split()) for t in task.get("turns", [])]
    for i, user_text in enumerate(turns):
        if i > 0:
            messages.append({"role": "user", "content": user_text})
        reply = chat(base_url, model, messages, api_key=api_key,
                     temperature=temperature, max_tokens=max_tokens)
        messages.append({"role": "assistant", "content": reply})
    return messages


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--model", required=True)
    ap.add_argument("--api-key-env", default=None,
                    help="env var holding the API key (if any)")
    ap.add_argument("--tasks-dir", default="tasks")
    ap.add_argument("--results-dir", default="results")
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--max-tokens", type=int, default=2048)
    ap.add_argument("--tier", choices=["auto", "judged", "dialogue"], default=None,
                    help="run only one tier")
    ap.add_argument("--category", default=None, help="run only one category")
    args = ap.parse_args()

    tasks = load_tasks(args.tasks_dir)
    if args.tier:
        tasks = [t for t in tasks if t["tier"] == args.tier]
    if args.category:
        tasks = [t for t in tasks if t.get("category") == args.category]
    if not tasks:
        raise SystemExit("no tasks matched")

    api_key = api_key_from(args.api_key_env)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = f"{stamp}-{hashlib.sha1(args.model.encode()).hexdigest()[:6]}"
    run_dir = Path(args.results_dir) / slug(args.model) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"running {len(tasks)} tasks -> {run_dir}")
    transcripts, failures = [], 0
    for task in tasks:
        t0 = time.time()
        record = {
            "task_id": task["id"],
            "tier": task["tier"],
            "category": task.get("category"),
            "turns": task.get("turns", []),
            "messages": None,
            "error": None,
            "seconds": None,
        }
        try:
            record["messages"] = run_task(
                task, args.base_url, args.model, api_key,
                args.temperature, args.max_tokens)
        except Exception as exc:  # keep going; record the failure
            record["error"] = f"{type(exc).__name__}: {exc}"
            failures += 1
            print(f"  FAIL {task['id']}: {record['error']}")
        record["seconds"] = round(time.time() - t0, 1)
        transcripts.append(record)
        if record["messages"]:
            print(f"  ok   {task['id']} ({record['seconds']}s)")

    meta = {
        "model": args.model,
        "base_url": args.base_url,
        "temperature": args.temperature,
        "max_tokens": args.max_tokens,
        "run_id": run_id,
        "timestamp_utc": stamp,
        "tasks": len(tasks),
        "failures": failures,
    }
    (run_dir / "run.json").write_text(json.dumps(meta, indent=2))
    (run_dir / "transcripts.json").write_text(json.dumps(transcripts, indent=2))
    print(f"done: {len(tasks) - failures}/{len(tasks)} ok")


if __name__ == "__main__":
    main()
