"""Both directions of the one-sided test.

The positive cases matter, but the negative cases matter more: a detector that
fires on Devanagari orthography or on an emoji is worse than no detector, and
the whole value of a positive rests on those never happening.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wm_hook.carriers import carrier_class
from wm_hook.verdict import (
    ANOMALY,
    BENIGN,
    NONE,
    PAYLOAD,
    classify,
    render,
)

ZWSP, ZWNJ, ZWJ = "​", "‌", "‍"


def tag_block(s: str) -> str:
    return "".join(chr(0xE0000 + ord(c)) for c in s)


def zw_bits(data: bytes) -> str:
    bits = "".join(f"{b:08b}" for b in data)
    return "".join(ZWSP if b == "0" else ZWNJ for b in bits)


# ---------------------------------------------------------------------------
# Negatives. Each of these is real text that a naive detector reports as a hit.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,why", [
    ("just some ordinary prose.", "no carriers at all"),
    ("def f(x):\n    return x + 1\n", "source code"),
    ("﻿# A file with a byte-order mark\n", "BOM at offset zero"),
    ("weather ☀️ today", "emoji presentation selector"),
    ("family \U0001f468‍\U0001f469‍\U0001f467", "emoji ZWJ sequence"),
    ("\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f",
     "subdivision flag tag sequence"),
    ("तथा अयम्‌ एकम्‌",
     "Devanagari virama joiners -- the case the cleaner gets wrong"),
    ("การ​ทดสอบ", "Thai word separator"),
    ("café : 5 €", "French typographic spaces"),
])
def test_legitimate_text_is_not_a_carrier(text, why):
    v = classify(text)
    assert not v.carrier_present, f"{why}: got {v.level} via {[e.name for e in v.evidence]}"
    assert v.level in (NONE, BENIGN), why


def test_half_escaped_emoji_in_source_is_not_an_orphan_selector():
    # Found in a real test file. The base is spelled as an ASCII escape, so a
    # base lookup sees the trailing hex digit and calls the selector orphaned.
    v = classify('assert render() == "\\\\U0001f441️ 10"\n')
    assert v.level == BENIGN
    assert not v.carrier_present


def test_the_escape_exemption_covers_exactly_one_selector():
    # An unbounded exemption is a channel -- the lesson the flag-tag bound
    # taught. A run after an escape must stay unexplained.
    run = "️" * 10
    v = classify('x = "\\\\U0001f441' + run + '"\n')
    assert v.carrier_present
    assert v.unexplained == 9


def test_a_clean_verdict_refuses_to_imply_human_authorship():
    v = classify("Perfectly ordinary text.")
    assert v.level is NONE or v.level == NONE
    assert "NOT evidence that a human wrote" in v.means
    assert "statistical watermark" in v.means.lower()


# ---------------------------------------------------------------------------
# Positives.
# ---------------------------------------------------------------------------

def test_tag_block_payload_is_decoded_and_named():
    text = "Shipped today." + tag_block("gen=claude-opus-4;run=8f31c2a0")
    v = classify(text)
    assert v.level == PAYLOAD
    assert v.confidence == "high"
    assert v.carrier_present
    assert v.payloads[0]["decoded"] == "gen=claude-opus-4;run=8f31c2a0"
    assert "claude" in v.payloads[0]["identifiers"]
    assert "tag_outside_flag" in {e.name for e in v.evidence}


def test_zero_width_bit_stream_is_read_as_a_bit_stream():
    v = classify("The release ships Tuesday." + zw_bits(b"AI"))
    assert v.carrier_present
    names = {e.name for e in v.evidence}
    assert "binary_alphabet" in names
    assert "byte_aligned" in names


def test_variation_selector_run_on_a_letter_is_payload_not_presentation():
    # A single selector after an emoji is legitimate; a run on a plain letter
    # is a byte string. The difference is the base, and it is the whole test.
    run = "".join(chr(0xE0100 + b - 16) if b >= 16 else chr(0xFE00 + b)
                  for b in b"model=x")
    v = classify("hello" + run + "world")
    assert v.carrier_present


def test_private_use_in_prose_is_flagged():
    v = classify("The value is  as of today.")
    assert v.carrier_present
    assert "private_use_in_text" in {e.name for e in v.evidence}


def test_carrier_between_latin_letters_needs_no_run():
    # Four separate marks, none adjacent, all between ASCII letters.
    v = classify(f"a{ZWSP}b c{ZWSP}d e{ZWSP}f g{ZWSP}h")
    assert "latin_context" in {e.name for e in v.evidence}
    assert v.carrier_present


def test_evenly_spaced_marks_read_as_one_per_token():
    v = classify("".join(f"word{ZWJ}" for _ in range(8)))
    assert "periodic" in {e.name for e in v.evidence}


# ---------------------------------------------------------------------------
# The middle ground has to exist, or every stray character becomes a finding.
# ---------------------------------------------------------------------------

def test_one_isolated_stray_carrier_is_an_anomaly_not_a_finding():
    v = classify("Pasted from a web page:⁠ see below.")
    assert v.level == ANOMALY
    assert not v.carrier_present
    assert "debris" in v.means


def test_anomaly_still_reports_the_character():
    v = classify("Pasted from a web page:⁠ see below.")
    assert v.unexplained == 1
    assert v.by_class == {"zero_width": 1}


# ---------------------------------------------------------------------------
# Reporting contract.
# ---------------------------------------------------------------------------

def test_evidence_is_itemised_so_a_verdict_can_be_argued_with():
    v = classify("Shipped." + tag_block("gen=2026"))
    assert v.evidence, "a positive with no stated reason is unfalsifiable"
    for e in v.evidence:
        assert e.detail and e.weight > 0
        assert e.name in e.to_dict()["name"]


def test_render_marks_positives_and_stays_quiet_on_clean_files():
    hit = render("a.md", classify("x" + tag_block("gen=2026")))
    assert hit[0].startswith("CARRIER!")
    assert any("gen=2026" in line for line in hit)
    clean = render("b.md", classify("nothing here"))
    assert clean[0].startswith("CLEAN")


def test_to_dict_is_json_safe():
    import json

    d = classify("x" + tag_block("gen=2026")).to_dict()
    assert json.loads(json.dumps(d))["carrier_present"] is True


# ---------------------------------------------------------------------------
# The null result is a property of the world, not of the instrument.
#
# This repository was written almost entirely by an agent and scans clean. That
# looks like a contradiction until the unstated premise is made explicit: the
# inference "AI wrote it, therefore a carrier is present" assumes AI writing
# embeds carriers, which is exactly the claim under test. These are the positive
# controls that separate "nothing is there" from "we cannot see it".
# ---------------------------------------------------------------------------

AI_WRITTEN = Path(__file__).resolve().parents[1] / "src" / "wm_hook" / "atomic.py"


def test_agent_written_source_in_this_repo_has_no_carrier():
    v = classify(AI_WRITTEN.read_bytes().decode("utf-8"))
    assert not v.carrier_present
    assert v.unexplained == 0


@pytest.mark.parametrize("inject,expect", [
    (lambda: tag_block("gen=claude"), "tag_outside_flag"),
    (lambda: zw_bits(b"\x91\x3f"), "binary_alphabet"),
    (lambda: "", "private_use_in_text"),
])
def test_the_same_file_lights_up_the_moment_a_carrier_is_added(inject, expect):
    """Blindness and absence are distinguishable, and this is how.

    If the detector could not see a carrier in agent-written source, injecting
    one would change nothing. It changes the verdict every time, so the clean
    result above is the absence of material rather than a failure to look.
    """
    original = AI_WRITTEN.read_bytes().decode("utf-8")
    v = classify(original + "\n# " + inject() + "\n")
    assert v.carrier_present
    assert expect in {e.name for e in v.evidence}


def test_there_is_no_room_for_a_codepoint_carrier_to_hide():
    """604,030 characters of agent-written text, 0.17% of it non-ASCII.

    A codepoint carrier needs codepoints. This file is representative: the
    non-ASCII inventory of the whole repository is em dashes, arrows, box
    drawing and the detector's own documented examples.
    """
    text = AI_WRITTEN.read_bytes().decode("utf-8")
    invisible = [c for c in text if carrier_class(ord(c)) is not None]
    assert invisible == [], f"unexpected carrier material: {invisible!r}"


@pytest.mark.xfail(
    strict=True,
    reason="Known false positive. Nerd Font and icon-font glyphs are private-use "
           "codepoints sitting in ASCII config text, which is exactly the shape "
           "private_use_in_text scores as payload. The preservation corpus says "
           "this file must never be flagged, and it is. Distinguishing an icon "
           "font from a payload needs more than adjacency -- probably the range "
           "(Nerd Fonts cluster in U+E000-U+F8FF) plus the file's role -- and "
           "that is a change with its own false-positive profile.",
)
def test_icon_font_private_use_is_not_payload():
    fixture = (
        Path(__file__).resolve().parent
        / "corpus" / "preservation" / "icon_font_private_use.txt"
    )
    v = classify(fixture.read_bytes().decode("utf-8"))
    assert not v.carrier_present


def test_capacity_is_reported_in_bits():
    v = classify("The release ships Tuesday." + zw_bits(b"AI"))
    assert v.bits_available == 16  # one bit per zero-width codepoint
