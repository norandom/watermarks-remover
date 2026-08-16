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

    uvx --from 'git+https://github.com/norandom/watermarks-remover' wm-hook --help
    pipx install 'git+https://github.com/norandom/watermarks-remover'

.pre-commit-config.yaml in any target repo (pre-commit builds the isolated
env itself, so this needs nothing preinstalled beyond pre-commit):

    - repo: https://github.com/norandom/watermarks-remover
      rev: v0.1.0a2
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
import collections
import json
import sys
from importlib import metadata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "core"))

from common import MAX_INPUT_BYTES, eprint, looks_binary, safe_write_text  # noqa: E402
from text_unicode import clean_text  # noqa: E402

from wm_hook import signing as _signing  # noqa: E402
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


#: What each verdict level means, in words a reader does not have to decode.
_LEVEL_BLURB = {
    _verdict.NONE: "no invisible characters at all",
    _verdict.BENIGN: "invisible characters, all legitimate",
    _verdict.ANOMALY: "unexplained, but too little to call it hidden data",
    _verdict.CARRIER: "hidden data found",
    _verdict.PAYLOAD: "hidden data found, and it can be read",
}


def _summary(results: list[dict], scanned: int, hits: int) -> None:
    """The default report: counts first, then only the files that matter.

    Printing every file, including the clean ones, buried ten real findings in
    forty lines of "all legitimate". Worse, the per-file output never answered
    the question a reader actually has after a clean run: was there any
    invisible material here at all? The counts answer it in one glance.
    """
    counts = collections.Counter(
        r["level"] for r in results if "level" in r
    )
    print(f"{scanned} file(s) scanned\n")
    for level in _verdict.LEVEL_ORDER:
        n = counts.get(level, 0)
        if n:
            print(f"  {n:>5}  {level:<8} {_LEVEL_BLURB[level]}")

    if hits:
        print("\nFiles with hidden data:")
        flagged = [r for r in results if r.get("carrier_present")]
        width = max(len(r["path"]) for r in flagged)
        for r in flagged:
            v_ev = r["payloads"] or r["evidence"]
            reason = (
                "reads: " + ", ".join(repr(p["decoded"]) for p in r["payloads"][:2])
                if r["payloads"]
                else ", ".join(e["name"] for e in r["evidence"][:3])
            )
            print(f"  {r['path']:<{width}}  {reason}" if v_ev else f"  {r['path']}")
        print(f"\n{hits} of {scanned} file(s) carry hidden data. Run -v for the reasons.")
    else:
        print(f"\nNo hidden data in {scanned} file(s).")

    # Said once, at the end, rather than repeated under every finding.
    print(
        "\nA clean result does not mean a human wrote the text. It only means\n"
        "nothing is hidden in the characters. Anthropic marks Claude output by\n"
        "changing which words are chosen, which leaves no trace this can see."
    )


def detect(
    paths: list[Path], *, as_json: bool, verbose: bool,
) -> int:
    """Report whether hidden data is present. Exit 1 if any is.

    This is a one-sided test and the output says so once per run. A positive
    shows that something embedded hidden data; a clean result shows nothing
    about whether a human wrote the text.
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
        # Verbose prints everything above "nothing here". The default prints
        # nothing per-file and lets the summary do the work.
        if verbose and v.level != _verdict.NONE:
            lines.extend(_verdict.render(str(path), v, verbose=True))

    scanned = len(paths) - errors

    if as_json:
        json.dump(results, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        if errors:
            return 2
        return 1 if hits else 0

    for line in lines:
        print(line)
    if lines:
        print()
    if not scanned:
        # Never print a reassuring summary for a scan that did not happen.
        # "0 of 0 files are clean" is manufactured confidence in its purest form.
        eprint("wm-hook: no text files were scanned; nothing was checked")
        return 2
    _summary(results, scanned, hits)

    if errors:
        return 2
    return 1 if hits else 0


def _load_key(path: Path | None) -> bytes | None:
    if path is None:
        return None
    try:
        key = path.read_bytes()
    except OSError as e:
        raise SystemExit(f"wm-hook: cannot read key {path}: {e}")
    if len(key) < 16:
        raise SystemExit(f"wm-hook: {path} is too short to be a key")
    return key


def sign_files(paths: list[Path], label: str, key: bytes | None) -> int:
    """Add an invisible label to each file. Exit 2 if any could not be signed."""
    errors = 0
    for path in paths:
        text, why = read_text(path)
        if text is None:
            eprint(f"wm-hook: {path}: {why}")
            errors += 1
            continue
        try:
            signed = _signing.sign(text, label, key)
        except _signing.SigningError as e:
            eprint(f"wm-hook: {path}: {e}")
            errors += 1
            continue
        try:
            safe_write_text(path, signed)
        except OSError as e:
            eprint(f"wm-hook: {path}: cannot write: {e}")
            errors += 1
            continue
        added = len(signed) - len(text)
        print(f"signed  {path}  ({added} invisible characters added)")

    if not errors:
        if key is None:
            print(
                "\nThis is a label, not proof. Anyone who reads it can copy it onto\n"
                "other text. Pass --key to bind it to this text's content."
            )
        else:
            print("\nBound to the text. Editing the text invalidates the mark.")
        print(
            "Any carrier cleaner removes it, including this tool. Do not run\n"
            "wm-hook without --sign over a signed file, and exclude signed files\n"
            "from the pre-commit hook."
        )
    return 2 if errors else 0


def verify_files(paths: list[Path], key: bytes | None) -> int:
    """Report the mark on each file. Exit 1 if any is missing or invalid."""
    bad = 0
    for path in paths:
        text, why = read_text(path)
        if text is None:
            print(f"ERROR    {path}: {why}")
            bad += 1
            continue
        r = _signing.verify(text, key)
        if r.label is None:
            print(f"UNSIGNED {path}")
            bad += 1
            continue
        state = {True: "VALID   ", False: "INVALID ", None: "UNKEYED "}[r.valid]
        print(f"{state} {path}: {r.label!r}")
        print(f"         {r.detail}")
        if r.valid is not True:
            bad += 1
    print(
        "\nA missing mark proves nothing: removing one is trivial and leaves no\n"
        "trace that anything was there."
    )
    return 1 if bad else 0


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
                   help="with --detect, show why each flagged file was flagged")
    p.add_argument(
        "--sign", metavar="LABEL",
        help="add LABEL to each file as invisible characters. Without --key "
             "this is a label anyone can copy, not proof of authorship.",
    )
    p.add_argument(
        "--verify", action="store_true",
        help="report the invisible label on each file, and whether --key binds it",
    )
    p.add_argument(
        "--key", type=Path, metavar="FILE",
        help="secret key binding a signature to the text it signs. Create one "
             "with --keygen.",
    )
    p.add_argument(
        "--keygen", type=Path, metavar="FILE",
        help="write a new random key to FILE and exit",
    )
    p.add_argument(
        "--include-hidden-files", action="store_true",
        help="also scan dot files and dot directories. Off by default: a scan "
             "of a project root otherwise reports on .claude/, .kiro/ and "
             "every other tool's config, which you did not write.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {_version()}")
    args = p.parse_args()

    if args.keygen:
        # Written before anything is read, so a mistyped path fails cheaply.
        try:
            _signing.write_key(args.keygen)
        except (_signing.SigningError, OSError) as e:
            raise SystemExit(f"wm-hook: {e}")
        print(f"wrote a new key to {args.keygen}. Keep it secret: anyone holding")
        print("it can produce marks indistinguishable from yours.")
        return 0

    if args.sign and args.verify:
        raise SystemExit("wm-hook: --sign and --verify are separate operations")
    if args.detect and (args.sign or args.verify):
        raise SystemExit("wm-hook: --detect looks for other people's marks; "
                         "--sign and --verify handle your own")

    # A directory becomes its text files. pre-commit always passes an explicit
    # list, so this only ever fires for a human pointing at a project.
    paths = list(iter_text_files(args.paths, include_hidden=args.include_hidden_files))
    if not paths:
        eprint("wm-hook: no text files were found; nothing was done")
        return 2

    if args.sign:
        return sign_files(paths, args.sign, _load_key(args.key))
    if args.verify:
        return verify_files(paths, _load_key(args.key))
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
