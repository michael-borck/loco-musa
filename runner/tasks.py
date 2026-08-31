"""Task loading. Tasks are plain YAML files under tasks/."""

from pathlib import Path

import yaml

TIERS = ("auto", "judged", "dialogue")


def load_tasks(tasks_dir="tasks"):
    """Load all task YAML files, sorted by tier then id."""
    tasks = []
    for path in sorted(Path(tasks_dir).rglob("*.yaml")):
        if path.name.startswith("._"):  # macOS AppleDouble junk on exFAT
            continue
        with open(path, encoding="utf-8") as f:
            task = yaml.safe_load(f)
        if not task or "id" not in task:
            continue
        tier = task.get("tier")
        if tier not in TIERS:
            raise ValueError(f"{path}: tier must be one of {TIERS}, got {tier!r}")
        task["_path"] = str(path)
        tasks.append(task)
    ids = [t["id"] for t in tasks]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate task ids: {dupes}")
    return tasks


def task_index(tasks):
    return {t["id"]: t for t in tasks}
