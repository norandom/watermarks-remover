#!/usr/bin/env python3
"""Measure Layer A recall: what fraction of published techniques do we catch?

Runs every technique in the catalogue through the cleaner and reports detection
and removal rates separately, because they are different questions and a tool
that conflates them will overstate itself.

A technique whose expectation is `remove=False` under the default policy is
re-run under the policy it names. Failing to strip a private-use character by
default is correct behaviour, not a miss, and is scored as such.

Usage:
    python research/recall/benchmark.py [--json] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "src" / "wm_hook" / "_vendor"))
sys.path.insert(0, str(Path(__file__).parent))

from text_unicode import clean_text, inspect_text  # noqa: E402
from techniques import TECHNIQUES, Technique  # noqa: E402


def carriers_in(text: str) -> set[int]:
    out = set()
    for ch in text:
        cp = ord(ch)
        cat = unicodedata.category(ch)
        if (cat == "Cf"
                or 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0xFFFFD
                or 0x100000 <= cp <= 0x10FFFD
                or 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF
                or cp in (0x00A0, 0x2009, 0x200A, 0x202F, 0x205F, 0x3000)
                or 0x2000 <= cp <= 0x200A):
            out.add(cp)
    return out


# Flags the SHIPPED cleaner accepts. The specification adds others
# (strip_private_use, strip_bom); a technique naming one of those is describing
# target behaviour that does not exist yet, and the benchmark says so rather
# than crashing or quietly scoring it as a pass.
import inspect as _inspect  # noqa: E402

SHIPPED_FLAGS = {
    p for p in _inspect.signature(clean_text).parameters if p != "text"
}


def evaluate(t: Technique) -> dict:
    """Score one technique for detection and for removal."""
    report = inspect_text(t.text)
    detected = report.suspicious_total > 0

    kwargs = {k: v for k, v in t.policy.items() if k in SHIPPED_FLAGS}
    unimplemented = sorted(set(t.policy) - SHIPPED_FLAGS)
    cleaned, stats = clean_text(t.text, **kwargs)
    changed = cleaned != t.text

    before = carriers_in(t.text)
    after = carriers_in(cleaned)
    allowed = set(t.residue)
    leaked = after - allowed

    default_clean, _ = clean_text(t.text)
    preserved_by_default = bool(carriers_in(default_clean) & before)

    if unimplemented:
        # The technique names a policy flag the shipped cleaner does not have.
        # Score against what the code does today and flag the divergence.
        removed_ok = changed and not leaked
        status = f"spec-only flag: {', '.join(unimplemented)}"
    elif t.remove:
        removed_ok = changed and not leaked
        status = ""
    else:
        # Expected NOT to strip by default; the named policy should strip it.
        removed_ok = preserved_by_default and (changed and not leaked if kwargs else True)
        status = ""

    return {
        "unimplemented_flags": unimplemented,
        "preserved_by_default": preserved_by_default,
        "status": status,
        "key": t.key,
        "name": t.name,
        "reference": t.reference,
        "expect_detect": t.detect,
        "expect_remove": t.remove,
        "policy": t.policy or None,
        "detected": detected,
        "detect_ok": detected == t.detect,
        "changed": changed,
        "remove_ok": removed_ok,
        "carriers_before": sorted(f"U+{c:04X}" for c in before),
        "leaked": sorted(f"U+{c:04X}" for c in leaked),
        "removed_count": stats["removed_count"],
        "replaced_count": stats["replaced_count"],
        "note": t.note,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    rows = [evaluate(t) for t in TECHNIQUES]

    if args.json:
        json.dump(rows, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return 0

    in_scope = [r for r in rows if r["expect_detect"]]
    known_gaps = [r for r in rows if not r["expect_detect"]]
    det_hits = sum(1 for r in in_scope if r["detected"])
    rem_hits = sum(1 for r in rows if r["remove_ok"])
    surprises = [r for r in rows if not r["detect_ok"]]

    print(f"{'technique':<34} {'detect':>7} {'remove':>7}  note")
    print("-" * 92)
    for r in rows:
        d = "yes" if r["detected"] else "NO"
        if not r["expect_detect"]:
            d = "gap" if not r["detected"] else "BONUS"
        rm = "yes" if r["remove_ok"] else "NO"
        if not r["expect_remove"]:
            rm = "policy" if r["remove_ok"] else "NO"
        flag = "" if r["detect_ok"] else "  <-- UNEXPECTED"
        note = r["status"] or r["note"]
        note = (note[:34] + "...") if len(note) > 37 else note
        print(f"{r['name'][:34]:<34} {d:>7} {rm:>7}  {note}{flag}")

    print()
    print("=" * 92)
    print(f"  techniques catalogued        {len(rows)}")
    print(f"  in scope for Layer A         {len(in_scope)}")
    print(f"  DETECTION RECALL             {det_hits}/{len(in_scope)}"
          f"  ({100*det_hits/len(in_scope):.1f}%)")
    print(f"  removal correct              {rem_hits}/{len(rows)}"
          f"  ({100*rem_hits/len(rows):.1f}%)")
    print(f"  documented out-of-scope gaps {len(known_gaps)}")
    for r in known_gaps:
        print(f"      - {r['name']}")
    if surprises:
        print(f"\n  UNEXPECTED RESULTS ({len(surprises)}) - the catalogue or the tool is wrong:")
        for r in surprises:
            print(f"      {r['name']}: expected detect={r['expect_detect']}, got {r['detected']}")
    print()
    print("  Layer B (statistical token-sampling) recall: 0 of 1 known scheme.")
    print("  No publicly available method detects it; key recovery requires")
    print("  active querying of the watermarked API, not corpus analysis.")

    if args.verbose:
        print("\n=== leaked carriers, per technique ===")
        for r in rows:
            if r["leaked"]:
                print(f"  {r['name']}: {', '.join(r['leaked'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
