"""Detection of homoglyphs is decoupled from the policy that rewrites them.

The defect: confusable handling sat behind `aggressive_homoglyphs`, a *removal*
flag. With it off — the default, because rewriting homoglyphs has a real
false-positive cost on multilingual source — a Cyrillic character in a hostname
was not merely left alone, it was never reported.

The naive fix, reporting every confusable, is worse: it would flag every
Cyrillic letter in Russian prose. The discriminator is script mixing within a
token, after Unicode TR39.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "wm_hook" / "core"))

from text_unicode import (  # noqa: E402
    _mixed_script_confusable_indices,
    clean_text,
    inspect_text,
)

CYR_A = "а"   # CYRILLIC SMALL LETTER A, confusable with 'a'
CYR_O = "о"   # CYRILLIC SMALL LETTER O
FW_A = "Ａ"    # FULLWIDTH LATIN CAPITAL LETTER A


def reports_confusable(text: str) -> bool:
    return any(h.kind == "confusable" for h in inspect_text(text).hits)


class TestMixedScriptIsReported:
    def test_cyrillic_in_a_hostname(self) -> None:
        assert reports_confusable(f'HOST = "p{CYR_A}ypal.com"')

    def test_fullwidth_among_ascii(self) -> None:
        assert reports_confusable(f"use {FW_A}BCmodule")

    def test_two_confusables_in_one_token(self) -> None:
        report = inspect_text(f"g{CYR_O}{CYR_O}gle")
        total = sum(h.count for h in report.hits if h.kind == "confusable")
        assert total == 2

    def test_the_position_is_reported(self) -> None:
        report = inspect_text(f"p{CYR_A}ypal")
        hit = next(h for h in report.hits if h.kind == "confusable")
        assert hit.samples == [1]


class TestSingleScriptIsNotReported:
    """The false-positive floor. Getting this wrong makes the tool unusable."""

    @pytest.mark.parametrize(("text", "what"), [
        ("привет мир", "Russian prose"),
        ("абвгд", "Cyrillic alphabet"),
        ("hello world", "plain ASCII"),
        ("αβγ", "Greek prose"),
    ])
    def test_not_reported(self, text: str, what: str) -> None:
        assert not reports_confusable(text), what

    def test_scripts_in_separate_tokens_are_fine(self) -> None:
        """Mixing scripts in a document is normal; mixing them in a word is not."""
        assert not reports_confusable("привет world")

    def test_a_whole_cyrillic_document_stays_quiet(self) -> None:
        text = " ".join(["коммит"] * 200)
        assert not reports_confusable(text)


class TestDecoupling:
    """Detection reports; policy decides whether to rewrite."""

    def test_reported_but_not_rewritten_by_default(self) -> None:
        text = f"p{CYR_A}ypal.com"
        assert reports_confusable(text)
        assert clean_text(text)[0] == text, "default must not rewrite"

    def test_rewritten_when_the_policy_asks(self) -> None:
        text = f"p{CYR_A}ypal.com"
        out, _ = clean_text(text, aggressive_homoglyphs=True)
        assert out == "paypal.com"

    def test_cleaning_is_unaffected_by_detection_context(self) -> None:
        """Mixed-script context must not leak into removal behaviour."""
        for text in (f"p{CYR_A}ypal", "привет"):
            assert clean_text(text)[0] == text


class TestIndexHelper:
    def test_flags_only_the_confusable_characters(self) -> None:
        text = f"p{CYR_A}ypal"
        assert _mixed_script_confusable_indices(text) == {1}

    def test_empty_for_single_script(self) -> None:
        assert _mixed_script_confusable_indices("привет") == set()

    def test_token_boundaries_are_identifier_like(self) -> None:
        """A dot keeps a hostname together, whitespace does not."""
        assert _mixed_script_confusable_indices(f"p{CYR_A}ypal.com")
        assert not _mixed_script_confusable_indices(f"{CYR_A} paypal")


class TestKnownTableGap:
    @pytest.mark.xfail(
        reason="LATIN_CONFUSABLES covers Cyrillic and fullwidth only. Greek "
               "omicron U+03BF is a classic homoglyph for 'o' and is absent "
               "from the table, so mixed-script detection has nothing to "
               "match. Widening the table is a separate change with its own "
               "false-positive profile.",
    )
    def test_greek_omicron_in_a_latin_word(self) -> None:
        assert reports_confusable("gοοgle")
