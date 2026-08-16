#!/usr/bin/env python3
"""Decode what a carrier actually says.

Reporting "20 tag characters found" is the wrong output. A tag-block run is an
invisible mirror of ASCII, so it usually *spells something* -- and what it
spells is the attribution. A payload reading ``gen=claude-opus-4;ts=2026-08-16``
identifies its producer far more definitively than any stylometric inference,
and unlike a style score it is evidence rather than a prior.

This is why the distinction between "which agent wrote this text" and "which
agent embedded this carrier" matters. The first is unanswerable without a key.
The second is often trivial: read the payload.

Each decoder is best-effort and self-scoring. A run of zero-width characters
may be a bit stream or may be orthography; the decoder returns a confidence
based on whether the result looks like data, and never asserts more than that.
"""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field

PRINTABLE = set(string.printable) - set("\x0b\x0c")


@dataclass
class Payload:
    scheme: str
    raw_codepoints: int
    decoded: str
    confidence: str          # confirmed | probable | speculative
    offset: int
    note: str = ""
    identifiers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scheme": self.scheme,
            "carrier_codepoints": self.raw_codepoints,
            "decoded": self.decoded,
            "confidence": self.confidence,
            "offset": self.offset,
            "identifiers": self.identifiers,
            "note": self.note,
        }


# Vendor and provenance tokens worth surfacing if a payload contains one. This
# is attribution from *decoded content*, not from writing style.
_IDENTIFIER_RE = re.compile(
    r"(claude|anthropic|openai|chatgpt|gpt-?[0-9]|gemini|copilot|codex|llama|"
    r"mistral|synthid|c2pa|aigc|gen(?:erated)?[-_=:]|model[-_=:]|"
    r"\bv?\d+\.\d+(?:\.\d+)?\b|\b20\d\d-\d\d-\d\d\b|[0-9a-f]{8,})",
    re.I,
)


def _printable_ratio(s: str) -> float:
    return sum(1 for c in s if c in PRINTABLE) / len(s) if s else 0.0


def _score(text: str) -> str:
    """How much to trust a decode. Printable ASCII is the discriminator."""
    if not text:
        return "speculative"
    ratio = _printable_ratio(text)
    if ratio == 1.0 and len(text) >= 4:
        return "confirmed"
    if ratio >= 0.8:
        return "probable"
    return "speculative"


def decode_tag_block(text: str) -> list[Payload]:
    """U+E0000-U+E007F mirrors ASCII one-to-one."""
    out = []
    for m in re.finditer(r"[\U000E0000-\U000E007F]{2,}", text):
        run = m.group(0)
        decoded = "".join(chr(ord(c) - 0xE0000) for c in run)
        decoded = decoded.replace("\x7f", "")  # CANCEL TAG terminator
        if not decoded:
            continue
        out.append(Payload(
            scheme="unicode tag block",
            raw_codepoints=len(run),
            decoded=decoded,
            confidence=_score(decoded),
            offset=m.start(),
            note="each tag character is one ASCII character, invisibly",
            identifiers=sorted({g.group(0) for g in _IDENTIFIER_RE.finditer(decoded)}),
        ))
    return out


def decode_variation_selectors(text: str) -> list[Payload]:
    """256 selectors give one arbitrary byte each."""
    out = []
    for m in re.finditer(r"[︀-️\U000E0100-\U000E01EF]{3,}", text):
        run = m.group(0)
        vals = []
        for c in run:
            cp = ord(c)
            vals.append(cp - 0xFE00 if cp <= 0xFE0F else cp - 0xE0100 + 16)
        decoded = bytes(v & 0xFF for v in vals).decode("latin-1")
        out.append(Payload(
            scheme="variation selector bytes",
            raw_codepoints=len(run),
            decoded=decoded,
            confidence=_score(decoded),
            offset=m.start(),
            note="one byte per selector; a run on one base is payload",
            identifiers=sorted({g.group(0) for g in _IDENTIFIER_RE.finditer(decoded)}),
        ))
    return out


def decode_zero_width(text: str) -> list[Payload]:
    """Zero-width runs as a bit stream, under both common conventions."""
    out = []
    for m in re.finditer(r"[​‌‍⁠﻿]{8,}", text):
        run = m.group(0)
        for zero, one, label in (("​", "‌", "ZWSP/ZWNJ"),
                                 ("‌", "‍", "ZWNJ/ZWJ")):
            if not set(run) <= {zero, one}:
                continue
            bits = [1 if c == one else 0 for c in run]
            data = bytearray()
            for i in range(0, len(bits) - 7, 8):
                v = 0
                for b in bits[i:i + 8]:
                    v = (v << 1) | b
                data.append(v)
            if not data:
                continue
            decoded = data.decode("latin-1")
            out.append(Payload(
                scheme=f"zero-width binary ({label})",
                raw_codepoints=len(run),
                decoded=decoded,
                confidence=_score(decoded),
                offset=m.start(),
                note=f"{len(bits)} bits under the {label} convention",
                identifiers=sorted({g.group(0) for g in _IDENTIFIER_RE.finditer(decoded)}),
            ))
            break
    return out


def decode_private_use(text: str) -> list[Payload]:
    out = []
    for m in re.finditer(r"[-]{2,}", text):
        run = m.group(0)
        decoded = "".join(
            chr(ord(c) - 0xE000) if ord(c) - 0xE000 < 0x80 else "�" for c in run
        )
        out.append(Payload(
            scheme="private-use area",
            raw_codepoints=len(run),
            decoded=decoded,
            confidence=_score(decoded),
            offset=m.start(),
            note="offset from U+E000; the mapping is a guess, the range has "
                 "no assigned meaning",
            identifiers=sorted({g.group(0) for g in _IDENTIFIER_RE.finditer(decoded)}),
        ))
    return out


DECODERS = (
    decode_tag_block,
    decode_variation_selectors,
    decode_zero_width,
    decode_private_use,
)


def extract(text: str) -> list[Payload]:
    """Every payload any decoder can recover, best first."""
    found: list[Payload] = []
    for fn in DECODERS:
        found.extend(fn(text))
    rank = {"confirmed": 0, "probable": 1, "speculative": 2}
    found.sort(key=lambda p: (rank[p.confidence], -p.raw_codepoints))
    return found


def carrier_signature(text: str) -> dict[str, int]:
    """Which carrier classes a producer reached for, and how often.

    Weak attribution on its own -- but a tool that only ever uses tag blocks
    behind flag emoji looks different from one that uses zero-width runs, and
    the pattern is stable across documents in a way prose style is not.
    """
    sig: dict[str, int] = {}
    for label, pattern in (
        ("tag_block", r"[\U000E0000-\U000E007F]"),
        ("variation_selector", r"[︀-️\U000E0100-\U000E01EF]"),
        ("zero_width", r"[​‌‍⁠﻿]"),
        ("private_use", r"[-\U000F0000-\U000FFFFD\U00100000-\U0010FFFD]"),
        ("bidi_override", r"[‭‮]"),
        ("space_homoglyph", r"[  -   　]"),
    ):
        n = len(re.findall(pattern, text))
        if n:
            sig[label] = n
    return sig
