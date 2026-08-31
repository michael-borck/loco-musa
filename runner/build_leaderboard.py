"""Aggregate auto scores + pairwise judgements into leaderboard.json.

Bradley-Terry ratings are normalized so that the mean anchor rating is 100
(and, absent anchors, the mean of all models is 100).

Usage:
    python -m runner.build_leaderboard            # uses anchors.yaml if present
    python -m runner.build_leaderboard --anchor claude-sonnet-4-5 --anchor gpt-4o
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_runs(results_dir):
    """model -> latest auto_scores.json"""
    autos = {}
    if not (results_dir / "auto_scores.json").exists():
        for run_dir in sorted(results_dir.glob("*/*/")):
            f = run_dir / "auto_scores.json"
            if f.exists():
                data = json.loads(f.read_text())
                autos[run_dir.parent.name] = data.get("auto_score")
    else:  # results dir itself is a run dir
        data = json.loads((results_dir / "auto_scores.json").read_text())
        autos[results_dir.parent.name] = data.get("auto_score")
    return autos


def load_judgements(results_dir):
    """Aggregate all judgements files into wins/losses/ties per model."""
    stats, judge_model = {}, None
    for jf in sorted(results_dir.glob("judgements-*.json")):
        data = json.loads(jf.read_text())
        judge_model = data.get("judge_model", judge_model)
        for rec in data["records"]:
            x, y, w = rec["model_x"], rec["model_y"], rec["winner"]
            for m in (x, y):
                stats.setdefault(m, {"wins": 0, "losses": 0, "ties": 0,
                                     "categories": {}})
            if w == "tie":
                stats[x]["ties"] += 1
                stats[y]["ties"] += 1
            else:
                win, lose = (x, y) if w == x else (y, x)
                stats[win]["wins"] += 1
                stats[lose]["losses"] += 1
            cat = rec.get("category") or "general"
            for m in (x, y):
                stats[m]["categories"].setdefault(cat,
                                                  {"wins": 0, "losses": 0, "ties": 0})
            cat_stats = stats[x]["categories"][cat]
            if w == "tie":
                cat_stats["ties"] += 1
            elif w == x:
                cat_stats["wins"] += 1
            else:
                cat_stats["losses"] += 1
    return stats, judge_model


def bradley_terry(stats, iters=200):
    """Zermelo iterations; returns {model: strength} (scale-free)."""
    models = list(stats)
    strength = {m: 1.0 for m in models}
    pairs = {}
    for i, a in enumerate(models):
        for b in models[i + 1:]:
            wins_a = stats[a]["_vs"].get(b, 0.0)
            wins_b = stats[b]["_vs"].get(a, 0.0)
            games = wins_a + wins_b
            if games:
                pairs[(a, b)] = (wins_a, wins_b, games)
    for _ in range(iters):
        new = {}
        for m in models:
            wins = 0.0
            denom = 0.0
            for (a, b), (wa, wb, n) in pairs.items():
                if a == m:
                    wins += wa
                    denom += n / (strength[a] + strength[b])
                elif b == m:
                    wins += wb
                    denom += n / (strength[a] + strength[b])
            new[m] = wins / denom if denom > 0 else strength[m]
        strength = new
    # fix scale geometrically to mean 1
    import math
    mean_log = sum(math.log(max(s, 1e-9)) for s in strength.values()) / len(strength)
    return {m: s / math.exp(mean_log) for m, s in strength.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results-dir", default="results")
    ap.add_argument("--anchors-file", default="anchors.yaml")
    ap.add_argument("--anchor", action="append", default=[],
                    help="anchor model name (repeatable; overrides anchors.yaml)")
    args = ap.parse_args()

    anchors = list(args.anchor)
    if not anchors and Path(args.anchors_file).exists():
        import yaml
        anchors = list(yaml.safe_load(Path(args.anchors_file).read_text())
                       .get("anchors", []))

    results_dir = Path(args.results_dir)
    autos = load_runs(results_dir)

    stats, judge_model = {}, None
    records = []
    for jf in sorted(results_dir.glob("judgements-*.json")):
        data = json.loads(jf.read_text())
        judge_model = data.get("judge_model", judge_model)
        records += data.get("records", [])

    for m in sorted({r[k] for r in records for k in ("model_x", "model_y")}):
        stats[m] = {"wins": 0, "losses": 0, "ties": 0, "_vs": {}, "categories": {}}
    for rec in records:
        x, y, w = rec["model_x"], rec["model_y"], rec["winner"]
        if w == "tie":
            stats[x]["ties"] += 1
            stats[y]["ties"] += 1
            stats[x]["_vs"][y] = stats[x]["_vs"].get(y, 0.0) + 0.5
            stats[y]["_vs"][x] = stats[y]["_vs"].get(x, 0.0) + 0.5
        else:
            win, lose = (x, y) if w == x else (y, x)
            stats[win]["wins"] += 1
            stats[lose]["losses"] += 1
            stats[win]["_vs"][lose] = stats[win]["_vs"].get(lose, 0.0) + 1.0
        cat = rec.get("category") or "general"
        for m in (x, y):
            stats[m]["categories"].setdefault(cat, {"wins": 0, "losses": 0, "ties": 0})
        if w == "tie":
            stats[x]["categories"][cat]["ties"] += 1
        elif w == x:
            stats[x]["categories"][cat]["wins"] += 1
        else:
            stats[y]["categories"][cat]["wins"] += 1
            stats[x]["categories"][cat]["losses"] += 1

    bt = bradley_terry(stats) if len(stats) > 1 else {}
    anchor_strengths = [bt[a] for a in anchors if a in bt]
    ref = (sum(anchor_strengths) / len(anchor_strengths)) if anchor_strengths \
        else (sum(bt.values()) / len(bt) if bt else 1.0)

    models = []
    for m, s in sorted(stats.items()):
        games = s["wins"] + s["losses"] + s["ties"]
        models.append({
            "model": m,
            "anchor": m in anchors,
            "auto_score": autos.get(m),
            "bt": round(100 * bt.get(m, 1.0) / ref, 1) if bt else None,
            "win_rate": round((s["wins"] + 0.5 * s["ties"]) / games, 3) if games else None,
            "games": games,
            "per_category": {
                c: {"win_rate": round((v["wins"] + 0.5 * v["ties"]) /
                                      (v["wins"] + v["losses"] + v["ties"]), 3)}
                for c, v in sorted(s["categories"].items())
            },
        })
    models.sort(key=lambda m: (-(m["bt"] or 0), m["model"]))

    agreement = None
    ag_path = results_dir / "human" / "agreement.json"
    if ag_path.exists():
        agreement = json.loads(ag_path.read_text())

    leaderboard = {
        "updated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "judge_model": judge_model,
        "anchors": anchors,
        "human_judge_agreement": agreement,
        "models": models,
    }
    Path("leaderboard.json").write_text(json.dumps(leaderboard, indent=2))
    print(f"leaderboard.json: {len(models)} models, {len(records)} judgements, "
          f"anchors={anchors or 'none'}")


if __name__ == "__main__":
    main()
