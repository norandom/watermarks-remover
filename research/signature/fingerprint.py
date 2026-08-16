#!/usr/bin/env python3
"""Measure which mechanical features identify a producer, and what erases them.

Runs the mechanical feature set over labelled corpora, reports AUC per feature
with length controlled, and prints the normalisation that would erase each
discriminative one.

Two corpora, because they answer different questions:

  files     -- markdown authored wholly by one producer. The realistic target.
  messages  -- commit messages. Cleaner labels, but a register humans write
               tersely in, so length dominates unless matched.

Usage:
    python research/signature/fingerprint.py [--derived DIR] [--min-auc 0.65]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mechanics import MECHANICS, NORMALISATION  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def auc(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return float("nan")
    neg_sorted = sorted(neg)
    n = len(neg_sorted)
    wins = 0.0
    import bisect
    for a in pos:
        lo = bisect.bisect_left(neg_sorted, a)
        hi = bisect.bisect_right(neg_sorted, a)
        wins += lo + 0.5 * (hi - lo)
    return wins / (len(pos) * n)


def match_on_length(a: list[str], b: list[str], seed: int = 0):
    """Bucket both classes by log2 character length, truncate to equal n."""
    rng = random.Random(seed)
    def bucket(t: str) -> int:
        return int(math.log2(max(len(t), 1)))
    ba, bb = {}, {}
    for t in a:
        ba.setdefault(bucket(t), []).append(t)
    for t in b:
        bb.setdefault(bucket(t), []).append(t)
    ka, kb = [], []
    for k in sorted(set(ba) & set(bb)):
        n = min(len(ba[k]), len(bb[k]))
        ka += rng.sample(ba[k], n)
        kb += rng.sample(bb[k], n)
    return ka, kb


def report(title: str, pos: list[str], neg: list[str], pos_name: str,
           neg_name: str, min_auc: float) -> list[tuple[str, float]]:
    print(f"\n{'=' * 84}")
    print(f"  {title}")
    print(f"  {pos_name} n={len(pos)}   {neg_name} n={len(neg)}")
    mp, mn = match_on_length(pos, neg)
    print(f"  length-matched: n={len(mp)} each", end="")
    if mp:
        print(f"  (median chars {statistics.median(map(len, mp)):.0f}"
              f" vs {statistics.median(map(len, mn)):.0f})")
    else:
        print("  -- NO OVERLAP, matched AUC unavailable")
    print("=" * 84)
    print(f"{'feature':<24} {'raw':>7} {'matched':>8}  {'strength':<12} normalisation")
    print("-" * 100)

    strong: list[tuple[str, float]] = []
    rows = []
    for name, fn in MECHANICS.items():
        raw = auc([fn(t) for t in pos], [fn(t) for t in neg])
        mat = auc([fn(t) for t in mp], [fn(t) for t in mn]) if mp else float("nan")
        use = mat if not math.isnan(mat) else raw
        rows.append((abs(use - 0.5), name, raw, mat, use))
    for _, name, raw, mat, use in sorted(rows, reverse=True):
        d = abs(use - 0.5)
        if d >= 0.25:
            s = "DECISIVE"
        elif d >= 0.15:
            s = "strong"
        elif d >= 0.08:
            s = "weak"
        else:
            s = "-"
        if d >= (min_auc - 0.5):
            strong.append((name, use))
        mt = f"{mat:.3f}" if not math.isnan(mat) else "  n/a"
        norm = NORMALISATION[name] if s != "-" else ""
        print(f"{name:<24} {raw:>7.3f} {mt:>8}  {s:<12} {norm}")
    return strong


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--derived", type=Path,
                   default=REPO / "research" / "corpus" / "derived")
    p.add_argument("--min-auc", type=float, default=0.65)
    args = p.parse_args()

    msgs_p = args.derived / "local_messages.json"
    human_p = args.derived / "human_messages.json"
    files_p = args.derived / "local_files.json"
    if not msgs_p.exists() or not human_p.exists():
        print("missing derived data; run research/corpus/*.py first")
        return 1

    local = json.loads(msgs_p.read_text(encoding="utf-8"))
    human = json.loads(human_p.read_text(encoding="utf-8"))
    claude_msgs = local.get("claude", [])

    strong_msgs = report(
        "Commit messages: Claude vs pre-LLM git/git",
        claude_msgs, human, "claude", "human", args.min_auc)

    strong_files: list[tuple[str, float]] = []
    if files_p.exists():
        entries = json.loads(files_p.read_text(encoding="utf-8"))
        src_root = REPO.parent
        claude_files = []
        for e in entries:
            if e["kind"] != "prose":
                continue
            f = src_root / e["repo"] / e["path"]
            try:
                claude_files.append(f.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                continue
        if claude_files:
            print(f"\n\n(markdown-file corpus: {len(claude_files)} Claude prose files; "
                  f"no human markdown control assembled yet)")

    print("\n" + "=" * 84)
    print("  WHAT TO STRIP")
    print("=" * 84)
    if not strong_msgs:
        print("  Nothing reached the threshold. No mechanical normalisation is")
        print("  justified by this evidence.")
    else:
        seen = set()
        for name, a in strong_msgs:
            if name in seen:
                continue
            seen.add(name)
            print(f"  [{abs(a-0.5)+0.5:.2f}] {name}")
            print(f"         -> {NORMALISATION[name]}")
    print()
    print("  A mechanical feature survives a prose rewrite. That is what makes")
    print("  these the residue after a humanizer pass, and what makes each one")
    print("  answerable with a normal form rather than a judgement call.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
