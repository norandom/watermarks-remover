"""Guards for the preservation corpus (tasks.md 1.3, Requirement 11.1).

The corpus in ``tests/corpus/preservation/`` is the reference set of files
that must survive cleaning **byte-identically**. Task 4.2 will run the cleaner
over it; this module owns something earlier and more fragile — the fixtures
themselves.

Three things are asserted here, and each closes a way the corpus could rot
without anyone noticing:

* **The bytes are what they were authored to be.** Every entry's exact content
  is recorded below as an escaped literal. A fixture whose invisible
  characters an editor normalised, whose CRLF git rewrote, or which this
  repository's own hook stripped on the way into a commit, is not a weaker
  fixture — it is a fixture that silently proves nothing. Byte equality
  against a recorded literal is the only check that catches that, and it
  doubles as the reproduction source if one is ever damaged.

* **Every entry carries the rule that protects it.** The annotations live in
  ``manifest.json`` beside the files, because a preservation entry must come
  out byte-identical and therefore cannot carry an inline comment. Each entry
  names the requirement criteria that keep it intact and the task that
  implements them, so a future change cannot reclassify an entry without
  editing the claim that says why it survives.

* **The manifest describes the file it is attached to.** Declared codepoints,
  encoding, line endings and trailing-newline state are all checked against
  the actual bytes. Adding an invisible character to a fixture without
  declaring it fails here.

Every non-ASCII character in this module is written as an escape. That is not
only the rule about invisible carriers in test sources: the corpus is
right-to-left in places, and escaping keeps the source unambiguous to read and
impossible for an editor to renormalise. The corpus *data* files are the
deliberate exception — they must hold the real bytes, which is why they live
outside the test modules and are pinned by ``tests/corpus/** -text`` in
``.gitattributes``.
"""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path

import pytest
from conftest import CORPUS_MANIFEST_NAME, PRESERVATION_CORPUS, load_corpus

# --------------------------------------------------------------------------
# Named carriers, so the fixtures below read as intent rather than as escapes
# --------------------------------------------------------------------------

_ZWSP = "\u200b"
_ZWNJ = "\u200c"
_ZWJ = "\u200d"
_LRM = "\u200e"
_RLM = "\u200f"
_RLE = "\u202b"
_PDF = "\u202c"
_RLI = "\u2067"
_FSI = "\u2068"
_PDI = "\u2069"
_VS1 = "\ufe00"
_VS15 = "\ufe0e"
_VS16 = "\ufe0f"
_IVS17 = "\U000e0100"
_TAG_CANCEL = "\U000e007f"
_NBSP = "\u00a0"
_NNBSP = "\u202f"
_BOM = "\ufeff"
_VIRAMA = "\u094d"


def _tag(letters: str) -> str:
    """Encode ISO 3166-2 subdivision letters as Unicode tag characters."""
    return "".join(chr(0xE0000 + ord(ch)) for ch in letters)


# --------------------------------------------------------------------------
# The authored bytes
# --------------------------------------------------------------------------

#: Every corpus file, keyed by name, with its exact contents.
EXPECTED_BYTES: dict[str, bytes] = {
    # -- emoji -----------------------------------------------------------
    "emoji_zwj_sequences.txt": (
        f"family: \U0001f468{_ZWJ}\U0001f469{_ZWJ}\U0001f467{_ZWJ}\U0001f466\n"
        f"technologist: \U0001f469{_ZWJ}\U0001f4bb\n"
        f"rainbow flag: \U0001f3f3{_VS16}{_ZWJ}\U0001f308\n"
        f"firefighter: \U0001f468\U0001f3fd{_ZWJ}\U0001f692\n"
        f"people holding hands: \U0001f9d1{_ZWJ}\U0001f91d{_ZWJ}\U0001f9d1\n"
        f"red heart: \u2764{_VS16}\n"
    ).encode(),
    "emoji_subdivision_flags.txt": (
        f"scotland: \U0001f3f4{_tag('gbsct')}{_TAG_CANCEL}\n"
        f"wales: \U0001f3f4{_tag('gbwls')}{_TAG_CANCEL}\n"
        f"england: \U0001f3f4{_tag('gbeng')}{_TAG_CANCEL}\n"
    ).encode(),
    "emoji_presentation_selectors.txt": (
        f"information: \u2139{_VS16}\n"
        f"double exclamation: \u203c{_VS16}\n"
        f"exclamation question: \u2049{_VS16}\n"
        f"up-right arrow: \u2934{_VS16}\n"
        f"down-right arrow: \u2935{_VS16}\n"
        f"airplane, text presentation: \u2708{_VS15}\n"
    ).encode(),
    # -- Arabic-script joiners -------------------------------------------
    "arabic_joiners.txt": (
        "# Arabic: ZWNJ inside a compound name\n"
        f"\u0639\u0628\u062f{_ZWNJ}\u0627\u0644\u0644\u0647\n"
        "# Arabic: ZWNJ before punctuation\n"
        f"\u0639\u0628\u062f{_ZWNJ}\u0627\u0644\u0644\u0647{_ZWNJ}\u060c\n"
        "# Arabic: ZWNJ beside Arabic-Indic digits\n"
        f"\u0627\u0644\u0635\u0641\u062d\u0629{_ZWNJ}"
        f"\u0661\u0662\u0663{_ZWNJ}\u0623\n"
        "# Arabic: ZWJ forcing a connected form between letters\n"
        f"\u0645{_ZWJ}\u0646\n"
        "# Arabic: ZWNJ before a line break\n"
        f"\u0639\u0628\u062f{_ZWNJ}\n"
    ).encode(),
    "persian_joiners.txt": (
        "# Persian: ZWNJ inside a compound verb\n"
        f"\u0645\u06cc{_ZWNJ}\u0631\u0648\u062f\n"
        "# Persian: ZWNJ before punctuation\n"
        f"\u0646\u0645\u06cc{_ZWNJ}\u062e\u0648\u0627\u0647\u0645{_ZWNJ}\u061f\n"
        "# Persian: ZWNJ beside Persian digits\n"
        f"\u06f1\u06f4\u06f0\u06f3{_ZWNJ}\u0634\n"
        "# Persian: ZWNJ before a line break\n"
        f"\u06a9\u062a\u0627\u0628{_ZWNJ}\u0647\u0627{_ZWNJ}\n"
        "# Persian: ZWNJ at end of file, with no trailing newline\n"
        f"\u0645\u06cc{_ZWNJ}\u0631\u0648\u062f{_ZWNJ}"
    ).encode(),
    "urdu_joiners.txt": (
        "# Urdu: ZWNJ inside a compound greeting\n"
        f"\u062e\u0648\u0634{_ZWNJ}\u0622\u0645\u062f\u06cc\u062f\n"
        "# Urdu: ZWNJ before the Urdu full stop\n"
        f"\u062e\u0648\u0634{_ZWNJ}\u0622\u0645\u062f\u06cc\u062f{_ZWNJ}\u06d4\n"
        "# Urdu: ZWNJ beside extended Arabic-Indic digits\n"
        f"\u0635\u0641\u062d\u06c1{_ZWNJ}\u06f1\u06f2\u06f3{_ZWNJ}\u0628\n"
        "# Urdu: ZWNJ before a line break\n"
        f"\u067e\u0627\u06a9\u0633\u062a\u0627\u0646{_ZWNJ}\n"
    ).encode(),
    "persian_frontmatter_values.md": (
        "---\n"
        f"title: \u0645\u06cc{_ZWNJ}\u0631\u0648\u062f{_ZWNJ}\n"
        "lang: fa\n"
        "tags:\n"
        f"  - \u06a9\u062a\u0627\u0628{_ZWNJ}\u0647\u0627{_ZWNJ}\n"
        f"  - \u062e\u0648\u0634{_ZWNJ}\u0622\u0645\u062f\u06cc\u062f\n"
        "---\n"
        "\n"
        f"# \u06a9\u062a\u0627\u0628{_ZWNJ}\u0647\u0627\n"
        "\n"
        f"\u0645\u06cc{_ZWNJ}\u0631\u0648\u062f{_ZWNJ}.\n"
    ).encode(),
    # -- scripts that use U+200B as a word separator ---------------------
    "thai_zwsp.txt": (
        "# Thai: U+200B separates words\n"
        f"\u0e2a\u0e27\u0e31\u0e2a\u0e14\u0e35{_ZWSP}"
        f"\u0e04\u0e23\u0e31\u0e1a{_ZWSP}"
        "\u0e20\u0e32\u0e29\u0e32\u0e44\u0e17\u0e22\n"
    ).encode(),
    "lao_zwsp.txt": (
        "# Lao: U+200B separates words\n"
        f"\u0eaa\u0eb0\u0e9a\u0eb2\u0e8d\u0e94\u0eb5{_ZWSP}"
        "\u0e9e\u0eb2\u0eaa\u0eb2\u0ea5\u0eb2\u0ea7\n"
    ).encode(),
    "khmer_zwsp.txt": (
        "# Khmer: U+200B separates words\n"
        f"\u179f\u17bd\u179f\u17d2\u178f\u17b8{_ZWSP}"
        "\u1797\u17b6\u179f\u17b6\u1781\u17d2\u1798\u17c2\u179a\n"
    ).encode(),
    "myanmar_zwsp.txt": (
        "# Myanmar: U+200B separates words\n"
        f"\u1019\u1004\u103a\u1039\u1002\u101c\u102c\u1015\u102b{_ZWSP}"
        "\u1019\u103c\u1014\u103a\u1019\u102c\u1018\u102c\u101e\u102c\n"
    ).encode(),
    # -- ideographic variation -------------------------------------------
    "cjk_variation_selectors.txt": (
        "# CJK: one legal variation selector per ideographic base\n"
        f"\u8fbb{_VS1} \u9038{_VS1}\n"
        f"\u845b{_IVS17} \u82a6{_IVS17} \u908a{_IVS17}\n"
    ).encode(),
    # -- Indic conjuncts -------------------------------------------------
    "devanagari_conjuncts.txt": (
        "# Devanagari: ZWNJ forces an explicit virama\n"
        f"\u0915{_VIRAMA}{_ZWNJ}\u0937\n"
        "# Devanagari: ZWJ forces a half form\n"
        f"\u0915{_VIRAMA}{_ZWJ}\u0937\n"
        "# Marathi: the eyelash reph needs its ZWJ\n"
        f"\u0930{_VIRAMA}{_ZWJ}\u092f\n"
        "# The same conjunct with no joiner at all\n"
        "\u0939\u093f\u0928\u094d\u0926\u0940\n"
    ).encode(),
    # -- private use -----------------------------------------------------
    "icon_font_private_use.txt": (
        "# Icon font: private-use glyphs from a patched Nerd Font\n"
        "branch \ue0a0 separators \ue0b0\ue0b2 github \uf09b folder \uf07b\n"
        "supplementary planes: \U000f0001 \U00100001\n"
    ).encode(),
    # -- typographic spaces ----------------------------------------------
    "french_typography.txt": (
        "# French typography: the no-break spaces are load-bearing\n"
        f"\u00ab{_NBSP}Bonjour{_NBSP}!{_NBSP}\u00bb dit-elle.\n"
        f"Il a r\u00e9pondu{_NNBSP}: \u00ab{_NNBSP}Merci{_NNBSP}!{_NNBSP}\u00bb\n"
        f"Prix{_NNBSP}: 12{_NNBSP}500{_NBSP}\u20ac\n"
    ).encode(),
    # -- byte-level fidelity ---------------------------------------------
    "crlf_markdown_frontmatter.md": (
        "---\r\n"
        "title: Comparing Claude and Gemini output\r\n"
        "date: 2026-03-14\r\n"
        "tags:\r\n"
        "  - review\r\n"
        "  - tooling\r\n"
        "---\r\n"
        "\r\n"
        "# Comparing Claude and Gemini output\r\n"
        "\r\n"
        "The blank lines and the indentation below are part of this file.\r\n"
        "\r\n"
        "---\r\n"
        "\r\n"
        "    an indented code block\r\n"
        "\r\n"
        "Done.\r\n"
    ).encode(),
    "bom_prefixed.csv": (
        f"{_BOM}name,r\u00f4le,ville\r\n"
        "\u00c9dith,r\u00e9dactrice,Gen\u00e8ve\r\n"
        "Zo\u00e9,relectrice,Montr\u00e9al\r\n"
    ).encode(),
    # Latin-1, not UTF-8: every one of \xe9 \xc9 \xe8 \xef \xe7 \xdc \xf1 \xa0
    # \xa4 is either a bare continuation byte or a lead byte followed by one
    # that cannot continue the sequence.
    "latin1_text.txt": (
        b"# latin-1: these bytes are not valid UTF-8 and must round-trip\n"
        b"R\xe9dactrice : \xc9dith Pi\xe8ce\n"
        b"Na\xefve fa\xe7ade, \xdcbermut, ma\xf1ana\n"
        b"Tarif : 3\xa050 \xa4\n"
    ),
    # -- bidi ------------------------------------------------------------
    "bidi_marks_and_embeddings.txt": (
        "# Bidi: marks, a paired embedding and isolates; no overrides\n"
        f"left-to-right mark {_LRM} and right-to-left mark {_RLM}\n"
        f"paired embedding: {_RLE}\u0639\u0631\u0628\u064a{_PDF} done\n"
        f"isolate: {_RLI}\u0639\u0631\u0628\u064a{_PDI} done\n"
        f"first-strong isolate: {_FSI}\u0639\u0631\u0628\u064a{_PDI} done\n"
    ).encode(),
}

# --------------------------------------------------------------------------
# Annotation contract
# --------------------------------------------------------------------------

#: Every entry must carry all of these. ``protected_by`` and ``rule`` are the
#: point of the corpus: the criterion that keeps the entry intact, and the
#: same claim in prose.
REQUIRED_ANNOTATIONS = (
    "summary",
    "protected_by",
    "rule",
    "implemented_by",
    "policy",
    "protected_codepoints",
    "encoding",
    "line_endings",
    "trailing_newline",
)

#: Requirement 11.1 names the classes this corpus has to cover; these are the
#: criteria that do the protecting for those classes, plus the byte-fidelity
#: criteria of Requirement 6 that the corpus also exercises.
REQUIRED_CRITERIA = frozenset(
    {
        "1.4",  # a mark-free file is left byte-for-byte identical
        "2.2",  # tag characters inside a complete subdivision flag survive
        "2.3",  # a selector following a base it can legally modify survives
        "3.1",  # emoji joiner glue
        "3.2",  # presentation selectors on emoji-presentable bases
        "3.3",  # orthographic joiners, including at edge positions
        "3.4",  # U+200B as a word separator
        "3.5",  # private use preserved by default
        "3.6",  # rules read the neighbouring base, not another carrier
        "3.7",  # directional marks and paired embeddings
        "4.4",  # normalisation disabled leaves space homoglyphs alone
        "4.5",  # typographic space homoglyphs
        "5.2",  # a vendor name in a value is not a provenance key
        "6.1",  # line-ending convention
        "6.2",  # uniform endings stay uniform
        "6.3",  # trailing-newline presence
        "6.4",  # untargeted blank lines and indentation
        "6.5",  # a required byte-order mark
        "6.6",  # undecodable bytes round-trip
    }
)

#: tasks.md implementation tasks an entry may name. A typo would point a
#: reader at a task that does not exist.
IMPLEMENTING_TASKS = frozenset({"2.2", "2.4", "2.5", "2.6", "2.7", "2.8", "3.1"})

#: The transform flags conftest documents, mirrored so a policy annotation can
#: be range-checked before it is handed to the factory.
POLICY_FLAGS = frozenset(
    {
        "normalize_spaces",
        "strip_private_use",
        "strip_bom",
        "strip_bidi",
        "strip_emoji_glue",
        "aggressive_homoglyphs",
        "drop_frontmatter_keys",
    }
)

#: Removed unconditionally (Requirement 2.4) — a preservation entry holding
#: one of these would be asserting something false.
UNCONDITIONALLY_REMOVED = ("\u202d", "\u202e")

#: The scripts whose U+200B is a word separator, and the block each entry's
#: bases must stay inside for the rule to apply (Requirement 3.4).
ZWSP_SCRIPT_BLOCKS = {
    "thai_zwsp.txt": ("\u0e01", "\u0e5b"),
    "lao_zwsp.txt": ("\u0e80", "\u0edf"),
    "khmer_zwsp.txt": ("\u1780", "\u17ff"),
    "myanmar_zwsp.txt": ("\u1000", "\u109f"),
}

JOINER_ENTRIES = ("arabic_joiners.txt", "persian_joiners.txt", "urdu_joiners.txt")

# Loaded at import: a missing corpus, an unannotated file or an annotation
# without a file must break collection rather than quietly shrink this module.
ENTRIES = load_corpus(PRESERVATION_CORPUS)
BY_NAME = {entry.name: entry for entry in ENTRIES}
NAMES = tuple(BY_NAME)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _decode(name: str) -> str:
    """Decode an entry the way the Cleaner will (Requirement 6.6)."""
    return BY_NAME[name].read_bytes().decode("utf-8", "surrogateescape")


def _at(text: str, index: int) -> str:
    return text[index] if 0 <= index < len(text) else ""


def _category(text: str, index: int) -> str:
    ch = _at(text, index)
    return unicodedata.category(ch) if ch else ""


def _is_variation_selector(ch: str) -> bool:
    return "\ufe00" <= ch <= "\ufe0f" or "\U000e0100" <= ch <= "\U000e01ef"


def _is_tag_character(ch: str) -> bool:
    return "\U000e0000" <= ch <= "\U000e007f"


def _is_carrier_class(ch: str) -> bool:
    """True for anything invisible, private-use or a space homoglyph.

    This is the set an entry must declare. It is deliberately wider than what
    the Cleaner removes: a preservation entry's whole job is to hold members
    of this set that must *not* be removed, so the manifest has to account for
    every one of them.
    """
    if _is_variation_selector(ch):
        return True
    category = unicodedata.category(ch)
    if category in ("Cf", "Co"):
        return True
    return category == "Zs" and ch != " "


def _previous_base(text: str, index: int) -> str:
    """The last non-carrier character before *index*.

    Requirement 3.6: adjacency rules read the neighbouring base, never
    another carrier.
    """
    for candidate in range(index - 1, -1, -1):
        if not _is_carrier_class(text[candidate]):
            return text[candidate]
    return ""


def _codepoint(ch: str) -> str:
    return f"U+{ord(ch):04X}"


# --------------------------------------------------------------------------
# Enumeration and annotations — the observable of tasks.md 1.3
# --------------------------------------------------------------------------


def test_corpus_holds_exactly_the_authored_entries():
    # Not a subset check. An entry that appeared without a recorded literal
    # would be enumerated by the loader and byte-checked by nothing.
    assert set(NAMES) == set(EXPECTED_BYTES)


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_entry_bytes_match_the_recorded_literal(name):
    assert BY_NAME[name].read_bytes() == EXPECTED_BYTES[name]


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_entry_is_not_a_placeholder(name):
    data = BY_NAME[name].read_bytes()

    assert len(data) >= 40
    assert data.strip()


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_entry_carries_every_required_annotation(name):
    entry = BY_NAME[name]

    for key in REQUIRED_ANNOTATIONS:
        entry.annotation(key)  # raises, naming the entry, when absent
    assert entry.annotation("summary").strip()
    assert entry.annotation("rule").strip()


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_entry_names_the_criteria_that_protect_it(name):
    protected_by = BY_NAME[name].annotation("protected_by")

    assert isinstance(protected_by, list) and protected_by
    for criterion in protected_by:
        requirement, _, item = criterion.partition(".")
        assert requirement.isdigit() and item.isdigit(), criterion
        assert 1 <= int(requirement) <= 11, criterion


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_entry_names_the_task_that_implements_its_protection(name):
    implemented_by = BY_NAME[name].annotation("implemented_by")

    assert isinstance(implemented_by, list) and implemented_by
    assert set(implemented_by) <= IMPLEMENTING_TASKS


def test_corpus_covers_every_preservation_rule_requirement_11_1_names():
    cited = {
        criterion for entry in ENTRIES for criterion in entry.annotation("protected_by")
    }

    assert REQUIRED_CRITERIA <= cited


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_policy_annotation_names_only_documented_flags(name, policy_variant):
    overrides = BY_NAME[name].annotation("policy")

    assert isinstance(overrides, dict)
    assert set(overrides) <= POLICY_FLAGS
    # Round-trips through the harness factory, which is what task 4.2 will
    # splat into the real CleanPolicy.
    policy_variant(**overrides)


# --------------------------------------------------------------------------
# The manifest describes the actual bytes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_declared_codepoints_are_exactly_those_present(name):
    present = sorted({ch for ch in _decode(name) if _is_carrier_class(ch)}, key=ord)

    assert BY_NAME[name].annotation("protected_codepoints") == [
        _codepoint(ch) for ch in present
    ]


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_declared_encoding_matches_the_bytes(name):
    data = BY_NAME[name].read_bytes()
    encoding = BY_NAME[name].annotation("encoding")

    if encoding == "latin-1":
        with pytest.raises(UnicodeDecodeError):
            data.decode("utf-8")
        assert data.decode("latin-1")
    elif encoding == "utf-8-sig":
        assert data.startswith(b"\xef\xbb\xbf")
        assert data.decode("utf-8")
    else:
        assert encoding == "utf-8"
        assert not data.startswith(b"\xef\xbb\xbf")
        assert data.decode("utf-8")


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_declared_line_endings_match_the_bytes(name):
    data = BY_NAME[name].read_bytes()
    line_endings = BY_NAME[name].annotation("line_endings")

    if line_endings == "CRLF":
        assert b"\r\n" in data
        # Uniform (Requirement 6.2): nothing is left once the pairs are gone.
        assert b"\r" not in data.replace(b"\r\n", b"")
        assert b"\n" not in data.replace(b"\r\n", b"")
    else:
        assert line_endings == "LF"
        assert b"\n" in data
        assert b"\r" not in data


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_declared_trailing_newline_matches_the_bytes(name):
    data = BY_NAME[name].read_bytes()

    assert BY_NAME[name].annotation("trailing_newline") is data.endswith(b"\n")


# --------------------------------------------------------------------------
# Nothing in here may be contraband
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_no_entry_carries_an_unconditionally_removed_character(name):
    text = _decode(name)

    # A bidi override (Requirement 2.4) is removed whatever surrounds it, so
    # an entry containing one could never come out byte-identical.
    for override in UNCONDITIONALLY_REMOVED:
        assert override not in text


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_a_byte_order_mark_appears_only_at_offset_zero(name):
    text = _decode(name)

    # Interior U+FEFF is a carrier however the file is encoded; only the
    # offset-zero occurrence is a required signal (Requirement 6.5).
    assert _BOM not in text[1:]
    if _BOM in text:
        assert BY_NAME[name].annotation("encoding") == "utf-8-sig"


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_variation_selectors_follow_a_base_and_never_repeat(name):
    text = _decode(name)

    for index, ch in enumerate(text):
        if not _is_variation_selector(ch):
            continue
        assert index > 0, f"{name}: selector at offset 0 has no base"
        previous = text[index - 1]
        # An orphan selector is contraband (Requirement 2.3), and only the
        # first selector of a run is legal (design.md, the selector-run rule).
        assert not _is_variation_selector(previous)
        assert previous not in " \n\r\t"


@pytest.mark.parametrize("name", sorted(EXPECTED_BYTES))
def test_tag_characters_only_form_complete_subdivision_flags(name):
    text = _decode(name)
    if name != "emoji_subdivision_flags.txt":
        assert not any(_is_tag_character(ch) for ch in text)
        return

    runs, current, start = [], "", -1
    for index, ch in enumerate(text):
        if _is_tag_character(ch):
            if not current:
                start = index
            current += ch
        elif current:
            runs.append((start, current))
            current = ""
    if current:
        runs.append((start, current))

    assert runs
    for start, run in runs:
        assert _at(text, start - 1) == "\U0001f3f4"
        assert run.endswith(_TAG_CANCEL)
        payload = run[:-1]
        # Requirement 2.2: a conforming payload only, never an open-ended one.
        assert 2 <= len(payload) <= 6
        assert all("\U000e0061" <= ch <= "\U000e007a" for ch in payload)


# --------------------------------------------------------------------------
# Per-category content: the positions Requirement 3 actually names
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", JOINER_ENTRIES)
def test_joiner_entries_cover_every_edge_position(name):
    text = _decode(name)
    positions = [i for i, ch in enumerate(text) if ch in (_ZWNJ, _ZWJ)]
    assert positions

    # Requirement 3.3 names four positions; all four must be represented.
    assert any(_at(text, i + 1) == "\n" for i in positions), "none before a newline"
    assert any(
        _category(text, i + 1).startswith("P") for i in positions
    ), "none before punctuation"
    assert any(
        "Nd" in (_category(text, i - 1), _category(text, i + 1)) for i in positions
    ), "none beside a digit"
    assert any(
        _category(text, i - 1) == "Lo" and _category(text, i + 1) == "Lo"
        for i in positions
    ), "none between letters"


def test_persian_entry_ends_at_end_of_file_with_a_joiner():
    data = BY_NAME["persian_joiners.txt"].read_bytes()

    # The one entry with no trailing newline: the joiner is the last character
    # in the file, the harshest form of "the end of a text value".
    assert data.endswith(_ZWNJ.encode())
    assert not data.endswith(b"\n")


def test_frontmatter_entry_ends_a_scalar_value_with_a_joiner():
    lines = _decode("persian_frontmatter_values.md").split("\n")

    assert lines[0] == "---"
    assert lines[1].startswith("title: ") and lines[1].endswith(_ZWNJ)
    # An indented list item whose value also ends with a joiner, so the
    # end-of-value rule is exercised inside a nested block too.
    assert any(line.startswith("  - ") and line.endswith(_ZWNJ) for line in lines)


@pytest.mark.parametrize("name,bounds", sorted(ZWSP_SCRIPT_BLOCKS.items()))
def test_zwsp_sits_between_bases_of_its_own_script(name, bounds):
    text = _decode(name)
    low, high = bounds
    positions = [i for i, ch in enumerate(text) if ch == _ZWSP]
    assert positions

    # Requirement 3.4 keys off the surrounding script, so a separator whose
    # neighbours were ASCII would not be protected and the fixture would be
    # asserting the wrong thing.
    for index in positions:
        assert low <= _at(text, index - 1) <= high
        assert low <= _at(text, index + 1) <= high


def test_emoji_entry_glues_pictographic_bases():
    text = _decode("emoji_zwj_sequences.txt")
    positions = [i for i, ch in enumerate(text) if ch == _ZWJ]

    assert len(positions) >= 5
    for index in positions:
        # Both neighbouring bases are pictographs or emoji modifiers, which is
        # what makes the joiner glue rather than a carrier (Requirement 3.1),
        # and the lookup skips carriers per Requirement 3.6.
        assert unicodedata.category(_previous_base(text, index)) in ("So", "Sk")
        assert _category(text, index + 1) == "So"


def test_presentation_selector_entry_covers_the_widened_base_set():
    text = _decode("emoji_presentation_selectors.txt")

    # design.md: `_is_emoji_base` is widened for exactly these five, and a
    # text-presentation selector is equally legitimate (Requirement 3.2).
    for base in "\u2139\u203c\u2049\u2934\u2935":
        assert base + _VS16 in text
    assert "\u2708" + _VS15 in text


def test_ideographic_entry_gives_each_base_exactly_one_selector():
    text = _decode("cjk_variation_selectors.txt")
    selectors = [i for i, ch in enumerate(text) if _is_variation_selector(ch)]

    assert len(selectors) >= 4
    for index in selectors:
        # A unified ideograph or an extension-A ideograph; a selector after
        # anything else would not be the case this fixture claims to cover.
        assert "\u3400" <= text[index - 1] <= "\u9fff"


def test_devanagari_entry_covers_both_joiner_roles():
    text = _decode("devanagari_conjuncts.txt")

    assert _VIRAMA + _ZWNJ in text  # explicit virama
    assert _VIRAMA + _ZWJ in text  # half form and eyelash reph


def test_private_use_entry_spans_the_basic_and_supplementary_planes():
    private_use = [
        ch for ch in _decode("icon_font_private_use.txt")
        if unicodedata.category(ch) == "Co"
    ]

    assert any("\ue000" <= ch <= "\uf8ff" for ch in private_use)
    assert any(ch >= "\U000f0000" for ch in private_use)


def test_french_entry_holds_both_no_break_spaces_under_a_disabling_policy():
    text = _decode("french_typography.txt")

    assert _NBSP in text and _NNBSP in text
    # The only entry whose byte-identity depends on a policy: the default
    # normalises spaces, so the manifest has to say so (Requirements 4.4, 4.5).
    assert BY_NAME["french_typography.txt"].annotation("policy") == {
        "normalize_spaces": False
    }


def test_crlf_markdown_entry_is_mark_free_frontmatter():
    text = _decode("crlf_markdown_frontmatter.md")

    assert not any(_is_carrier_class(ch) for ch in text)
    assert text.startswith("---\r\n")
    # A vendor name in a value, which Requirement 5.2 keeps, and the structure
    # Requirement 6.4 keeps: blank lines, an indented list, an indented block.
    assert "title: Comparing Claude and Gemini output\r\n" in text
    assert "\r\n  - review\r\n" in text
    assert "\r\n\r\n    an indented code block\r\n" in text


def test_bom_entry_is_a_signature_followed_by_real_content():
    data = BY_NAME["bom_prefixed.csv"].read_bytes()

    assert data.startswith(b"\xef\xbb\xbf")
    body = data[3:].decode("utf-8")
    assert body.startswith("name,")
    # Non-ASCII content is what makes the mark a required encoding signal
    # rather than decoration (Requirement 6.5).
    assert any(ord(ch) > 0x7F for ch in body)


def test_latin1_entry_round_trips_through_surrogate_escaping():
    data = BY_NAME["latin1_text.txt"].read_bytes()

    with pytest.raises(UnicodeDecodeError):
        data.decode("utf-8")
    # Requirement 6.6: this is precisely the round-trip the Cleaner must not
    # break, so the fixture has to be able to support it.
    round_tripped = data.decode("utf-8", "surrogateescape").encode(
        "utf-8", "surrogateescape"
    )
    assert round_tripped == data


def test_bidi_entry_holds_marks_and_balanced_pairs_only():
    text = _decode("bidi_marks_and_embeddings.txt")

    assert _LRM in text and _RLM in text
    assert text.count(_RLE) == text.count(_PDF) == 1
    assert text.count(_RLI) + text.count(_FSI) == text.count(_PDI) == 2


# --------------------------------------------------------------------------
# The annotation contract is enforced, not merely present
# --------------------------------------------------------------------------


def _clone_corpus(work_tree) -> dict:
    for entry in ENTRIES:
        work_tree.write_bytes(f"preservation/{entry.name}", entry.read_bytes())
    return json.loads(
        (PRESERVATION_CORPUS / CORPUS_MANIFEST_NAME).read_text(encoding="utf-8")
    )


def test_dropping_an_annotation_breaks_the_corpus(work_tree):
    manifest = _clone_corpus(work_tree)
    victim = sorted(manifest)[0]
    del manifest[victim]
    work_tree.write_bytes(
        f"preservation/{CORPUS_MANIFEST_NAME}", json.dumps(manifest).encode()
    )

    with pytest.raises(ValueError, match=victim):
        load_corpus(work_tree.path("preservation"))


def test_dropping_a_file_breaks_the_corpus(work_tree):
    manifest = _clone_corpus(work_tree)
    work_tree.write_bytes(
        f"preservation/{CORPUS_MANIFEST_NAME}", json.dumps(manifest).encode()
    )
    victim = sorted(manifest)[0]
    work_tree.path(f"preservation/{victim}").unlink()

    with pytest.raises(ValueError, match=victim):
        load_corpus(work_tree.path("preservation"))


def test_the_corpus_lives_where_the_design_says_it_does():
    # design.md "File Structure Plan": tests/corpus/preservation.
    assert PRESERVATION_CORPUS.is_dir()
    assert PRESERVATION_CORPUS.name == "preservation"
    assert (PRESERVATION_CORPUS / CORPUS_MANIFEST_NAME).is_file()
    # Files only: a nested directory would be skipped by the loader and so
    # would never be annotated or asserted on.
    assert all(child.is_file() for child in PRESERVATION_CORPUS.iterdir())


def test_gitattributes_pins_the_corpus_against_line_ending_translation():
    # Without this the CRLF entry is rewritten to LF on checkout and every
    # byte-identity claim in the corpus becomes untestable.
    gitattributes = Path(__file__).resolve().parents[1] / ".gitattributes"

    assert "tests/corpus/** -text" in gitattributes.read_text(encoding="utf-8")
