#!/usr/bin/env python3
"""Build the locally-labelled corpus from sibling git repositories.

Two label kinds, both from evidence rather than assumption:

- **commit messages** carry one label each, from the trailer.
- **files** are labelled only when *every* commit that ever touched them is
  trailered. A file edited by both an agent and a human by hand has no clean
  label and is excluded rather than guessed at.

Reads git metadata and file contents. Writes only to derived/.

Usage:
    python research/corpus/build_labelled.py [--source-root DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
from pathlib import Path

CLAUDE = re.compile(r"Co-Authored-By:\s*Claude|Generated with \[Claude Code\]", re.I)
CODEX = re.compile(r"Co-Authored-By:\s*(Codex|ChatGPT)", re.I)
TRAILER = re.compile(r"^(Co-Authored-By|Signed-off-by|Generated with):", re.I)
WORDS = re.compile(r"\b[\w'-]+\b")
SHA = re.compile(r"^[0-9a-f]{40}$")

PROSE_EXT = {".md", ".markdown", ".rst", ".txt"}
CODE_EXT = {".py", ".ps1", ".psm1", ".js", ".ts", ".sh", ".go", ".rs"}
MIN_WORDS = 50

# Repos labelled by on-disk agent config rather than by trailer, because the
# agent in question writes none. Kept explicit so the assumption is visible.
CODEX_BY_DISK = {"PowerShell"}


def git(repo: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=180)
    return r.stdout if r.returncode == 0 else ""


def commit_labels(repo: Path) -> dict[str, str]:
    """sha -> 'claude' | 'codex' | 'plain'."""
    out: dict[str, str] = {}
    log = git(repo, "log", "--format=%H%x00%s%x00%b%x01", "-n", "5000")
    for entry in log.split("\x01"):
        if not entry.strip():
            continue
        parts = entry.split("\x00")
        if len(parts) < 3:
            continue
        sha, blob = parts[0].strip(), parts[1] + "\n" + parts[2]
        if CLAUDE.search(blob):
            out[sha] = "claude"
        elif CODEX.search(blob):
            out[sha] = "codex"
        else:
            out[sha] = "plain"
    return out


def files_touched(repo: Path) -> dict[str, set[str]]:
    touched: dict[str, set[str]] = collections.defaultdict(set)
    raw = git(repo, "log", "--format=%H", "--name-only", "-n", "5000")
    cur = None
    for line in raw.splitlines():
        line = line.rstrip()
        if not line:
            continue
        if SHA.match(line):
            cur = line
        elif cur:
            touched[line].add(cur)
    return touched


def prose_of(subject: str, body: str) -> str:
    lines = [subject] + [
        l for l in body.splitlines() if l.strip() and not TRAILER.match(l.strip())
    ]
    return "\n".join(lines).strip()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source-root", type=Path,
                   default=Path(__file__).resolve().parents[3])
    p.add_argument("--out", type=Path, default=Path(__file__).parent / "derived")
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    messages: dict[str, list[str]] = collections.defaultdict(list)
    files: list[dict] = []

    repos = sorted(d for d in args.source_root.iterdir()
                   if d.is_dir() and (d / ".git").exists())
    for repo in repos:
        labels = commit_labels(repo)
        if not labels:
            continue

        log = git(repo, "log", "--format=%H%x00%s%x00%b%x01", "-n", "5000")
        for entry in log.split("\x01"):
            if not entry.strip():
                continue
            parts = entry.split("\x00")
            if len(parts) < 3:
                continue
            sha = parts[0].strip()
            text = prose_of(parts[1], parts[2])
            if not text:
                continue
            label = labels.get(sha, "plain")
            if label == "plain" and repo.name in CODEX_BY_DISK:
                label = "codex_by_disk"
            messages[label].append(text)

        for rel, shas in files_touched(repo).items():
            if not shas or not all(labels.get(s) == "claude" for s in shas):
                continue
            f = repo / rel
            ext = f.suffix.lower()
            if not f.is_file() or (ext not in PROSE_EXT and ext not in CODE_EXT):
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            n = len(WORDS.findall(text))
            if n < MIN_WORDS:
                continue
            files.append({
                "repo": repo.name,
                "path": rel.replace("\\", "/"),
                "kind": "prose" if ext in PROSE_EXT else "code",
                "words": n,
                "label": "claude",
            })

    (args.out / "local_messages.json").write_text(
        json.dumps(messages, indent=1), encoding="utf-8")
    (args.out / "local_files.json").write_text(
        json.dumps(files, indent=1), encoding="utf-8")

    print(f"{'label':<16} {'msgs':>6} {'words':>8}")
    print("-" * 34)
    for label, msgs in sorted(messages.items()):
        w = sum(len(WORDS.findall(m)) for m in msgs)
        print(f"{label:<16} {len(msgs):>6} {w:>8}")
    by_kind = collections.Counter(f["kind"] for f in files)
    print(f"\nwholly-claude files: {len(files)} "
          f"(prose {by_kind['prose']}, code {by_kind['code']}, "
          f"{sum(f['words'] for f in files)} words)")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
