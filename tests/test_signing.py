"""The signing prototype's security properties, as tests rather than claims.

Skipped where `cryptography` is absent, since research code must not add a
dependency to the stdlib-only hook's test run.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("cryptography", reason="research signing needs cryptography")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "research" / "signing"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "wm_hook" / "core"))

from sign import PAYLOAD_LEN, canonical, keygen, sign, verify  # noqa: E402

TEXT = "The scheduler retries failed jobs three times before giving up.\n"


@pytest.fixture(scope="module")
def keys():
    return keygen()


def test_a_signature_verifies(keys):
    priv, pub = keys
    ok, why = verify(sign(TEXT, priv, pub), pub)
    assert ok, why


def test_signing_changes_no_visible_character(keys):
    priv, pub = keys
    signed = sign(TEXT, priv, pub)
    assert canonical(signed) == canonical(TEXT)


def test_it_costs_exactly_the_payload_in_codepoints(keys):
    priv, pub = keys
    assert len(sign(TEXT, priv, pub)) - len(TEXT) == PAYLOAD_LEN


# ---------------------------------------------------------------------------
# The properties that make it a signature rather than a sticker.
# ---------------------------------------------------------------------------

def test_a_signature_cannot_be_transplanted_onto_other_text(keys):
    """The attack that kills every fixed-string design.

    Lift the invisible bytes off my paragraph, paste them under yours. If that
    verified, the mark would prove nothing about who wrote what.
    """
    priv, pub = keys
    signed = sign(TEXT, priv, pub)
    stolen = "".join(c for c in signed if ord(c) >= 0xFE00)
    forged = "Somebody else wrote this entirely.\n" + stolen
    ok, why = verify(forged, pub)
    assert not ok
    assert "does not match this text" in why


def test_editing_one_word_invalidates_it(keys):
    priv, pub = keys
    signed = sign(TEXT, priv, pub)
    ok, _ = verify(signed.replace("three", "five"), pub)
    assert not ok


def test_another_key_does_not_verify(keys):
    priv, pub = keys
    _, other_pub = keygen()
    ok, why = verify(sign(TEXT, priv, pub), other_pub)
    assert not ok
    assert "different key" in why


def test_unsigned_text_reports_absence_not_failure(keys):
    _, pub = keys
    ok, why = verify(TEXT, pub)
    assert not ok
    assert why == "no signature found"


# ---------------------------------------------------------------------------
# Canonicalisation: what must NOT break a signature.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mangle,label", [
    (lambda t: t.replace("\n", "\r\n"), "CRLF"),
    (lambda t: t.replace("\n", "  \n"), "trailing whitespace"),
    (lambda t: t + "\n\n", "extra blank lines at the end"),
])
def test_cosmetic_changes_do_not_break_it(keys, mangle, label):
    priv, pub = keys
    ok, why = verify(mangle(sign(TEXT, priv, pub)), pub)
    assert ok, f"{label}: {why}"


def test_the_cleaner_destroys_it_and_that_is_the_documented_limit(keys):
    """No signature proves nothing, because removing one is trivial."""
    from text_unicode import clean_text

    priv, pub = keys
    cleaned, _ = clean_text(sign(TEXT, priv, pub))
    ok, why = verify(cleaned, pub)
    assert not ok
    assert why == "no signature found"


def test_a_signature_is_invisible_but_not_hidden(keys):
    """It is meant to be unseen by a reader, not concealed from a scanner."""
    from wm_hook.verdict import classify

    priv, pub = keys
    assert classify(sign(TEXT, priv, pub)).carrier_present
