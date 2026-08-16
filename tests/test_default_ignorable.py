"""The strip rule derives from Default_Ignorable_Code_Point, not category Cf.

Category Cf was standing in for "renders as nothing" and is strictly narrower.
Three carriers lived in the gap, and one of them -- the Hangul fillers --
accounted for 84% of residual covert-channel capacity after every other hole
had been closed.

Every carrier below is a ``\\uXXXX`` escape. A literal one would be rewritten
by this repository's own hook and the constant would silently change.
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "wm_hook" / "core"))

from text_unicode import (  # noqa: E402
    _DEFAULT_IGNORABLE_RANGES,
    _is_default_ignorable,
    clean_text,
)


def strip_probe(ch: str) -> bool:
    """True when *ch* is removed from an ordinary Latin context."""
    out, _ = clean_text(f"ab{ch}cd")
    return ch not in out


class TestTheGapThatWasClosed:
    @pytest.mark.parametrize(("cp", "why"), [
        (0x3164, "HANGUL FILLER, category Lo -- 728 bits/KB of channel"),
        (0xFFA0, "HALFWIDTH HANGUL FILLER, category Lo"),
        (0x180F, "MONGOLIAN FVS FOUR, category Mn, added in Unicode 14"),
    ])
    def test_invisible_non_cf_characters_are_stripped(self, cp: int, why: str) -> None:
        assert unicodedata.category(chr(cp)) != "Cf", "precondition: not a format char"
        assert strip_probe(chr(cp)), why

    def test_the_hangul_fillers_are_letters(self) -> None:
        """Why the category rule could never have caught them."""
        assert unicodedata.category("ㅤ") == "Lo"
        assert unicodedata.category("ﾠ") == "Lo"


class TestLegitimateContextSurvives:
    """Closing the gap must not break the scripts these characters belong to."""

    @pytest.mark.parametrize(("text", "what"), [
        ("ᄀᅠ", "jungseong filler holding a slot after a choseong jamo"),
        ("ᠠ᠋", "Mongolian free variation selector after a Mongolian letter"),
        ("ក឴", "Khmer inherent vowel after a Khmer letter"),
        ("⁦אב⁩", "bidi isolate around Hebrew"),
        ("क्‍ष", "Devanagari half-form joiner"),
    ])
    def test_preserved(self, text: str, what: str) -> None:
        out, _ = clean_text(text)
        assert out == text, what

    @pytest.mark.xfail(
        reason="Requirement 3.4 is not implemented yet: U+200B is the word "
               "separator in Thai, Lao, Khmer and Myanmar and is currently "
               "stripped there. Pre-existing, not caused by the "
               "default-ignorable change. Task 2.4(c) fixes it, and "
               "xfail_strict will fail this suite when it does.",
    )
    def test_thai_word_separator_is_preserved(self) -> None:
        text = "ก​ข"
        assert clean_text(text)[0] == text

    def test_a_filler_after_a_jamo_is_kept_but_a_free_one_is_not(self) -> None:
        """The discriminator is position, not identity."""
        assert clean_text("ᄀᅠ")[0] == "ᄀᅠ"
        assert "ᅠ" not in clean_text("abᅠcd")[0]


class TestThePropertyItself:
    def test_ranges_are_ascending_and_well_formed(self) -> None:
        """The lookup short-circuits on ascending order; enforce it."""
        prev_hi = -1
        for lo, hi in _DEFAULT_IGNORABLE_RANGES:
            assert lo <= hi
            assert lo > prev_hi, "ranges must ascend and not overlap"
            prev_hi = hi

    @pytest.mark.parametrize("cp", [0x00AD, 0x200B, 0xFEFF, 0x3164, 0xFFA0,
                                    0x180F, 0xE0001, 0x1D173])
    def test_known_members(self, cp: int) -> None:
        assert _is_default_ignorable(cp)

    @pytest.mark.parametrize("cp", [0x0041, 0x0020, 0x2800, 0x00A0, 0x3000,
                                    0xE000, 0x1F600])
    def test_known_non_members(self, cp: int) -> None:
        assert not _is_default_ignorable(cp)

    def test_braille_blank_is_not_default_ignorable(self) -> None:
        """An empty braille cell is a real character, not an invisible one.

        It stays out of scope deliberately: stripping it would corrupt braille
        text, and it is only 15% of what remains.
        """
        assert not _is_default_ignorable(0x2800)
        assert unicodedata.category("⠀") == "So"


class TestForwardCompatibility:
    def test_every_assigned_ignorable_is_handled(self) -> None:
        """No assigned default-ignorable character escapes, except by policy.

        The six exceptions are bidi marks and isolates, preserved under
        Requirement 3.7 because they are legitimate in mixed-direction prose,
        and governed by the strip_bidi flag rather than by this rule.
        """
        policy_preserved = {0x061C, 0x200E, 0x200F, 0x2066, 0x2067, 0x2068, 0x2069}
        escaped = []
        for lo, hi in _DEFAULT_IGNORABLE_RANGES:
            for cp in range(lo, hi + 1):
                if unicodedata.category(chr(cp)) == "Cn" or cp in policy_preserved:
                    continue
                if not strip_probe(chr(cp)):
                    escaped.append(f"U+{cp:04X}")
        assert not escaped, f"unhandled default-ignorable characters: {escaped}"

    def test_the_policy_exceptions_strip_when_asked(self) -> None:
        for cp in (0x200E, 0x2066):
            out, _ = clean_text(f"ab{chr(cp)}cd", strip_bidi=True)
            assert chr(cp) not in out
