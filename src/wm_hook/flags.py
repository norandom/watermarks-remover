"""Bounded validation of emoji tag sequences.

The vendored cleaner exempts "complete subdivision-flag sequences" from tag
stripping, so that the Scotland flag survives. Its check is too permissive in
two independent ways, and together they turn the exemption into the widest
covert channel the tool leaves open -- measured at 1535 bits per kilobyte of
host text, 64% of all residual capacity, with 100% survival.

The vendored predicate accepts a run as valid when::

    0xE0020 <= codepoint <= 0xE007E     # the whole printable tag range
    and length >= 1                     # no upper bound at all

So prefixing any payload with U+1F3F4 and terminating it with U+E007F hands an
attacker 95 symbols per position and unlimited length. The adversary sets the
data rate, not the host text.

Unicode TR51 defines the sequence as::

    emoji_tag_sequence := tag_base tag_spec tag_term
    tag_base           := U+1F3F4
    tag_spec           := [U+E0030-U+E0039 U+E0061-U+E007A]+
    tag_term           := U+E007F

and the interchange-recommended set encodes ISO 3166-2 subdivision codes, which
are two to six characters drawn from digits and lowercase letters. Restricting
to that alphabet and length is both correct per the standard and sufficient to
close the channel: 36 symbols over at most 6 positions caps a sequence at
about 31 bits total, and every one of those bits has to spell a plausible
subdivision code.

This module is a slice of ``watermark-removal`` task 2.4(b). It is deliberately
standalone -- pure sequence validation, no dependency on segmentation or the
classifier -- so that the highest-capacity hole can be closed without waiting
for the rest of that task.
"""

from __future__ import annotations

__all__ = [
    "TAG_BASE",
    "TAG_TERM",
    "MIN_TAG_SPEC",
    "MAX_TAG_SPEC",
    "is_tag_spec_codepoint",
    "valid_flag_tag_indices",
]

#: U+1F3F4 WAVING BLACK FLAG.
TAG_BASE = 0x1F3F4

#: U+E007F CANCEL TAG.
TAG_TERM = 0xE007F

#: ISO 3166-2 subdivision codes are 2 to 6 characters. TR51's grammar says
#: "one or more"; the interchange set never exceeds six, and permitting more
#: reopens the channel for no benefit.
MIN_TAG_SPEC = 2
MAX_TAG_SPEC = 6

# Tag characters mirroring '0'-'9' and 'a'-'z'. Everything else in the tag
# block -- uppercase, punctuation, space -- has no role in a subdivision code
# and is contraband wherever it appears.
_TAG_DIGIT_LO, _TAG_DIGIT_HI = 0xE0030, 0xE0039
_TAG_LOWER_LO, _TAG_LOWER_HI = 0xE0061, 0xE007A


def is_tag_spec_codepoint(cp: int) -> bool:
    """True for a tag character that may appear inside a subdivision code."""
    return (_TAG_DIGIT_LO <= cp <= _TAG_DIGIT_HI
            or _TAG_LOWER_LO <= cp <= _TAG_LOWER_HI)


def valid_flag_tag_indices(text: str) -> set[int]:
    """Indices belonging to a well-formed emoji tag sequence.

    Returns the positions of the tag-spec characters and the terminator, so a
    caller can preserve them while stripping every other tag character. The
    base itself is a normal emoji and is never at risk.

    A run is well-formed only when every character is a tag digit or lowercase
    tag letter, the run is between ``MIN_TAG_SPEC`` and ``MAX_TAG_SPEC``
    characters, and it is closed by ``TAG_TERM``. Anything else -- an overlong
    run, an uppercase tag character, an unterminated run -- is payload, and
    none of its indices are returned.
    """
    valid: set[int] = set()
    i = 0
    n = len(text)
    while i < n:
        if ord(text[i]) != TAG_BASE:
            i += 1
            continue

        # Consume only characters legal inside a subdivision code. Stopping at
        # the first illegal one is what prevents a payload from being absorbed
        # into a run that happens to end with a terminator.
        j = i + 1
        while j < n and is_tag_spec_codepoint(ord(text[j])):
            j += 1

        spec_len = j - (i + 1)
        terminated = j < n and ord(text[j]) == TAG_TERM
        if terminated and MIN_TAG_SPEC <= spec_len <= MAX_TAG_SPEC:
            valid.update(range(i + 1, j + 1))
            i = j + 1
        else:
            # Advance past the base only. A malformed sequence must not
            # swallow a well-formed one that follows it.
            i += 1
    return valid
