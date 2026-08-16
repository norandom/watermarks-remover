"""The --sign feature, and the attacks it has to survive.

The security properties are the tests. A label that can be copied onto someone
else's text is a sticker, and the whole point of the keyed mode is that it
cannot be.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "wm_hook" / "core"))

from wm_hook.signing import (  # noqa: E402
    SigningError,
    canonical,
    find,
    keygen,
    sign,
    verify,
    write_key,
)

TEXT = "# Notes\n\nThe scheduler retries failed jobs three times.\n"
LABEL = "Marius Ciepluch"


@pytest.fixture
def key():
    return keygen()


# ---------------------------------------------------------------------------
# It works at all
# ---------------------------------------------------------------------------

def test_a_keyed_mark_verifies(key):
    r = verify(sign(TEXT, LABEL, key), key)
    assert r.valid is True
    assert r.label == LABEL
    assert r.proves_authorship


def test_signing_changes_no_visible_text(key):
    assert canonical(sign(TEXT, LABEL, key)) == canonical(TEXT)


def test_the_label_is_readable_by_the_ordinary_detector(key):
    # A third party running --detect should see the name without knowing this
    # feature exists. That is the attribution story working end to end.
    from wm_hook.verdict import classify

    v = classify(sign(TEXT, LABEL, key))
    assert v.payloads
    assert LABEL in v.payloads[0]["decoded"]


# ---------------------------------------------------------------------------
# The attacks
# ---------------------------------------------------------------------------

def test_a_mark_cannot_be_transplanted_onto_other_text(key):
    """Lift the invisible bytes off my paragraph, paste them under yours."""
    signed = sign(TEXT, LABEL, key)
    stolen = "".join(c for c in signed if ord(c) >= 0xE0000 or 0xFE00 <= ord(c) <= 0xFE0F)
    r = verify("Somebody else wrote this.\n" + stolen, key)
    assert r.valid is False
    assert "copied from other text" in r.detail


def test_editing_the_text_invalidates_the_mark(key):
    r = verify(sign(TEXT, LABEL, key).replace("three", "five"), key)
    assert r.valid is False


def test_a_different_key_does_not_verify(key):
    r = verify(sign(TEXT, LABEL, key), keygen())
    assert r.valid is False


def test_an_unkeyed_label_refuses_to_claim_authorship():
    r = verify(sign(TEXT, LABEL), None)
    assert r.label == LABEL
    assert r.valid is None
    assert not r.proves_authorship
    assert "not proof of authorship" in r.detail


def test_a_keyed_mark_without_the_key_is_not_called_valid(key):
    r = verify(sign(TEXT, LABEL, key), None)
    assert r.valid is None
    assert not r.proves_authorship


def test_unsigned_text_reports_absence(key):
    assert verify(TEXT, key).label is None


# ---------------------------------------------------------------------------
# Cosmetic changes must NOT break it
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mangle,label", [
    (lambda t: t.replace("\n", "\r\n"), "CRLF"),
    (lambda t: t.replace("\n", "  \n"), "trailing whitespace"),
    (lambda t: t + "\n\n", "extra blank lines"),
])
def test_cosmetic_changes_survive(key, mangle, label):
    assert verify(mangle(sign(TEXT, LABEL, key)), key).valid is True, label


def test_the_cleaner_removes_it_which_is_the_documented_limit(key):
    from text_unicode import clean_text

    cleaned, _ = clean_text(sign(TEXT, LABEL, key))
    assert verify(cleaned, key).label is None


# ---------------------------------------------------------------------------
# Input handling
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad,why", [
    ("", "empty"),
    ("   ", "whitespace only"),
    ("x" * 200, "too long"),
    ("Mariüs", "non-ASCII cannot go in the tag block"),
])
def test_bad_labels_are_refused(bad, why):
    with pytest.raises(SigningError):
        sign(TEXT, bad, None)


def test_double_signing_is_refused(key):
    with pytest.raises(SigningError, match="already signed"):
        sign(sign(TEXT, LABEL, key), "Someone Else", key)


def test_find_returns_the_label_and_mac(key):
    label, mac = find(sign(TEXT, LABEL, key))
    assert label == LABEL
    assert mac is not None and len(mac) == 32


# ---------------------------------------------------------------------------
# Key handling. Losing a key silently is the worst outcome here.
# ---------------------------------------------------------------------------

def test_keygen_refuses_to_overwrite_an_existing_key(tmp_path):
    p = tmp_path / "wm.key"
    write_key(p)
    original = p.read_bytes()
    with pytest.raises(SigningError, match="Refusing to overwrite"):
        write_key(p)
    assert p.read_bytes() == original


def test_a_written_key_is_usable_and_long_enough(tmp_path):
    p = tmp_path / "wm.key"
    write_key(p)
    k = p.read_bytes()
    assert len(k) == 32
    assert verify(sign(TEXT, LABEL, k), k).valid is True


@pytest.mark.skipif(not hasattr(__import__("os"), "fchmod"),
                    reason="platform has no POSIX file modes")
def test_a_key_is_not_world_readable(tmp_path):
    p = tmp_path / "wm.key"
    write_key(p)
    assert p.stat().st_mode & 0o077 == 0
