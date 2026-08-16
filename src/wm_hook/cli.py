#!/usr/bin/env python3
"""wm-hook — pre-commit cleaner for invisible Unicode carriers in text.

Strips Layer A carriers from any text file: zero-width characters, Unicode tag
sequences, orphan variation selectors, private-use codepoints, bidi overrides,
and space homoglyphs. The cleaning modules live in core/ and originated in
guillaumemeyer/watermarks-remover; see NOTICE. This is a fork, not a vendored
dependency, and core/ is edited freely.

**Scope is text and Unicode carriers, and nothing else.** Images, C2PA
manifests, container metadata, YAML frontmatter keys and stylometry are all
out of scope and were removed. Each was a different medium or a different
kind of evidence, and carrying them widened the surface without serving the
question this tool answers: what invisible material is in my text, and can it
be removed without changing what the text says.

Frontmatter key removal in particular is gone. It was provenance *metadata*,
not a text carrier, and it was the source of three of the worst defects:
deleting a whole key when its value merely named a vendor, rebuilding CRLF
blocks with line feeds, and eating a leading thematic break. Deleting the
feature removed all three.

Autofix semantics for pre-commit: changed files are rewritten in place
(atomic, no .bak — git is the backup) and the exit code is 1, so the commit
fails and you re-stage. Exit 0 means everything was already clean. Files that
look binary are skipped with a warning and never modified.

Install (no system Python needed if you have uv):

    uvx --from 'git+https://github.com/norandom/watermarks-remover@v0.1.0a1' wm-hook --help
    pipx install 'git+https://github.com/norandom/watermarks-remover@v0.1.0a1'

.pre-commit-config.yaml in any target repo (pre-commit builds the isolated
env itself, so this needs nothing preinstalled beyond pre-commit):

    - repo: https://github.com/norandom/watermarks-remover
      rev: v0.1.0a1
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
import json
import sys
from importlib import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))

from common import MAX_INPUT_BYTES, eprint, looks_binary, safe_write_text  # noqa: E402
from text_unicode import clean_text  # noqa: E402

from wm_hook import verdict as _verdict  # noqa: E402
from wm_hook.discovery import iter_text_files  # noqa: E402


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
    text, stats = clean_text(text)

    new_data = text.encode("utf-8", errors="surrogateescape")
    if new_data == data:
        return "clean", ""

    detail = f"unicode removed={stats['removed_count']} replaced={stats['replaced_count']}"
    if check:
        return "changed", f"would clean ({detail})"
    try:
        safe_write_text(path, text)
    except OSError as e:
        return "error", f"cannot write: {e}"
    return "changed", f"cleaned ({detail})"


def read_text(path: Path) -> tuple[str | None, str]:
    """Decoded text, or (None, reason)."""
    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            return None, f"refusing input larger than {MAX_INPUT_BYTES} bytes"
        data = path.read_bytes()
    except OSError as e:
        return None, f"cannot read: {e}"
    binary = looks_binary(data)
    if binary is not None:
        return None, f"looks like {binary} — not scanned"
    return data.decode("utf-8", errors="surrogateescape"), ""


def detect(paths: list[Path], *, as_json: bool, verbose: bool) -> int:
    """Report whether a covert carrier is present. Exit 1 if any is.

    This is a one-sided test and the output says so on every run. A positive
    establishes that something embedded hidden data; a negative establishes
    nothing about whether a human wrote the text.
    """
    results, hits, errors = [], 0, 0
    lines: list[str] = []
    for path in paths:
        text, why = read_text(path)
        if text is None:
            errors += 1
            lines.append(f"ERROR    {path}: {why}")
            results.append({"path": str(path), "error": why})
            continue
        v = _verdict.classify(text)
        if v.carrier_present:
            hits += 1
        results.append({"path": str(path), **v.to_dict()})
        if v.level != _verdict.NONE or verbose:
            lines.extend(_verdict.render(str(path), v, verbose=verbose))

    if as_json:
        json.dump(results, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        for line in lines:
            print(line)
        scanned = len(paths) - errors
        if not scanned:
            # Never print a reassuring summary for a scan that did not happen.
            # "0 of 0 files are clean" is the manufactured confidence this
            # project exists to avoid, in its purest form.
            eprint("wm-hook: no text files were scanned; nothing was checked")
            return 2
        print(f"\n{hits} of {scanned} file(s) carry a covert carrier.")
        if not hits:
            print(
                "A clean result is not evidence of human authorship. Statistical\n"
                "watermarks leave no codepoint trace and are invisible to this test."
            )

    if errors:
        return 2
    return 1 if hits else 0


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        epilog="exit: 0 = all clean, 1 = files were (or would be) modified, 2 = errors. "
               "With --detect, 1 means a covert carrier was found.",
    )
    p.add_argument(
        "paths", nargs="+", type=Path,
        help="files to clean in place, or directories to walk for text files",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if any file would change",
    )
    p.add_argument(
        "--detect",
        action="store_true",
        help="do not write; report whether a covert carrier is present and why. "
             "Answers 'did something embed hidden data here', never 'was this "
             "written by an AI' — the second needs a key nobody has published.",
    )
    p.add_argument("--json", action="store_true", help="machine-readable --detect output")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="with --detect, report clean files too")
    p.add_argument("--version", action="version", version=f"%(prog)s {_version()}")
    args = p.parse_args()

    # A directory becomes its text files. pre-commit always passes an explicit
    # list, so this only ever fires for a human pointing at a project.
    paths = list(iter_text_files(args.paths))

    if args.detect:
        return detect(paths, as_json=args.json, verbose=args.verbose)

    changed = 0
    errors = 0
    for path in paths:
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
