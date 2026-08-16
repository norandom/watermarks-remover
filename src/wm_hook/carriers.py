"""Which invisible codepoints are present, and which of them have an excuse.

This is the detection half of the project, and it is deliberately separate from
the cleaning half in ``core/text_unicode.py``. The two answer different
questions and are allowed to disagree:

    the cleaner asks    is this codepoint safe to delete?
    the detector asks   is this codepoint doing legitimate work?

A cleaner may strip something a detector calls legitimate (a no-break space is
typography, but removing it changes nothing that matters), and a detector may
flag something a cleaner leaves alone. Collapsing them into one table would
force one of the two questions to be answered wrongly.

The central discipline here is that presence is not evidence. Almost every
invisible codepoint in real source trees is an emoji presentation selector, a
script joiner doing orthographic work, or a byte-order mark. A detector that
counts codepoints reports a hit rate two orders of magnitude above the truth.
``explain`` is what separates the two, and everything downstream depends on it.
"""

from __future__ import annotations

import re
import unicodedata

# An emoji written half-escaped in source: the base spelled as an ASCII escape,
# the selector left as a real codepoint. Found in a real test file, where
# "\\U0001f441" + U+FE0F made the selector look orphaned because its base is
# not a codepoint at all. The anchor matters -- it excuses exactly one selector,
# since the character before a second one is the first, not a hex digit. That
# bound is the same lesson the flag-tag exemption taught: an exemption without
# a length limit is a channel.
_ESCAPED_BASE_RE = re.compile(
    r"\\(?:U[0-9a-fA-F]{8}|u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|N\{[^}]{1,64})\}?$"
)

ZERO_WIDTH = frozenset({0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF})
BIDI = frozenset({0x200E, 0x200F, 0x061C, 0x202A, 0x202B, 0x202C, 0x202D,
                  0x202E, 0x2066, 0x2067, 0x2068, 0x2069})
SPACE_HOMOGLYPHS = frozenset({0x00A0, 0x1680, 0x202F, 0x205F, 0x3000}) | frozenset(
    range(0x2000, 0x200B)
)

# Scripts in which a zero-width joiner or non-joiner is orthography, not payload.
JOINING_RANGES = (
    (0x0600, 0x08FF), (0x0900, 0x0DFF), (0x0F00, 0x109F),
    (0x1780, 0x17FF), (0x1800, 0x18AF),
)
# Scripts that use U+200B as a word or line-break separator.
ZWSP_SEPARATOR_RANGES = ((0x0E00, 0x0E7F), (0x0E80, 0x0EFF),
                         (0x1780, 0x17FF), (0x1000, 0x109F))

# Emoji bases outside the Symbol categories. These are exactly the ones the
# cleaner's own base table omits, and the survey prototype inherited the same
# gap -- it reported three of them as watermark candidates.
_EXTRA_EMOJI_BASES = frozenset({
    0x2139,  # information source
    0x203C,  # double exclamation mark
    0x2049,  # exclamation question mark
    0x2934, 0x2935,  # right arrow curving up / down
    0x00A9, 0x00AE, 0x2122,  # copyright, registered, trade mark
    0x3030, 0x303D, 0x3297, 0x3299,
})

_CHAINABLE = frozenset({"variation_selector", "zero_width", "tag_chars"})


def carrier_class(cp: int) -> str | None:
    """The carrier family a codepoint belongs to, or None if it is visible."""
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


def in_ranges(cp: int, ranges) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


def is_symbolish(ch: str) -> bool:
    cp = ord(ch)
    return (
        unicodedata.category(ch) in ("So", "Sk", "Sm")
        or 0x1F000 <= cp <= 0x1FAFF
        or cp in _EXTRA_EMOJI_BASES
    )


def preceding_base(text: str, i: int) -> str:
    """The nearest preceding character that is not itself a carrier.

    A backward look that stops at ``text[i-1]`` fails on any chained sequence:
    in the emoji U+2764 U+FE0F U+200D U+1F525 the character before the joiner
    is a variation selector, not the heart. Skipping carriers is what lets the
    joiner be recognised as emoji glue rather than a payload.
    """
    j = i - 1
    while j >= 0 and carrier_class(ord(text[j])) in _CHAINABLE:
        j -= 1
    return text[j] if j >= 0 else ""


def following_base(text: str, i: int) -> str:
    j = i + 1
    while j < len(text) and carrier_class(ord(text[j])) in _CHAINABLE:
        j += 1
    return text[j] if j < len(text) else ""


def explain(text: str, i: int) -> str | None:
    """Why the carrier at ``text[i]`` is legitimate, or None if unexplained.

    Only the unexplained residual is evidence of anything.
    """
    cp = ord(text[i])
    prev = preceding_base(text, i)
    nxt = following_base(text, i)
    kind = carrier_class(cp)

    if kind == "variation_selector":
        if prev and is_symbolish(prev):
            return "emoji or symbol presentation selector"
        if prev and (0x3400 <= ord(prev) <= 0x9FFF or 0xF900 <= ord(prev) <= 0xFAFF):
            return "ideographic variation sequence"
        if _ESCAPED_BASE_RE.search(text[max(0, i - 72):i]):
            return "selector after an escaped codepoint in source"
    if cp in (0x200C, 0x200D):
        if prev and nxt and in_ranges(ord(prev), JOINING_RANGES) and in_ranges(ord(nxt), JOINING_RANGES):
            return "script joiner between same-script letters"
        if prev and in_ranges(ord(prev), JOINING_RANGES):
            return "script joiner at a word boundary (word-final virama etc.)"
        if cp == 0x200D and prev and nxt and is_symbolish(prev) and is_symbolish(nxt):
            return "emoji zero-width joiner sequence"
    if cp == 0x200B and prev and in_ranges(ord(prev), ZWSP_SEPARATOR_RANGES):
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


def scan(text: str) -> tuple[list[tuple[int, str, str | None]], int]:
    """Every carrier in ``text`` as (offset, class, reason-or-None), plus a count.

    One pass, so callers do not each re-walk the string.
    """
    found = []
    explained = 0
    for i, ch in enumerate(text):
        kind = carrier_class(ord(ch))
        if not kind:
            continue
        why = explain(text, i)
        if why:
            explained += 1
        found.append((i, kind, why))
    return found, explained
