"""Tests for bounded emoji tag sequence validation (task 2.4(b) slice).

Every carrier is written as a ``\\uXXXX`` escape. A literal one here would be
rewritten by this repository's own hook and the constant would silently change.
"""

from __future__ import annotations

import pytest

from wm_hook.flags import (
    MAX_TAG_SPEC,
    MIN_TAG_SPEC,
    TAG_BASE,
    TAG_TERM,
    is_tag_spec_codepoint,
    valid_flag_tag_indices,
)

BASE = chr(TAG_BASE)
TERM = chr(TAG_TERM)


def tag(s: str) -> str:
    """Spell *s* in tag characters."""
    return "".join(chr(0xE0000 + ord(c)) for c in s)


def seq(code: str) -> str:
    return BASE + tag(code) + TERM


class TestRealFlags:
    """The three subdivision flags in interchange use must survive."""

    @pytest.mark.parametrize("code", ["gbeng", "gbsct", "gbwls"])
    def test_recommended_subdivision_flags_are_valid(self, code: str) -> None:
        text = f"Score: {seq(code)} wins"
        idx = valid_flag_tag_indices(text)
        # every tag character plus the terminator
        assert len(idx) == len(code) + 1

    def test_a_flag_survives_surrounded_by_prose(self) -> None:
        text = f"before {seq('gbsct')} after"
        assert valid_flag_tag_indices(text)

    def test_two_flags_in_one_document(self) -> None:
        text = f"{seq('gbsct')} and {seq('gbwls')}"
        assert len(valid_flag_tag_indices(text)) == 12  # 5+1 twice


class TestPayloadIsRejected:
    """The channel this closes: 1535 bits/KB, 64% of residual capacity."""

    def test_overlong_payload_is_not_exempt(self) -> None:
        payload = "secretpayloaddata"
        assert len(payload) > MAX_TAG_SPEC
        assert valid_flag_tag_indices(BASE + tag(payload) + TERM) == set()

    def test_payload_at_the_length_boundary(self) -> None:
        assert valid_flag_tag_indices(seq("a" * MAX_TAG_SPEC))
        assert valid_flag_tag_indices(seq("a" * (MAX_TAG_SPEC + 1))) == set()

    def test_single_character_is_too_short(self) -> None:
        assert len("a") < MIN_TAG_SPEC
        assert valid_flag_tag_indices(seq("a")) == set()

    def test_uppercase_tag_characters_are_contraband(self) -> None:
        """The vendored check accepted the whole printable tag range."""
        assert valid_flag_tag_indices(seq("GBSCT")) == set()

    def test_punctuation_tag_characters_are_contraband(self) -> None:
        assert valid_flag_tag_indices(BASE + tag("a=b") + TERM) == set()

    def test_unterminated_run_is_not_exempt(self) -> None:
        assert valid_flag_tag_indices(BASE + tag("gbsct")) == set()

    def test_terminator_without_a_base_is_not_exempt(self) -> None:
        assert valid_flag_tag_indices(tag("gbsct") + TERM) == set()

    def test_payload_smuggled_after_a_valid_flag(self) -> None:
        """A conforming flag must not launder a payload that follows it."""
        text = seq("gbsct") + tag("hiddenpayload")
        idx = valid_flag_tag_indices(text)
        assert len(idx) == 6  # only the real flag's characters
        smuggled = {i for i, c in enumerate(text)
                    if 0xE0020 <= ord(c) <= 0xE007E} - idx
        assert smuggled, "the trailing payload must be left unprotected"

    def test_a_malformed_sequence_does_not_swallow_a_valid_one(self) -> None:
        text = BASE + tag("toolongforacode") + seq("gbsct")
        assert len(valid_flag_tag_indices(text)) == 6


class TestCodepointClassification:
    def test_digits_and_lowercase_are_spec_characters(self) -> None:
        assert is_tag_spec_codepoint(0xE0030)  # '0'
        assert is_tag_spec_codepoint(0xE0039)  # '9'
        assert is_tag_spec_codepoint(0xE0061)  # 'a'
        assert is_tag_spec_codepoint(0xE007A)  # 'z'

    @pytest.mark.parametrize("cp", [
        0xE0020,  # space
        0xE002F,  # '/'
        0xE003A,  # ':'
        0xE0041,  # 'A'
        0xE005A,  # 'Z'
        0xE007B,  # '{'
        0xE007F,  # the terminator itself
    ])
    def test_everything_else_is_rejected(self, cp: int) -> None:
        assert not is_tag_spec_codepoint(cp)


def _vendored_predicate():
    """The upstream check, for divergence pinning.

    Importing ``wm_hook._tables`` first is not incidental: it is the gateway
    that puts ``_vendor`` on ``sys.path``, and without it this import succeeds
    only when some earlier test happened to establish the path. Depending on
    collection order is how a suite grows tests that pass together and fail
    alone.

    Production code may not import vendored decision functions. Tests may, and
    only to measure divergence.
    """
    import wm_hook._tables  # noqa: F401  (imported for its sys.path effect)
    from text_unicode import _valid_flag_tag_indices

    return _valid_flag_tag_indices


class TestAgainstTheVendoredImplementation:
    """Pin the divergence, so an upstream refresh cannot silently undo it."""

    def test_vendored_accepts_what_we_reject(self) -> None:
        vendored = _vendored_predicate()
        payload = BASE + tag("secretpayloaddata") + TERM
        assert vendored(payload), "precondition: upstream exempts the payload"
        assert valid_flag_tag_indices(payload) == set()

    def test_both_accept_a_real_flag(self) -> None:
        vendored = _vendored_predicate()
        real = seq("gbsct")
        assert vendored(real) == valid_flag_tag_indices(real)
