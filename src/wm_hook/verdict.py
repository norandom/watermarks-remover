"""Is a covert carrier present in this text? A one-sided test.

This module answers the one question in the project that is actually tractable.
"Which model wrote this text" is not answerable without the generating key, and
nothing here pretends otherwise. "Did something deliberately embed hidden data
in this text" is answerable, often decisively, and that is what this reports.

The asymmetry is the whole design, and it is not a limitation to be apologised
for -- it is what makes the positive result worth anything:

    a positive is strong     an unexplained, structured carrier does not occur
                             by accident. Text does not grow byte-aligned runs
                             of zero-width characters between Latin letters.

    a negative is worthless  as evidence of human authorship. A statistical
                             watermark leaves no codepoint trace at all, so a
                             clean scan is exactly what an AI-written file is
                             expected to look like.

Reporting these two as though they were the same measurement -- a "% AI"
number -- would be the central dishonesty this project exists to avoid.

Presence alone is not the test either. Almost every invisible codepoint in a
real source tree is legitimate, so the residual after ``carriers.explain`` is
the input here, and structure is what promotes a residual to a finding:

    run length          debris is isolated; payloads are contiguous
    binary alphabet     exactly two codepoints repeating is a bit stream
    byte alignment      a length that is a multiple of 8 was packed
    Latin context       orthographic joiners occur in Indic, Arabic and Thai,
                        never between two ASCII letters
    periodicity         evenly spaced carriers encode per token
    tag characters      one sanctioned use exists (subdivision flags); the
                        exemption is already applied, so anything left is
                        deliberate
    decodability        the payload reads as ASCII

Base rates come from the dated corpus (2026-08-16): zero carriers established
across 1,155 text files in 8 repositories, scanned unexcluded. By the rule of
three that bounds the per-file false-positive rate at 0.26% with 95%
confidence. Two of those repositories were written almost entirely by coding
agents and both scan clean, which puts sensitivity to AI *authorship* at
approximately zero. Specific, not sensitive.
"""

from __future__ import annotations

import itertools
import statistics
from dataclasses import dataclass, field

from wm_hook.carriers import carrier_class, following_base, preceding_base, scan
from wm_hook.payload import extract

# Verdict levels, in increasing order of what they establish.
NONE = "none"
BENIGN = "benign"
ANOMALY = "anomaly"
CARRIER = "carrier"
PAYLOAD = "payload"

LEVEL_ORDER = (NONE, BENIGN, ANOMALY, CARRIER, PAYLOAD)

BASELINE_DATE = "2026-08-16"

#: The original Layer A survey: 11 repositories, zero private-use codepoints.
#: Cited only for the private-use claim, which is what it measured.
BASELINE_FILES = 1268

#: The verdict false-positive corpus: 8 external repositories scanned
#: unexcluded, zero carriers established. A different measurement from the one
#: above, so it gets a different constant -- sharing one would let the two
#: numbers drift into each other silently, which in a project that reports
#: rates is the failure mode that matters most.
FP_CORPUS_FILES = 1155
FP_CORPUS_REPOS = 8

#: Rule-of-three 95% upper bound on the per-file false-positive rate, given
#: zero observed positives in FP_CORPUS_FILES trials.
FALSE_POSITIVE_BOUND_PCT = round(100 * 3 / FP_CORPUS_FILES, 2)


@dataclass(frozen=True)
class Evidence:
    """One structural reason to believe a residual is payload, not debris."""

    name: str
    weight: int
    detail: str

    def to_dict(self) -> dict:
        return {"name": self.name, "weight": self.weight, "detail": self.detail}


@dataclass
class Verdict:
    level: str
    confidence: str
    carriers: int = 0
    explained: int = 0
    unexplained: int = 0
    score: int = 0
    bits_available: int = 0
    evidence: list[Evidence] = field(default_factory=list)
    payloads: list[dict] = field(default_factory=list)
    by_class: dict[str, int] = field(default_factory=dict)

    @property
    def carrier_present(self) -> bool:
        """True only when a deliberate covert carrier is established."""
        return self.level in (CARRIER, PAYLOAD)

    @property
    def headline(self) -> str:
        return {
            NONE: "no invisible carrier of any kind",
            BENIGN: "invisible characters present, all legitimate",
            ANOMALY: "unexplained carrier, but no structure to call it payload",
            CARRIER: "covert carrier present -- something embedded hidden data",
            PAYLOAD: "covert carrier present, and it decodes",
        }[self.level]

    @property
    def means(self) -> str:
        """What the verdict licenses, stated in the direction that is valid."""
        if self.carrier_present:
            return (
                "Something deliberately embedded hidden data in this text. It "
                "does not identify what: a model vendor, a watermarking "
                "service, a CMS, a plagiarism tracker and an attacker all "
                "leave the same evidence. Read the payload if there is one -- "
                "that is the only attribution that is evidence rather than "
                "inference."
            )
        if self.level == ANOMALY:
            return (
                "An invisible character is present that no legitimate use "
                "explains, but it is isolated and unstructured. Copy-paste "
                "debris from a web page or an editor looks exactly like this. "
                "Worth removing, not worth concluding anything from."
            )
        return (
            "No covert carrier. This is NOT evidence that a human wrote the "
            "text. A statistical watermark leaves no codepoint trace, so an "
            f"AI-written file is expected to look like this: the {BASELINE_DATE} "
            f"corpus established zero carriers across {FP_CORPUS_FILES} files "
            f"in {FP_CORPUS_REPOS} repositories, two of which were written "
            "almost entirely by coding agents."
        )

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "carrier_present": self.carrier_present,
            "confidence": self.confidence,
            "headline": self.headline,
            "means": self.means,
            "carriers": self.carriers,
            "explained": self.explained,
            "unexplained": self.unexplained,
            "score": self.score,
            "bits_available": self.bits_available,
            "by_class": self.by_class,
            "evidence": [e.to_dict() for e in self.evidence],
            "payloads": self.payloads,
        }


def _runs(offsets: list[int]) -> list[list[int]]:
    """Group offsets into maximal contiguous runs."""
    out: list[list[int]] = []
    for off in offsets:
        if out and off == out[-1][-1] + 1:
            out[-1].append(off)
        else:
            out.append([off])
    return out


def _is_latin_letter(ch: str) -> bool:
    return bool(ch) and ch.isascii() and ch.isalpha()


def _nearest_visible(text: str, i: int, step: int) -> str:
    """The nearest character in one direction that renders as something.

    ``carriers.preceding_base`` deliberately skips only the classes that chain
    in legitimate sequences, because that is what ``explain`` needs. Here the
    question is different -- what ordinary text surrounds this run -- so every
    carrier class is skipped, including private-use. Without that, a run of
    private-use codepoints only ever sees itself as its own context.
    """
    j = i + step
    while 0 <= j < len(text) and carrier_class(ord(text[j])) is not None:
        j += step
    return text[j] if 0 <= j < len(text) else ""


def _in_ascii_text(text: str, i: int) -> bool:
    """Whether this offset sits inside ordinary ASCII prose or code.

    Line breaks and tabs count as ordinary context. Requiring printability
    would dismiss a carrier parked at end of line, which is the most natural
    place to put one, not a reason to ignore it.
    """
    around = [_nearest_visible(text, i, -1), _nearest_visible(text, i, 1)]
    seen = [c for c in around if c]
    return bool(seen) and all(
        c.isascii() and (c.isprintable() or c in "\r\n\t") for c in seen
    )


def structural_evidence(text: str, unexplained: list[tuple[int, str]]) -> list[Evidence]:
    """Reasons to read a residual as payload rather than as debris.

    Each test is independent and names itself in the output, so a verdict can
    always be argued with rather than merely believed.
    """
    ev: list[Evidence] = []
    if not unexplained:
        return ev

    offsets = [o for o, _ in unexplained]
    kinds = {o: k for o, k in unexplained}

    for run in _runs(offsets):
        if len(run) < 4:
            continue
        chars = {text[o] for o in run}
        kind = kinds[run[0]]
        ev.append(Evidence(
            "run", 2,
            f"{len(run)} consecutive unexplained {kind} at offset {run[0]}",
        ))
        if len(run) >= 8 and len(chars) == 2:
            ev.append(Evidence(
                "binary_alphabet", 3,
                f"run of {len(run)} uses exactly two codepoints "
                f"({' '.join(f'U+{ord(c):04X}' for c in sorted(chars))}) -- a bit stream",
            ))
        if len(run) >= 8 and len(run) % 8 == 0:
            ev.append(Evidence(
                "byte_aligned", 1,
                f"run length {len(run)} is a multiple of 8",
            ))

    latin = [
        o for o in offsets
        if _is_latin_letter(preceding_base(text, o)) and _is_latin_letter(following_base(text, o))
    ]
    if latin:
        ev.append(Evidence(
            "latin_context", 2,
            f"{len(latin)} carrier(s) between two ASCII letters, where no "
            f"script needs one (first at offset {latin[0]})",
        ))

    tags = [o for o in offsets if kinds[o] == "tag_chars"]
    if tags:
        ev.append(Evidence(
            "tag_outside_flag", 3,
            f"{len(tags)} tag character(s) outside a subdivision flag sequence; "
            "the tag block has no other sanctioned use",
        ))

    # Private-use codepoints have no assigned meaning at all. Legitimate uses
    # exist -- Nerd Font glyphs in a shell config, Apple's logo, CJK gaiji --
    # but they sit beside their own scripts, not inside ASCII prose or code.
    pua = [o for o in offsets if kinds[o] == "private_use" and _in_ascii_text(text, o)]
    if pua:
        ev.append(Evidence(
            "private_use_in_text", 2,
            f"{len(pua)} private-use codepoint(s) inside ordinary ASCII text, "
            f"where the codepoints have no assigned meaning; the {BASELINE_DATE} "
            f"baseline found zero in {BASELINE_FILES} files",
        ))

    gaps = [b - a for a, b in itertools.pairwise(offsets) if b - a > 1]
    if len(gaps) >= 3:
        mean = statistics.fmean(gaps)
        if mean > 1 and statistics.pstdev(gaps) / mean < 0.25:
            ev.append(Evidence(
                "periodic", 2,
                f"{len(gaps) + 1} carriers spaced evenly (~{mean:.0f} chars apart), "
                "consistent with one mark per token",
            ))

    return ev


#: Bits a single carrier of each class can carry, used for the capacity figure.
_BITS = {
    "tag_chars": 7,
    "private_use": 7,
    "variation_selector": 8,
    "zero_width": 1,
    "bidi": 1,
    "space_homoglyph": 1,
    "other_format": 1,
}


def classify(text: str) -> Verdict:
    """Grade a text from 'nothing here' to 'covert carrier, and it decodes'."""
    found, explained_n = scan(text)
    if not found:
        return Verdict(level=NONE, confidence="n/a")

    unexplained = [(o, k) for o, k, why in found if why is None]
    by_class: dict[str, int] = {}
    for _, k in unexplained:
        by_class[k] = by_class.get(k, 0) + 1

    base = Verdict(
        level=BENIGN,
        confidence="n/a",
        carriers=len(found),
        explained=explained_n,
        unexplained=len(unexplained),
        by_class=by_class,
        bits_available=sum(_BITS.get(k, 1) for _, k in unexplained),
    )
    if not unexplained:
        return base

    base.evidence = structural_evidence(text, unexplained)
    base.score = sum(e.weight for e in base.evidence)

    # A decoded payload is the strongest evidence available, because it is
    # evidence of content and not merely of shape.
    decoded = [p for p in extract(text) if p.confidence in ("confirmed", "probable")]
    if decoded:
        base.payloads = [p.to_dict() for p in decoded]
        base.level = PAYLOAD
        base.confidence = "high" if any(
            p.confidence == "confirmed" for p in decoded
        ) else "moderate"
        return base

    if base.score >= 4:
        base.level, base.confidence = CARRIER, "high"
    elif base.score >= 2:
        base.level, base.confidence = CARRIER, "moderate"
    else:
        base.level, base.confidence = ANOMALY, "low"
    return base


def render(path: str, v: Verdict, *, verbose: bool = False) -> list[str]:
    """Human-readable lines for one file."""
    tag = {
        NONE: "CLEAN   ", BENIGN: "CLEAN   ", ANOMALY: "ANOMALY ",
        CARRIER: "CARRIER!", PAYLOAD: "CARRIER!",
    }[v.level]
    out = [f"{tag} {path}: {v.headline}"]
    if v.carriers:
        out.append(
            f"         {v.carriers} carrier(s), {v.explained} explained, "
            f"{v.unexplained} unexplained"
        )
    for e in v.evidence:
        out.append(f"         + {e.name} (+{e.weight}): {e.detail}")
    for p in v.payloads:
        out.append(f"         > {p['scheme']} @{p['offset']} [{p['confidence']}]")
        out.append(f"           {p['decoded']!r}")
        if p["identifiers"]:
            out.append(f"           identifies: {', '.join(p['identifiers'])}")
    if v.carrier_present or verbose:
        out.append(f"         confidence: {v.confidence}; capacity {v.bits_available} bits")
        out.append(f"         {v.means}")
    return out
