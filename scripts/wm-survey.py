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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wm_hook.carriers import carrier_class, explain  # noqa: E402
from wm_hook.payload import carrier_signature, extract  # noqa: E402
from wm_hook.verdict import LEVEL_ORDER, classify  # noqa: E402

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



@dataclass
class FileResult:
    path: str
    carriers: int = 0
    explained: int = 0
    by_class: collections.Counter = field(default_factory=collections.Counter)
    unexplained_detail: list = field(default_factory=list)
    payloads: list = field(default_factory=list)
    signature: dict = field(default_factory=dict)
    verdict: dict = field(default_factory=dict)

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
    res.verdict = classify(text).to_dict()
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
    "carrier_verdict": {
        "name": "Carrier verdict - is hidden data deliberately embedded?",
        "detects": "unexplained carriers with the structure of data: contiguous "
                   "runs, two-codepoint alphabets, byte-aligned lengths, "
                   "placement between ASCII letters, even spacing",
        "blind_to": "anything that leaves no codepoint trace, and any carrier "
                    "short and isolated enough to be indistinguishable from "
                    "copy-paste debris",
        "applicable_when": "always, but the answer is one-sided",
        "status": "operational",
        "why": "This is the tractable question. A positive establishes "
               "deliberate embedding by something; it never identifies what. "
               "A negative establishes nothing about authorship, because a "
               "statistical watermark leaves no codepoint trace at all.",
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
    channels["carrier_verdict"]["files_covered"] = scanned
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
        "verdicts": verdict_summary(files),
        "attribution": attribute(root),
    }


def verdict_summary(files: list[FileResult]) -> dict:
    """The one question this project can answer: is a covert carrier present?

    Reported as a count per level rather than as a single percentage, because
    a percentage would invite reading it as "% AI", which it is not. The
    ``carrier_present`` count is the only number here that establishes
    anything, and it establishes deliberate embedding -- not authorship.
    """
    levels = collections.Counter(f.verdict.get("level", "none") for f in files)
    positives = [f for f in files if f.verdict.get("carrier_present")]
    return {
        "by_level": {lv: levels.get(lv, 0) for lv in LEVEL_ORDER},
        "carrier_present": len(positives),
        "files": [
            {"path": f.path,
             "level": f.verdict["level"],
             "confidence": f.verdict["confidence"],
             "evidence": [e["name"] for e in f.verdict["evidence"]],
             "bits": f.verdict["bits_available"]}
            for f in sorted(positives, key=lambda x: -x.verdict["score"])[:20]
        ],
        "one_sided": (
            "A positive establishes that something deliberately embedded hidden "
            "data. A negative establishes nothing about authorship: a "
            "statistical watermark leaves no codepoint trace, so an AI-written "
            "file is expected to score zero here."
        ),
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

    vs = rep.get("verdicts")
    if vs:
        print("\n  COVERT CARRIER PRESENT?")
        for lv, n in vs["by_level"].items():
            if n:
                print(f"    {lv:<22} {n} file(s)")
        print(f"    -> established in           {vs['carrier_present']} file(s)")
        for f in vs["files"]:
            print(f"       {f['path']}  [{f['level']}/{f['confidence']}] "
                  f"{', '.join(f['evidence'])}  {f['bits']} bits")
        print(f"    {vs['one_sided']}")

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
