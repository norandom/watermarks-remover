#!/usr/bin/env python3
"""Survey a tree for AI provenance signal, and report honest rates.

This is a research instrument, not part of the pre-commit hook. It answers two
questions the hook does not:

  1. How much invisible-carrier material is actually present, and how much of
     it is legitimate rather than a watermark?
  2. Which agent, if any, can be attributed as an author -- and on what basis?

Both answers are reported as rates so they can be tracked over time.

A note on the word "detection". A naive detector reports every invisible
codepoint as a hit and claims a high detection rate. That number is worthless:
in practice almost every hit is an emoji presentation selector, a script
joiner doing real orthographic work, or a byte-order mark. This tool therefore
separates three quantities and never collapses them:

    carriers found      every invisible / format codepoint present
    explained           those attributable to a documented legitimate cause
    unexplained         the residual -- the only watermark candidates

Only the residual is evidence of anything. Reporting "carriers found" as a
detection rate would overstate the result by roughly two orders of magnitude
against the corpus this was written for.

Usage:
    python scripts/wm-survey.py <path> [<path> ...] [--json]
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from payload import carrier_signature, extract  # noqa: E402

TEXT_EXTS = {
    ".md", ".markdown", ".mdx", ".qmd", ".rmd", ".txt", ".rst", ".tex",
    ".py", ".ps1", ".psm1", ".psd1", ".sh", ".bash", ".zsh",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".css", ".html",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml",
    ".rs", ".go", ".c", ".h", ".cpp", ".hpp", ".java", ".rb", ".sql", ".po",
}
SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".pytest_cache", "target", ".mypy_cache", ".ruff_cache", ".tox", "site",
}

# Overt agent artifacts. Each tool writes these into a project itself.
DISK_MARKERS: dict[str, tuple[str, ...]] = {
    "claude":  (".claude", "CLAUDE.md", ".mcp.json"),
    "codex":   ("AGENTS.md", ".agents", ".specify", ".codex"),
    "copilot": (".github/copilot-instructions.md",),
    "cursor":  (".cursor", ".cursorrules"),
    "gemini":  (".gemini", "GEMINI.md"),
    "aider":   (".aider.conf.yml", ".aiderignore"),
}

COMMIT_TRAILERS: dict[str, re.Pattern[str]] = {
    "claude":  re.compile(r"Co-Authored-By:\s*Claude|Generated with \[Claude Code\]", re.I),
    "codex":   re.compile(r"Co-Authored-By:\s*(Codex|ChatGPT)", re.I),
    "copilot": re.compile(r"Co-Authored-By:\s*(GitHub )?Copilot", re.I),
    "devin":   re.compile(r"Co-Authored-By:\s*Devin", re.I),
    "cursor":  re.compile(r"Co-Authored-By:\s*Cursor", re.I),
}

ZERO_WIDTH = {0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF}
BIDI = {0x200E, 0x200F, 0x061C, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
        0x2066, 0x2067, 0x2068, 0x2069}
SPACE_HOMOGLYPHS = {0x00A0, 0x1680, 0x202F, 0x205F, 0x3000} | set(range(0x2000, 0x200B))

# Scripts in which a zero-width joiner or non-joiner is orthography, not payload.
JOINING_RANGES = (
    (0x0600, 0x08FF), (0x0900, 0x0DFF), (0x0F00, 0x109F),
    (0x1780, 0x17FF), (0x1800, 0x18AF),
)
# Scripts that use U+200B as a word or line-break separator.
ZWSP_SEPARATOR_RANGES = ((0x0E00, 0x0E7F), (0x0E80, 0x0EFF),
                         (0x1780, 0x17FF), (0x1000, 0x109F))


def carrier_class(cp: int) -> str | None:
    if 0xE000 <= cp <= 0xF8FF or 0xF0000 <= cp <= 0xFFFFD or 0x100000 <= cp <= 0x10FFFD:
        return "private_use"
    if 0xE0000 <= cp <= 0xE007F:
        return "tag_chars"
    if 0xFE00 <= cp <= 0xFE0F or 0xE0100 <= cp <= 0xE01EF:
        return "variation_selector"
    if cp in ZERO_WIDTH:
        return "zero_width"
    if cp in BIDI:
        return "bidi"
    if cp in SPACE_HOMOGLYPHS:
        return "space_homoglyph"
    if unicodedata.category(chr(cp)) == "Cf":
        return "other_format"
    return None


def _in(cp: int, ranges) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


# Emoji bases outside the Symbol categories. These five are exactly the ones
# the cleaner's own base table omits, and the survey prototype inherited the
# same gap -- it reported three of them in design.md as watermark candidates.
_EXTRA_EMOJI_BASES = {
    0x2139,  # information source
    0x203C,  # double exclamation mark
    0x2049,  # exclamation question mark
    0x2934,  # right arrow curving up
    0x2935,  # right arrow curving down
    0x00A9, 0x00AE, 0x2122,  # copyright, registered, trade mark
    0x3030, 0x303D, 0x3297, 0x3299,
}


def _is_symbolish(ch: str) -> bool:
    cp = ord(ch)
    return (
        unicodedata.category(ch) in ("So", "Sk", "Sm")
        or 0x1F000 <= cp <= 0x1FAFF
        or cp in _EXTRA_EMOJI_BASES
    )


def _preceding_base(text: str, i: int) -> str:
    """The nearest preceding character that is not itself a carrier.

    A backward look that stops at text[i-1] fails on any chained sequence: in
    the emoji U+2764 U+FE0F U+200D U+1F525, the character before the joiner is
    a variation selector, not the heart. Skipping carriers is what lets the
    joiner be recognised as emoji glue rather than a payload.
    """
    j = i - 1
    while j >= 0 and carrier_class(ord(text[j])) in (
        "variation_selector", "zero_width", "tag_chars",
    ):
        j -= 1
    return text[j] if j >= 0 else ""


def _following_base(text: str, i: int) -> str:
    j = i + 1
    while j < len(text) and carrier_class(ord(text[j])) in (
        "variation_selector", "zero_width", "tag_chars",
    ):
        j += 1
    return text[j] if j < len(text) else ""


def explain(text: str, i: int) -> str | None:
    """Why this carrier is legitimate, or None if it is unexplained."""
    cp = ord(text[i])
    prev = _preceding_base(text, i)
    nxt = _following_base(text, i)
    kind = carrier_class(cp)

    if kind == "variation_selector":
        if prev and _is_symbolish(prev):
            return "emoji or symbol presentation selector"
        if prev and (0x3400 <= ord(prev) <= 0x9FFF or 0xF900 <= ord(prev) <= 0xFAFF):
            return "ideographic variation sequence"
    if cp in (0x200C, 0x200D):
        if prev and nxt and _in(ord(prev), JOINING_RANGES) and _in(ord(nxt), JOINING_RANGES):
            return "script joiner between same-script letters"
        if prev and _in(ord(prev), JOINING_RANGES):
            return "script joiner at a word boundary (word-final virama etc.)"
        if cp == 0x200D and prev and nxt and _is_symbolish(prev) and _is_symbolish(nxt):
            return "emoji zero-width joiner sequence"
    if cp == 0x200B and prev and _in(ord(prev), ZWSP_SEPARATOR_RANGES):
        return "word separator in a script without spaces"
    if cp == 0xFEFF and i == 0:
        return "byte-order mark at offset zero"
    if kind == "space_homoglyph":
        if cp == 0x3000 and prev and 0x2E80 <= ord(prev) <= 0x9FFF:
            return "ideographic space in CJK text"
        return "typographic space (no-break, narrow, thin)"
    if kind == "tag_chars" and 0xE0020 <= cp <= 0xE007F:
        window = text[max(0, i - 8):i]
        if "\U0001F3F4" in window:
            return "subdivision flag tag sequence"
    if kind == "bidi" and cp in (0x200E, 0x200F, 0x061C):
        return "directional mark in mixed-direction text"
    return None


@dataclass
class FileResult:
    path: str
    carriers: int = 0
    explained: int = 0
    by_class: collections.Counter = field(default_factory=collections.Counter)
    unexplained_detail: list = field(default_factory=list)
    payloads: list = field(default_factory=list)
    signature: dict = field(default_factory=dict)

    @property
    def unexplained(self) -> int:
        return self.carriers - self.explained


def scan_file(path: Path, root: Path) -> FileResult | None:
    try:
        raw = path.read_bytes()
        if b"\x00" in raw[:8192]:
            return None
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    res = FileResult(path=str(path.relative_to(root)).replace("\\", "/"))
    res.payloads = [p.to_dict() for p in extract(text)]
    res.signature = carrier_signature(text)
    for i, ch in enumerate(text):
        kind = carrier_class(ord(ch))
        if not kind:
            continue
        res.carriers += 1
        res.by_class[kind] += 1
        why = explain(text, i)
        if why:
            res.explained += 1
        else:
            res.unexplained_detail.append(
                {"offset": i, "codepoint": f"U+{ord(ch):04X}",
                 "name": unicodedata.name(ch, "?"), "class": kind}
            )
    return res


# ---------------------------------------------------------------------------
# Applicability
# ---------------------------------------------------------------------------
#
# A detector that reports "clean" when it was never able to see anything is
# worse than one that reports nothing at all: it manufactures confidence. Every
# channel therefore declares what it can and cannot speak to, and a zero result
# is qualified by the coverage that produced it.
#
# This is the same discipline as the carriers / explained / unexplained split.
# There, conflating "found" with "suspicious" overstated by two orders of
# magnitude. Here, conflating "no signal" with "wrong instrument" would do the
# same in the opposite direction.

CHANNELS = {
    "layer_a": {
        "name": "Layer A - invisible and format codepoints",
        "detects": "zero-width runs, tag-block payloads, orphan variation "
                   "selectors, private-use characters, bidi overrides, space "
                   "homoglyphs",
        "blind_to": "anything not encoded in the choice of codepoint",
        "applicable_when": "always; every file is scannable",
        "status": "operational",
    },
    "payload": {
        "name": "Payload decoding - what a carrier actually says",
        "detects": "tag-block ASCII, variation-selector bytes, zero-width bit "
                   "streams, private-use runs",
        "blind_to": "encrypted or compressed payloads, and any scheme whose "
                    "encoding is not one of the four published ones",
        "applicable_when": "a carrier is present at all",
        "status": "operational",
        "why": "This is the only attribution that is evidence rather than "
               "inference. A payload reading gen=claude-opus-4 names its "
               "producer outright; a style score never can.",
    },
    "metadata": {
        "name": "Channel C - declared provenance metadata",
        "detects": "nothing",
        "blind_to": "everything in this channel",
        "applicable_when": "never; removed from scope",
        "status": "unavailable",
        "why": "Frontmatter keys and container metadata are a declared field, "
               "not hidden material in text. Out of scope; see "
               ".kiro/steering/scope.md.",
    },
    "statistical": {
        "name": "Channel B - statistical token-sampling watermarks",
        "detects": "nothing",
        "blind_to": "everything in this channel",
        "applicable_when": "never, with currently public information",
        "status": "unavailable",
        "why": "Detection requires the scheme and keys used at generation. "
               "Anthropic states marking covers Claude Code but has not "
               "published a detector. The exclusion of 'very short passages "
               "with too little text for a reliable signal' indicates a "
               "statistical rather than a codepoint mark, which a Layer A "
               "scan cannot see by construction.",
    },
    "stylometric": {
        "name": "Stylometry - AI cadence in prose",
        "detects": "essay and marketing register markers",
        "blind_to": "technical documentation, specifications, commit prose, "
                    "and source code, where its markers do not occur",
        "applicable_when": "long-form prose in an essay register",
        "status": "not wired in",
        "why": "Measured against upstream's scorer: 0.685 on AI marketing "
               "prose, 0.029 on Claude-authored technical documentation. It "
               "discriminates register, not authorship. Reporting its zero on "
               "a technical corpus as 'clean' would be false confidence.",
    },
}


def applicability(rep: dict) -> dict:
    """What this run could and could not have detected."""
    scanned = rep["files_scanned"]
    channels = {k: dict(v) for k, v in CHANNELS.items()}
    channels["layer_a"]["files_covered"] = scanned
    channels["payload"]["files_covered"] = len(rep.get("payloads", []))
    channels["metadata"]["files_covered"] = 0
    channels["statistical"]["files_covered"] = 0
    channels["stylometric"]["files_covered"] = 0

    operational = [k for k, v in channels.items() if v["status"] == "operational"]
    return {
        "channels": channels,
        "operational_channels": operational,
        "verdict": (
            "A zero residual here means no deterministic Layer A carrier was "
            "found. It does not mean the text was written by a human, and it "
            "does not rule out a statistical watermark, which no publicly "
            "available tool can currently detect."
        ),
    }


def git(repo: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        return r.stdout if r.returncode == 0 else ""
    except Exception:
        return ""


def attribute(root: Path) -> dict:
    """Attribute authorship from OVERT evidence only."""
    disk = sorted({a for a, paths in DISK_MARKERS.items()
                   if any((root / p).exists() for p in paths)})
    trailers: collections.Counter = collections.Counter()
    total = 0
    if (root / ".git").exists():
        log = git(root, "log", "--format=%s%x00%b%x01", "-n", "1000")
        for entry in log.split("\x01"):
            if not entry.strip():
                continue
            total += 1
            for agent, rx in COMMIT_TRAILERS.items():
                if rx.search(entry):
                    trailers[agent] += 1
    return {
        "disk_markers": disk,
        "commits_scanned": total,
        "commit_trailers": dict(trailers.most_common()),
        "trailer_rate": {a: round(100 * n / total, 1) for a, n in trailers.items()} if total else {},
        "basis": "overt only: declared config directories and commit trailers",
    }


def survey(root: Path, exclude: tuple[str, ...] = ()) -> dict:
    files = []
    excluded = 0
    for f in sorted(root.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in TEXT_EXTS:
            continue
        rel = f.relative_to(root)
        if any(p in SKIP_DIRS for p in rel.parts[:-1]):
            continue
        if exclude and str(rel).replace("\\", "/").startswith(tuple(exclude)):
            excluded += 1
            continue
        r = scan_file(f, root)
        if r:
            files.append(r)

    scanned = len(files)
    with_carriers = [f for f in files if f.carriers]
    with_unexplained = [f for f in files if f.unexplained]
    total_carriers = sum(f.carriers for f in files)
    total_explained = sum(f.explained for f in files)
    by_class: collections.Counter = collections.Counter()
    for f in files:
        by_class.update(f.by_class)

    def pct(n, d):
        return round(100 * n / d, 2) if d else 0.0

    return {
        "root": str(root),
        "files_scanned": scanned,
        "files_excluded": excluded,
        "files_with_carriers": len(with_carriers),
        "files_with_unexplained": len(with_unexplained),
        "rates": {
            "files_with_any_carrier_pct": pct(len(with_carriers), scanned),
            "files_with_unexplained_pct": pct(len(with_unexplained), scanned),
            "carriers_explained_pct": pct(total_explained, total_carriers),
        },
        "carriers_total": total_carriers,
        "carriers_explained": total_explained,
        "carriers_unexplained": total_carriers - total_explained,
        "by_class": dict(by_class.most_common()),
        "unexplained_files": [
            {"path": f.path, "count": f.unexplained, "detail": f.unexplained_detail[:5]}
            for f in sorted(with_unexplained, key=lambda x: -x.unexplained)[:20]
        ],
        "payloads": [
            {"path": f.path, "payloads": f.payloads} for f in files if f.payloads
        ],
        "carrier_signature": dict(
            sum((collections.Counter(f.signature) for f in files),
                collections.Counter()).most_common()
        ),
        "attribution": attribute(root),
    }


def render(rep: dict) -> None:
    r = rep["rates"]
    print(f"\n{'=' * 74}")
    print(f"  {rep['root']}")
    print(f"{'=' * 74}")
    print(f"  files scanned                 {rep['files_scanned']}")
    print(f"  files with any carrier        {rep['files_with_carriers']}  ({r['files_with_any_carrier_pct']}%)")
    print(f"  files with UNEXPLAINED        {rep['files_with_unexplained']}  ({r['files_with_unexplained_pct']}%)")
    print()
    print(f"  carriers found                {rep['carriers_total']}")
    print(f"    explained as legitimate     {rep['carriers_explained']}  ({r['carriers_explained_pct']}%)")
    print(f"    unexplained (candidates)    {rep['carriers_unexplained']}")
    if rep["by_class"]:
        print("\n  by class:")
        for k, v in rep["by_class"].items():
            print(f"    {k:<22} {v}")
    if rep["unexplained_files"]:
        print("\n  unexplained detail:")
        for f in rep["unexplained_files"]:
            print(f"    {f['path']}  x{f['count']}")
            for d in f["detail"]:
                print(f"        @{d['offset']:<7} {d['codepoint']} {d['name']} [{d['class']}]")
    if rep.get("payloads"):
        print("\n  DECODED PAYLOADS:")
        for entry in rep["payloads"]:
            print(f"    {entry['path']}")
            for p in entry["payloads"]:
                print(f"      [{p['confidence']:<11}] {p['scheme']} @{p['offset']}")
                print(f"        {p['decoded']!r}")
                if p["identifiers"]:
                    print(f"        identifies: {', '.join(p['identifiers'])}")

    if rep.get("carrier_signature"):
        print("\n  carrier signature (classes a producer reached for):")
        for k, v in sorted(rep["carrier_signature"].items(), key=lambda kv: -kv[1]):
            print(f"    {k:<22} {v}")

    ap = rep["applicability"]
    print("\n  what this run could detect:")
    for key, ch in ap["channels"].items():
        mark = {"operational": "[on ]", "partial": "[part]",
                "unavailable": "[OFF]", "not wired in": "[OFF]"}[ch["status"]]
        print(f"    {mark} {ch['name']}")
        print(f"           covers {ch['files_covered']} file(s); blind to {ch['blind_to']}")
        if ch.get("why"):
            first = ch["why"].split(". ")[0]
            print(f"           {first}.")
    print(f"\n  {ap['verdict']}")

    a = rep["attribution"]
    print("\n  attribution (overt evidence only):")
    print(f"    config on disk              {', '.join(a['disk_markers']) or '(none)'}")
    if a["commits_scanned"]:
        tr = ", ".join(f"{k}={v} ({a['trailer_rate'][k]}%)" for k, v in a["commit_trailers"].items())
        print(f"    commit trailers             {tr or '(none)'}  of {a['commits_scanned']} commits")
    else:
        print("    commit trailers             (not a git repository)")


def main() -> int:
    p = argparse.ArgumentParser(
        description="Survey a tree for AI provenance signal and report honest rates.",
        epilog="Carriers found is not a detection rate. Only the unexplained residual is evidence.",
    )
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--json", action="store_true", help="emit machine-readable output on stdout")
    p.add_argument(
        "--exclude", action="append", default=[], metavar="PREFIX",
        help="skip paths starting with PREFIX (repeatable). A project's own "
             "carrier fixtures otherwise dominate its findings.",
    )
    args = p.parse_args()

    reports = []
    for path in args.paths:
        if not path.is_dir():
            continue
        rep = survey(path.resolve(), tuple(args.exclude))
        rep["applicability"] = applicability(rep)
        reports.append(rep)
    if args.json:
        json.dump(reports, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        for rep in reports:
            render(rep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
