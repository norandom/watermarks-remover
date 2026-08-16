#!/usr/bin/env python3
"""Fetch the pre-LLM human control corpus from git/git (2018-2019).

Not redistributed with this repository: git/git is GPLv2 and its commit
messages are its contributors' expression. This pulls them on demand into
derived/, which is gitignored. Only the measurements are committed.

git/git is the right control because it is *process-matched* to the Claude
corpus: no ticket system, so the commit message carries the documentation, the
same structural pressure that makes Claude verbose. CPython and curl reference
issue numbers instead and have a median of 16 words, which would make length
the dominant confound.

Requires the `gh` CLI, authenticated.

Usage:
    python research/corpus/fetch_human.py [--out DIR] [--repo OWNER/NAME]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

# Mailing-list ceremony, not prose. Stripped so length reflects what a person
# actually wrote about the change.
TRAILER = re.compile(
    r"^(Signed-off-by|Reviewed-by|Acked-by|Cc|Helped-by|Tested-by|Reported-by"
    r"|Suggested-by|Co-authored-by|Mentored-by|Based-on-patch-by|Noticed-by"
    r"|Improved-by|Analyzed-by|Original-patch-by):",
    re.I,
)
WORDS = re.compile(r"\b[\w'-]+\b")

WINDOWS = [
    ("2018-01-01", "2018-04-01"), ("2018-04-01", "2018-07-01"),
    ("2018-07-01", "2018-10-01"), ("2018-10-01", "2019-01-01"),
    ("2019-01-01", "2019-04-01"), ("2019-04-01", "2019-07-01"),
    ("2019-07-01", "2019-10-01"), ("2019-10-01", "2020-01-01"),
]


def gh_commits(repo: str, since: str, until: str, page: int) -> list[str] | None:
    r = subprocess.run(
        ["gh", "api", "-X", "GET", f"repos/{repo}/commits",
         "-f", f"since={since}T00:00:00Z", "-f", f"until={until}T00:00:00Z",
         "-f", "per_page=100", "-f", f"page={page}",
         "--jq", "[.[] | .commit.message]"],
        capture_output=True, text=True, shell=True, timeout=180,
        encoding="utf-8", errors="replace",
    )
    if r.returncode != 0 or not (r.stdout or "").strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def strip_trailers(message: str) -> str:
    return "\n".join(
        line for line in message.splitlines() if not TRAILER.match(line.strip())
    ).strip()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path, default=Path(__file__).parent / "derived")
    p.add_argument("--repo", default="git/git")
    args = p.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    messages: list[str] = []

    for since, until in WINDOWS:
        for page in (1, 2, 3):
            batch = gh_commits(args.repo, since, until, page)
            if not batch:
                break
            for raw in batch:
                body = strip_trailers(raw)
                if body:
                    messages.append(body)
            time.sleep(0.2)
        print(f"  {since} -> {until}: {len(messages)} total", file=sys.stderr)

    if not messages:
        print("no messages fetched; is `gh` authenticated?", file=sys.stderr)
        return 1

    dest = args.out / "human_messages.json"
    dest.write_text(json.dumps(messages, indent=1), encoding="utf-8")
    words = sum(len(WORDS.findall(m)) for m in messages)
    print(f"{len(messages)} messages, {words} words -> {dest}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
