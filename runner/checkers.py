"""Deterministic checkers for the auto tier.

Every checker: fn(text, args) -> (score in [0,1], detail dict).
Scores are fractional so near-misses still carry signal.
"""

import re
from collections import Counter


def _numbered_items(text):
    """Extract items from a numbered list: '1. foo' / '1) foo'."""
    return re.findall(r"^\s*\d+[.)]\s*(.+?)\s*$", text, flags=re.MULTILINE)


def _plain_lines(text):
    """Non-empty lines with list numbering stripped."""
    lines = []
    for line in text.splitlines():
        line = re.sub(r"^\s*\d+[.)]\s*", "", line.strip())
        if line:
            lines.append(line)
    return lines


def _norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _words(s):
    return [w for w in re.findall(r"[A-Za-z0-9'-]+", s) if w]


# --- checkers ---------------------------------------------------------------

def word_count(text, args):
    n = len(_words(text))
    lo, hi = args.get("min", 0), args.get("max", 10**9)
    ok = lo <= n <= hi
    return (1.0 if ok else 0.0), {"words": n, "min": lo, "max": hi}


def forbidden_chars(text, args):
    found = sorted({c for c in args.get("chars", []) if c in text})
    return (0.0 if found else 1.0), {"found": found}


def includes_phrases(text, args):
    low = text.lower()
    missing = [p for p in args.get("phrases", []) if p.lower() not in low]
    return (1.0 if not missing else 0.0), {"missing": missing}


def item_constraints(text, args):
    items = _numbered_items(text)
    detail, scores = {}, []

    if "count" in args:
        want = args["count"]
        s = 1.0 if len(items) == want else max(0.0, 1 - abs(len(items) - want) / want)
        detail["count"] = {"found": len(items), "want": want}
        scores.append(s)

    if "max_words" in args:
        lim = args["max_words"]
        over = [len(_words(i)) for i in items if len(_words(i)) > lim]
        s = 1.0 if len(items) == 0 else 1 - len(over) / len(items)
        detail["max_words"] = {"violations": len(over), "limit": lim}
        scores.append(s)

    if "forbidden_letters" in args:
        bad = args["forbidden_letters"]
        viol = [i for i in items if any(c.lower() in i.lower() for c in bad)]
        s = 1.0 if not items else 1 - len(viol) / len(items)
        detail["forbidden_letters"] = {"violations": len(viol)}
        scores.append(s)

    if args.get("unique"):
        if not items:
            scores.append(0.0)
        else:
            normed = [_norm(i) for i in items]
            dupes = sum(c - 1 for c in Counter(normed).values() if c > 1)
            scores.append(1 - dupes / len(items))
            detail["unique"] = {"duplicates": dupes}

    return (sum(scores) / len(scores) if scores else 0.0), detail


def line_constraints(text, args):
    lines = _plain_lines(text)
    detail, scores = {}, []

    if "count" in args:
        want = args["count"]
        s = 1.0 if len(lines) == want else max(0.0, 1 - abs(len(lines) - want) / want)
        detail["count"] = {"found": len(lines), "want": want}
        scores.append(s)

    if "max_words" in args:
        lim = args["max_words"]
        over = [len(_words(i)) for i in lines if len(_words(i)) > lim]
        s = 1.0 if not lines else 1 - len(over) / len(lines)
        detail["max_words"] = {"violations": len(over), "limit": lim}
        scores.append(s)

    return (sum(scores) / len(scores) if scores else 0.0), detail


def acrostic(text, args):
    word = args.get("word", "").upper()
    lines = _plain_lines(text)
    matches, letters = 0, []
    for i, ch in enumerate(word):
        if i < len(lines):
            first = next((c for c in lines[i] if c.isalpha()), "").upper()
            letters.append(first)
            matches += first == ch
    detail = {"expected": word, "got": "".join(letters), "lines_found": len(lines)}
    return (matches / len(word) if word else 0.0), detail


def sorted_order(text, args):
    items = [_norm(i) for i in _numbered_items(text)]
    if len(items) < 2:
        return 0.0, {"reason": "fewer than 2 numbered items"}
    desc = args.get("direction", "asc") == "desc"
    pairs = list(zip(items, items[1:]))
    good = sum((a > b) if desc else (a < b) for a, b in pairs)
    return good / len(pairs), {"ordered_pairs": f"{good}/{len(pairs)}"}


def numeric_answer(text, args):
    pattern = args.get("pattern", r"-?\d+(?:\.\d+)?")
    matches = re.findall(pattern, text)
    if not matches:
        return 0.0, {"reason": "no answer found"}
    got = matches[-1]
    try:
        ok = abs(float(got) - float(args["answer"])) < 1e-9
    except ValueError:
        ok = False
    return (1.0 if ok else 0.0), {"got": got, "want": args["answer"]}


def pairs_in_sentence(text, args):
    """Each (word_a, word_b) pair must co-occur in one sentence/line.
    window: 'last' restricts to the final non-empty line.
    max_gap: optional max chars between the two words (default: unbounded)."""
    window = args.get("window", "any")
    max_gap = args.get("max_gap")
    units = [l for l in text.splitlines() if l.strip()]
    if window == "last" and units:
        units = units[-1:]
    found, missing = 0, []
    for a, b in args.get("pairs", []):
        hit = False
        for u in units:
            low = u.lower()
            spans_a = [m.span() for m in re.finditer(re.escape(a.lower()), low)]
            spans_b = [m.span() for m in re.finditer(re.escape(b.lower()), low)]
            for sa in spans_a:
                for sb in spans_b:
                    gap = min(abs(sb[0] - sa[1]), abs(sa[0] - sb[1]))
                    if max_gap is None or gap <= max_gap:
                        hit = True
                        break
                if hit:
                    break
            if hit:
                break
        found += hit
        if not hit:
            missing.append([a, b])
    total = len(args.get("pairs", [])) or 1
    return found / total, {"missing": missing}


CHECKERS = {
    "word_count": word_count,
    "forbidden_chars": forbidden_chars,
    "includes_phrases": includes_phrases,
    "item_constraints": item_constraints,
    "line_constraints": line_constraints,
    "acrostic": acrostic,
    "sorted_order": sorted_order,
    "numeric_answer": numeric_answer,
    "pairs_in_sentence": pairs_in_sentence,
}


def run_checks(text, checks):
    """checks: list of {name, args}. Returns (mean score, per-check detail)."""
    total, detail = 0.0, {}
    for check in checks:
        fn = CHECKERS.get(check["name"])
        if fn is None:
            raise ValueError(f"unknown checker: {check['name']}")
        score, info = fn(text, check.get("args", {}))
        detail[check["name"]] = {"score": round(score, 3), **info}
        total += score
    return (total / len(checks) if checks else 0.0), detail
