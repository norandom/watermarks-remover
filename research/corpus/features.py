#!/usr/bin/env python3
"""Measure separation between labelled classes, with length controlled.

The finding this exists to guard against: commit-message length tracks
*process*, not authorship. git/git contributors wrote 50-word messages in 2019
because the message was the documentation; Claude writes 91-word ones here for
the same structural reason. Any feature correlated with length will appear to
discriminate and will be measuring workflow.

So every feature is reported twice: raw, and on a length-matched subsample.
A feature that survives length matching is telling you something. One that
does not is telling you about the ticket system.

Reports AUC per feature. AUC 0.5 is chance; below 0.5 means the feature runs
the other way.

Usage:
    python research/corpus/features.py [--derived DIR]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import statistics
from collections import Counter
from pathlib import Path

WORDS = re.compile(r"\b[\w'-]+\b")
SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def words(t: str) -> list[str]:
    return WORDS.findall(t.lower())


def sentences(t: str) -> list[str]:
    return [s for s in SENT.split(t.replace("\n", " ")) if s.strip()]


# --- features ---------------------------------------------------------------
# Each takes text, returns a float. Kept small and interpretable on purpose:
# an uninterpretable feature that separates is a confound you have not found
# yet.

def f_word_count(t: str) -> float:
    return float(len(words(t)))


def f_mean_sentence_len(t: str) -> float:
    s = sentences(t)
    if not s:
        return 0.0
    return statistics.mean(len(words(x)) for x in s)


def f_burstiness(t: str) -> float:
    """Coefficient of variation of sentence length. Lower = more uniform."""
    lens = [len(words(x)) for x in sentences(t)]
    if len(lens) < 2:
        return 0.0
    m = statistics.mean(lens)
    return statistics.pstdev(lens) / m if m else 0.0


def f_type_token(t: str) -> float:
    w = words(t)
    return len(set(w)) / len(w) if w else 0.0


def f_comma_rate(t: str) -> float:
    w = words(t)
    return t.count(",") / len(w) if w else 0.0


def f_bullet_rate(t: str) -> float:
    lines = [l for l in t.splitlines() if l.strip()]
    if not lines:
        return 0.0
    return sum(1 for l in lines if l.lstrip()[:2] in ("- ", "* ")) / len(lines)


def f_colon_rate(t: str) -> float:
    w = words(t)
    return t.count(":") / len(w) if w else 0.0


def f_hedge_rate(t: str) -> float:
    hedges = {"may", "might", "could", "generally", "typically", "often",
              "usually", "likely", "consider", "note"}
    w = words(t)
    return sum(1 for x in w if x in hedges) / len(w) if w else 0.0


def f_because_rate(t: str) -> float:
    """Explicit causal connectives: does the writer justify decisions inline?"""
    causal = {"because", "since", "therefore", "so", "thus", "hence", "why"}
    w = words(t)
    return sum(1 for x in w if x in causal) / len(w) if w else 0.0


def f_first_person(t: str) -> float:
    w = words(t)
    fp = {"i", "we", "my", "our", "us", "me"}
    return sum(1 for x in w if x in fp) / len(w) if w else 0.0


FEATURES = {
    "word_count": f_word_count,
    "mean_sentence_len": f_mean_sentence_len,
    "burstiness_cv": f_burstiness,
    "type_token_ratio": f_type_token,
    "comma_rate": f_comma_rate,
    "bullet_line_rate": f_bullet_rate,
    "colon_rate": f_colon_rate,
    "hedge_rate": f_hedge_rate,
    "causal_rate": f_because_rate,
    "first_person_rate": f_first_person,
}


def auc(pos: list[float], neg: list[float]) -> float:
    """Mann-Whitney U / |pos||neg|. Ties count a half."""
    if not pos or not neg:
        return float("nan")
    wins = 0.0
    for a in pos:
        for b in neg:
            if a > b:
                wins += 1
            elif a == b:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def length_matched(a: list[str], b: list[str], seed: int = 0) -> tuple[list[str], list[str]]:
    """Pair samples into shared word-count deciles, then truncate to equal n.

    Crude but transparent: a fancier propensity match would hide the very
    confound this is meant to expose.
    """
    rng = random.Random(seed)
    def bucket(t):
        n = len(words(t))
        return 0 if n <= 0 else int(math.log2(max(n, 1)))
    ba, bb = Counter(map(bucket, a)), Counter(map(bucket, b))
    keep_a, keep_b = [], []
    by_a, by_b = {}, {}
    for t in a:
        by_a.setdefault(bucket(t), []).append(t)
    for t in b:
        by_b.setdefault(bucket(t), []).append(t)
    for k in sorted(set(ba) & set(bb)):
        n = min(len(by_a[k]), len(by_b[k]))
        keep_a += rng.sample(by_a[k], n)
        keep_b += rng.sample(by_b[k], n)
    return keep_a, keep_b


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--derived", type=Path, default=Path(__file__).parent / "derived")
    args = p.parse_args()

    human_p = args.derived / "human_messages.json"
    local_p = args.derived / "local_messages.json"
    if not human_p.exists() or not local_p.exists():
        print("missing derived data; run fetch_human.py and build_labelled.py first")
        return 1

    human = json.loads(human_p.read_text(encoding="utf-8"))
    local = json.loads(local_p.read_text(encoding="utf-8"))
    claude = local.get("claude", [])

    print(f"raw:      claude n={len(claude)}  human n={len(human)}")
    mc, mh = length_matched(claude, human)
    print(f"matched:  claude n={len(mc)}  human n={len(mh)}")
    if mc:
        print(f"          median words: claude {statistics.median(map(f_word_count, mc)):.0f}"
              f"  human {statistics.median(map(f_word_count, mh)):.0f}")
    print()
    print(f"{'feature':<20} {'AUC raw':>9} {'AUC matched':>12}  reading")
    print("-" * 74)
    for name, fn in FEATURES.items():
        raw = auc([fn(t) for t in claude], [fn(t) for t in human])
        mat = auc([fn(t) for t in mc], [fn(t) for t in mh]) if mc else float("nan")
        if math.isnan(mat):
            note = "no matched sample"
        elif abs(mat - 0.5) < 0.10:
            note = "chance after matching"
        elif abs(raw - 0.5) > 0.20 and abs(mat - 0.5) < 0.15:
            note = "LENGTH CONFOUND"
        else:
            note = "survives matching"
        print(f"{name:<20} {raw:>9.3f} {mat:>12.3f}  {note}")

    print()
    print("AUC 0.5 is chance. A feature that scores high raw and near 0.5 after")
    print("length matching was measuring the ticket system, not the author.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
