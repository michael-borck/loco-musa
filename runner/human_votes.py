"""Human blind-voting packets and judge-agreement scoring.

Two modes:

  make-packet: sample blind A/B packets from run directories for human judging
      python -m runner.human_votes make-packet --runs results/A/<run> results/B/<run> --n 12

  score: score human votes against the packet key AND the judge's verdicts
      python -m runner.human_votes score human/votes.yaml

Humans never see model names: packets show "Response A/B"; the mapping lives in
human/packet-key.json (kept out of the leaderboard path).
"""

import argparse
import json
import random
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import yaml

from .judge import rubric_text, task_text, transcript_text
from .tasks import load_tasks, task_index


def _load_run(run_dir):
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run.json").read_text())
    transcripts = json.loads((run_dir / "transcripts.json").read_text())
    return meta["model"], {r["task_id"]: r for r in transcripts if not r.get("error")}


def make_packet(args):
    tasks = task_index(t for t in load_tasks(args.tasks_dir) if t["tier"] in ("judged", "dialogue"))
    runs = {str(p): _load_run(p) for p in args.runs}
    # pairs of (model_name, transcript) that share a task
    combos = []
    for (path_a, path_b) in combinations(sorted(runs), 2):
        ma, ta = runs[path_a]
        mb, tb = runs[path_b]
        for task_id in sorted(set(ta) & set(tb) & set(tasks)):
            combos.append((task_id, ma, ta[task_id]["messages"], mb, tb[task_id]["messages"]))
    rng = random.Random(args.seed)
    rng.shuffle(combos)
    combos = combos[: args.n]

    out_dir = Path(args.packet_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    key = []
    for i, (task_id, ma, msg_a, mb, msg_b) in enumerate(combos, 1):
        if rng.random() < 0.5:
            ma, mb, msg_a, msg_b = mb, ma, msg_b, msg_a
        pid = f"{i:03d}-{task_id}"
        task = tasks[task_id]
        body = (
            f"# Blind packet {pid}\n\n"
            f"## Original prompt\n{task_text(task)}\n\n"
            f"## What to judge\n{rubric_text(task)}\n\n"
            f"## Response A\n{transcript_text(msg_a)}\n\n"
            f"## Response B\n{transcript_text(msg_b)}\n\n"
            f"---\nYour vote: `winner: a`, `b`, or `tie` in votes.yaml for packet_id `{pid}`.\n"
        )
        (out_dir / f"{pid}.md").write_text(body)
        key.append({"packet_id": pid, "task_id": task_id,
                    "model_a": ma, "model_b": mb})
    (Path(args.packet_dir).parent / "packet-key.json").write_text(json.dumps(key, indent=2))
    print(f"{len(key)} blind packets -> {out_dir}")
    print("next: scorers fill human/votes.yaml, then: "
          "python -m runner.human_votes score human/votes.yaml")


def score(args):
    votes = yaml.safe_load(Path(args.votes_file).read_text())
    key = {k["packet_id"]: k for k in json.loads(Path(args.packet_key).read_text())}

    # latest judgements file, all records by (task, frozenset(models))
    judged = {}
    for jf in sorted(Path(args.results_dir).glob("judgements-*.json")):
        data = json.loads(jf.read_text())
        for rec in data["records"]:
            judged[(rec["task_id"], frozenset((rec["model_x"], rec["model_y"])))] = rec["winner"]

    agreement, n, kappa_pairs = [], 0, []
    for vote in votes.get("votes", []):
        k = key.get(vote["packet_id"])
        if not k:
            print(f"  ?? unknown packet {vote['packet_id']}")
            continue
        human = str(vote["winner"]).lower()
        human_pick = {"a": k["model_a"], "b": k["model_b"], "tie": "tie"}.get(human)
        judge_pick = judged.get((k["task_id"], frozenset((k["model_a"], k["model_b"]))))
        if judge_pick is None:
            print(f"  ?? no judge verdict for {k['packet_id']}")
            continue
        n += 1
        ok = human_pick == judge_pick
        agreement.append(ok)
        kappa_pairs.append((human_pick, judge_pick))
        print(f"  {'ok ' if ok else 'X  '} {k['packet_id']}: human={human_pick} judge={judge_pick}")

    result = {
        "voter": votes.get("voter"),
        "updated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_votes": n,
        "agreement": round(sum(agreement) / n, 3) if n else None,
    }
    if len(kappa_pairs) >= 2:
        result["kappa"] = _cohens_kappa(kappa_pairs)
    Path(args.results_dir, "human", "agreement.json").parent.mkdir(parents=True, exist_ok=True)
    Path(args.results_dir, "human", "agreement.json").write_text(json.dumps(result, indent=2))
    print(f"agreement: {result.get('agreement')} over {n} votes"
          + (f" (kappa {result['kappa']})" if "kappa" in result else ""))


def _cohens_kappa(pairs):
    """Cohen's kappa over non-tie picks only (tie/tie excluded as uninformative)."""
    pairs = [(h, j) for h, j in pairs if h != "tie" and j != "tie"]
    if len(pairs) < 2:
        return None
    labels = {l for p in pairs for l in p}
    po = sum(h == j for h, j in pairs) / len(pairs)
    pe = sum(
        (sum(h == l for h, _ in pairs) / len(pairs))
        * (sum(j == l for _, j in pairs) / len(pairs))
        for l in labels)
    return round((po - pe) / (1 - pe), 3) if pe < 1 else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="mode", required=True)

    p = sub.add_parser("make-packet")
    p.add_argument("--runs", nargs="+", required=True)
    p.add_argument("--tasks-dir", default="tasks")
    p.add_argument("--n", type=int, default=12)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--packet-dir", default="human/packet")
    p.set_defaults(func=make_packet)

    p = sub.add_parser("score")
    p.add_argument("votes_file", nargs="?", default="human/votes.yaml")
    p.add_argument("--packet-key", default="human/packet-key.json")
    p.add_argument("--results-dir", default="results")
    p.set_defaults(func=score)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
