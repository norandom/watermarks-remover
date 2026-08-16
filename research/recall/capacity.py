#!/usr/bin/env python3
"""Residual covert-channel capacity after cleaning, measured in bits.

Method, per channel: take a fixed host text, encode a maximal payload, run the
cleaner, decode whatever survived, and compare against what went in. Capacity
is measured rather than derived from alphabet arithmetic, because the channels
that matter are the ones where an exemption in the cleaner leaves a hole its
author did not intend.

Reported per kilobyte of host text so the figures compare across channels.

Usage:
    python research/recall/capacity.py [--json] [--host-kb 4]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src" / "wm_hook" / "_vendor"))
sys.path.insert(0, str(Path(__file__).parent))

from text_unicode import clean_text  # noqa: E402
from channels import CHANNELS, to_bits  # noqa: E402

WORDS = ("release", "deploy", "config", "module", "handler", "buffer", "index",
         "record", "session", "worker", "schema", "commit", "branch", "target")


def make_host(kb: int, seed: int = 7) -> str:
    """Plain ASCII prose. No carriers, so every surviving bit came from us."""
    rng = random.Random(seed)
    target, lines = kb * 1024, []
    total = 0
    while total < target:
        n = rng.randint(6, 14)
        line = " ".join(rng.choice(WORDS) for _ in range(n)) + "."
        lines.append(line)
        total += len(line) + 1
    return "\n".join(lines) + "\n"


def surviving(sent: list[int], got: list[int]) -> int:
    """Longest usable prefix agreement. A channel that garbles is not a channel."""
    n = 0
    for a, b in zip(sent, got):
        if a != b:
            break
        n += 1
    return n


def measure(host: str, policy: dict | None = None) -> list[dict]:
    rows = []
    kb = len(host) / 1024
    for ch in CHANNELS:
        cap = ch.capacity(host)
        payload = to_bits(bytes(random.Random(11).getrandbits(8) for _ in range(cap // 8 + 2)))[:cap]
        stuffed = ch.encode(host, payload)

        # sanity: the channel must actually work before cleaning
        pre = surviving(payload, ch.decode(stuffed))

        cleaned, _ = clean_text(stuffed, **(policy or {}))
        post = surviving(payload, ch.decode(cleaned))

        rows.append({
            "key": ch.key,
            "name": ch.name,
            "note": ch.note,
            "capacity_bits": cap,
            "pre_clean_bits": pre,
            "post_clean_bits": post,
            "pre_bits_per_kb": pre / kb,
            "post_bits_per_kb": post / kb,
            "survival_pct": 100 * post / pre if pre else 0.0,
            "host_bytes_changed": len(stuffed) != len(cleaned),
        })
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--json", action="store_true")
    p.add_argument("--host-kb", type=int, default=4)
    args = p.parse_args()

    host = make_host(args.host_kb)
    rows = measure(host)
    rows.sort(key=lambda r: -r["post_bits_per_kb"])

    if args.json:
        json.dump({"host_kb": args.host_kb, "channels": rows}, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    kb = len(host) / 1024
    print(f"host: {len(host)} bytes of carrier-free ASCII prose ({kb:.1f} KB)\n")
    print(f"{'channel':<32} {'pre b/KB':>9} {'post b/KB':>10} {'survives':>9}  note")
    print("-" * 96)
    for r in rows:
        surv = f"{r['survival_pct']:.1f}%"
        flag = ""
        if r["post_bits_per_kb"] > 100:
            flag = "  <-- HIGH CAPACITY"
        elif r["post_bits_per_kb"] > 0:
            flag = "  <-- open"
        print(f"{r['name']:<32} {r['pre_bits_per_kb']:>9.0f} "
              f"{r['post_bits_per_kb']:>10.0f} {surv:>9}  {r['note']}{flag}")

    total_pre = sum(r["pre_bits_per_kb"] for r in rows)
    total_post = sum(r["post_bits_per_kb"] for r in rows)
    open_ch = [r for r in rows if r["post_bits_per_kb"] > 0]

    print()
    print("=" * 96)
    print(f"  total channel capacity before cleaning   {total_pre:>9.0f} bits/KB")
    print(f"  RESIDUAL CAPACITY AFTER CLEANING         {total_post:>9.0f} bits/KB"
          f"   ({100*total_post/total_pre:.1f}% of the original)")
    print(f"  channels left open                       {len(open_ch)} of {len(rows)}")
    print()
    if open_ch:
        print("  ranked by what an adversary can still push through:")
        for r in open_ch:
            share = 100 * r["post_bits_per_kb"] / total_post
            print(f"    {r['post_bits_per_kb']:>7.0f} b/KB  ({share:>5.1f}% of residual)  {r['name']}")
        top = open_ch[0]
        print()
        print(f"  {top['name']} alone carries {100*top['post_bits_per_kb']/total_post:.0f}%"
              f" of everything that survives.")
        print("  A technique count would have ranked it equal with the trickles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
