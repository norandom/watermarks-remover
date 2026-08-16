#!/usr/bin/env python3
"""wm-hook — pre-commit cleaner for AI provenance marks in text files.

Strips Layer A invisible-Unicode carriers (ZWSP, bidi controls, tag chars,
exotic spaces) from any text file, plus AI YAML-frontmatter keys from Markdown
and Quarto files. The cleaning modules live in core/ and originated in
guillaumemeyer/watermarks-remover; see NOTICE. This is a fork, not a vendored
dependency, and core/ is edited freely.

Autofix semantics for pre-commit: changed files are rewritten in place
(atomic, no .bak — git is the backup) and the exit code is 1, so the commit
fails and you re-stage. Exit 0 means everything was already clean. Files that
look binary are skipped with a warning and never modified.

Install (no system Python needed if you have uv):

    uvx --from 'git+https://github.com/norandom/watermarks-remover@<tag>' wm-hook --help
    pipx install 'git+https://github.com/norandom/watermarks-remover@<tag>'

.pre-commit-config.yaml in any target repo (pre-commit builds the isolated
env itself, so this needs nothing preinstalled beyond pre-commit):

    - repo: https://github.com/norandom/watermarks-remover
      rev: <tag>
      hooks:
        - id: wm-hook

(The hook ships an explicit files: pattern rather than types: [text] —
identify does not know .qmd/.qml, so type filtering would silently skip
Quarto/Qt files.)

Note: this is deliberately the lossless path only. Layer B statistical-mark
rewrites need a model and reword your prose — that has no place in a
commit-time hook.
"""

from __future__ import annotations

import argparse
import sys
from importlib import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))

from common import MAX_INPUT_BYTES, eprint, looks_binary, safe_write_text  # noqa: E402
from frontmatter import clean_markdown  # noqa: E402
from text_unicode import clean_text  # noqa: E402

# Markdown routing covers .md/.markdown/.mdx, plus .qmd (Quarto), which shares
# the YAML frontmatter convention.
MARKDOWN_EXTS = {".md", ".markdown", ".mdx", ".qmd"}


def _version() -> str:
    try:
        return metadata.version("watermarks-hook")
    except metadata.PackageNotFoundError:
        return "0.0.0+local"


def clean_one(path: Path, *, check: bool) -> tuple[str, str]:
    """Clean a single file. Returns (status, detail).

    status: "clean" | "changed" | "skipped" | "error"
    """
    try:
        size = path.stat().st_size
    except OSError as e:
        return "error", f"cannot stat: {e}"
    if size > MAX_INPUT_BYTES:
        return "error", f"refusing input larger than {MAX_INPUT_BYTES} bytes"
    try:
        data = path.read_bytes()
    except OSError as e:
        return "error", f"cannot read: {e}"

    binary = looks_binary(data)
    if binary is not None:
        return "skipped", f"looks like {binary} — left untouched"

    text = data.decode("utf-8", errors="surrogateescape")
    actions: list[str] = []
    if path.suffix.lower() in MARKDOWN_EXTS:
        text, fm_actions = clean_markdown(text)
        actions.extend(a for a in fm_actions if not a.startswith("no "))
    text, stats = clean_text(text)

    new_data = text.encode("utf-8", errors="surrogateescape")
    if new_data == data:
        return "clean", ""

    parts = [f"unicode removed={stats['removed_count']} replaced={stats['replaced_count']}"]
    parts.extend(actions)
    detail = "; ".join(parts)
    if check:
        return "changed", f"would clean ({detail})"
    try:
        safe_write_text(path, text)
    except OSError as e:
        return "error", f"cannot write: {e}"
    return "changed", f"cleaned ({detail})"


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog="exit: 0 = all clean, 1 = files were (or would be) modified, 2 = errors",
    )
    p.add_argument("paths", nargs="+", type=Path, help="files to clean in place")
    p.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if any file would change",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {_version()}")
    args = p.parse_args()

    changed = 0
    errors = 0
    for path in args.paths:
        status, detail = clean_one(path, check=args.check)
        if status == "clean":
            continue
        line = f"wm-hook: {path}: {status}"
        if detail:
            line += f" — {detail}"
        eprint(line)
        if status == "changed":
            changed += 1
        elif status == "error":
            errors += 1

    if errors:
        return 2
    return 1 if changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
