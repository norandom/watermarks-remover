"""Guards for the carrier corpus (tasks.md 1.4, Requirement 11.4).

The corpus in ``tests/corpus/carriers/`` is the reference set of files that
must be **cleaned**. Task 4.3 will run the cleaner over it; this module owns
the fixtures themselves and, more importantly, the annotations that say what
"cleaned" means for each one.

That last part is what separates this corpus from the preservation corpus of
tasks.md 1.3. There, every entry behaves identically: byte-identical output,
full stop. Here the entries deliberately do **not** agree with each other:

* Some are not cleaned at all under the default policy. Private-use
  codepoints are preserved by default (Requirement 3.5) and a byte-order mark
  at offset zero is preserved by default (Requirement 6.5); an entry built on
  either one is contraband only under the flag that opts into removing it.
* Some legitimately keep part of what they carry. A smuggled selector run on
  legal ideographic bases retains its **first** selector under the
  selector-run rule (design.md, ``classify.py`` Implementation Notes), a
  conforming subdivision flag keeps its tag characters, and a Trojan Source
  file keeps its directional marks.

So the observable of tasks.md 1.4 is not "every entry names a policy" — it is
that the naming is **consistent with the rules**, and no entry claims a
removal that its own policy preserves. That is enforced here by a model of the
documented classification rules (``_contraband_positions`` and
``_dropped_keys``) rather than by careful authoring: every entry's declared
removals and declared residue are asserted to be exactly what the rules
produce for that entry's bytes under that entry's policy.

Every non-ASCII character in this module is written as an escape. A literal
invisible carrier in a test source is a fixture that silently proves nothing —
this repository's own hook would rewrite it — so the corpus *data* files are
the only place real carrier bytes live, pinned by ``tests/corpus/** -text`` in
``.gitattributes`` and by ``exclude: ^tests/corpus/`` on both hook ids.
"""

from __future__ import annotations

import json
import re
import unicodedata
from fnmatch import fnmatch
from pathlib import Path

import pytest
from conftest import CARRIERS_CORPUS, CORPUS_MANIFEST_NAME, load_corpus

REPO_ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# Named carriers, so the fixtures below read as intent rather than as escapes
# --------------------------------------------------------------------------

_ZWSP = "\u200b"
_ZWNJ = "\u200c"
_ZWJ = "\u200d"
_LRM = "\u200e"
_RLM = "\u200f"
_LRO = "\u202d"
_RLO = "\u202e"
_RLI = "\u2067"
_PDI = "\u2069"
_WJ = "\u2060"
_VS1 = "\ufe00"
_VS2 = "\ufe01"
_VS3 = "\ufe02"
_VS15 = "\ufe0e"
_VS16 = "\ufe0f"
_KEYCAP = "\u20e3"
_IVS17 = "\U000e0100"
_TAG_SPACE = "\U000e0020"
_TAG_CANCEL = "\U000e007f"
_BLACK_FLAG = "\U0001f3f4"
_BOM = "\ufeff"


def _tag(letters: str) -> str:
    """Encode ASCII characters as their Unicode Tag-block counterparts."""
    return "".join(chr(0xE0000 + ord(ch)) for ch in letters)


def _ivs(offset: int) -> str:
    """The *offset*-th Ideographic Variation Selector, ``U+E0100`` upwards."""
    return chr(0xE0100 + offset)


# --------------------------------------------------------------------------
# The authored bytes
# --------------------------------------------------------------------------

#: Every corpus file, keyed by name, with its exact contents. This is the
#: authoritative record: a fixture an editor renormalised, or that this
#: repository's own hook stripped on the way into a commit, fails here rather
#: than quietly becoming a file with nothing left to remove.
EXPECTED_BYTES: dict[str, bytes] = {
    # -- zero width --------------------------------------------------------
    "zero_width_binary_payload.txt": (
        "# A zero-width binary payload smuggled into ordinary prose\n"
        f"Ship it on Friday.{_ZWSP}{_ZWNJ}{_ZWSP}{_ZWSP}{_ZWNJ}{_ZWNJ}{_ZWSP}{_ZWNJ}\n"
        f"A joiner between Latin letters is not glue: hid{_ZWJ}den.\n"
        f"Word joiners run in threes:{_WJ}{_WJ}{_WJ}\n"
        f"An interior byte-order mark is a carrier:{_BOM}done.\n"
    ).encode(),
    "joiners_between_ascii_digits.txt": (
        "# Joiners smuggled between ASCII digits, beside genuine keycaps\n"
        f"account 4{_ZWJ}2{_ZWJ}0{_ZWJ}0\n"
        f"invoice 1{_ZWNJ}2{_ZWNJ}3\n"
        f"genuine keycaps survive: 1{_VS16}{_KEYCAP} 7{_VS16}{_KEYCAP} "
        f"#{_VS16}{_KEYCAP}\n"
        f"a joiner after a keycap is still contraband: 1{_VS16}{_KEYCAP}{_ZWJ}2\n"
    ).encode(),
    # -- Unicode Tag block -------------------------------------------------
    "tag_block_bare_payload.txt": (
        "# Tag-block characters with no flag base anywhere in this file\n"
        f"Ordinary sentence.{_tag('hidden')}\n"
        f"Tag digits and a tag space carry bytes too:{_tag('42')}{_TAG_SPACE}\n"
        f"A lone cancel tag terminates nothing:{_TAG_CANCEL}\n"
    ).encode(),
    "tag_block_behind_flag.txt": (
        "# Tag smuggling behind a flag emoji\n"
        f"over-long payload: {_BLACK_FLAG}{_tag('gbsctgbsctxy')}{_TAG_CANCEL}\n"
        f"conforming flag, trailing payload: {_BLACK_FLAG}{_tag('gbsct')}"
        f"{_TAG_CANCEL}{_tag('hi')}\n"
        f"empty payload: {_BLACK_FLAG}{_TAG_CANCEL}\n"
    ).encode(),
    # -- variation selectors ----------------------------------------------
    "variation_selector_smuggling.txt": (
        "# Selector-run byte smuggling on legal ideographic bases\n"
        f"\u8fbb{_VS1}{_VS2}{_VS3}\n"
        f"\u845b{_ivs(0)}{_ivs(1)}\n"
        f"\u9038{_VS2}{_VS1}\n"
        f"\u82a6{_ivs(0)}{_ivs(1)}{_ivs(2)}{_ivs(3)}{_ivs(4)}{_ivs(5)}\n"
    ).encode(),
    "orphan_variation_selectors.txt": (
        "# Variation selectors with no base they can legally modify\n"
        f"after a latin letter: a{_VS16}\n"
        f"after a space: {_VS15}now\n"
        "at the start of a line:\n"
        f"{_VS16}leading\n"
        f"after a digit outside a keycap: 7{_VS16}\n"
        f"{_IVS17}and an ideographic selector with nothing before it\n"
    ).encode(),
    # -- bidi --------------------------------------------------------------
    "bidi_override_trojan_source.txt": (
        "# Trojan Source: the overrides are contraband, the marks are not\n"
        f'if (level != "admin") {{ // {_RLO}{{ return; {_LRO}\n'
        f"left-to-right mark {_LRM} and right-to-left mark {_RLM} stay\n"
        f"a balanced isolate: {_RLI}\u0639\u0631\u0628\u064a{_PDI} done\n"
    ).encode(),
    # -- private use -------------------------------------------------------
    "private_use_floating.txt": (
        "# Free-floating private-use codepoints, with no icon-font context\n"
        "The build tag is \ue000\ue001 and the marker is \uf8ff.\n"
        "Supplementary planes carry payload too: \U000f0000 \U0010fffd\n"
    ).encode(),
    # -- byte-order mark ---------------------------------------------------
    "bom_interior_smuggling.csv": (
        f"{_BOM}id,name,note\r\n"
        f"1,Ada,{_BOM}a mark opening a field\r\n"
        f"2,Grace,sec{_BOM}ond\r\n"
        "3,Zo\u00e9,third\r\n"
    ).encode(),
    "bom_signature_only.txt": (
        f"{_BOM}A plain text file whose only invisible character is the leading mark.\n"
        "Nothing else here is a carrier, so the default policy leaves it alone.\n"
    ).encode(),
    # -- provenance frontmatter keys ---------------------------------------
    "frontmatter_provenance_keys.md": (
        "---\n"
        "title: Comparing Claude and Gemini output\n"
        "generator:\n"
        "  name: Claude Opus 4.1\n"
        "  vendor: Anthropic\n"
        "created_with:\n"
        "  - claude-code\n"
        "  - wm-hook\n"
        "model: linear\n"
        "date: 2026-03-14\n"
        "---\n"
        "\n"
        "# Comparing Claude and Gemini output\n"
        "\n"
        "The body carries no invisible characters and must survive untouched.\n"
    ).encode(),
    "frontmatter_keys_concealed.md": (
        f"{_BOM}---\n"
        "title: What Claude changed in this release\n"
        f"gene{_ZWSP}rator: Claude Opus 4.1\n"
        f"{_ZWNJ}ai-generated: true\n"
        "model: claude-opus-4\n"
        "tags:\n"
        "  - release\n"
        "  - security\n"
        "---\n"
        "\n"
        "# Release notes\n"
        "\n"
        "The body is ordinary prose.\n"
    ).encode(),
}

# --------------------------------------------------------------------------
# Annotation contract
# --------------------------------------------------------------------------

#: Every entry must carry all of these. ``policy`` plus ``cleaned_under_default``
#: are the expected-policy annotation tasks.md 1.4 requires; the two
#: ``expected_residue_*`` keys plus ``residue_rule`` are the expected-residue
#: annotation. Both are required on every entry, including the entries whose
#: residue is empty — an absent key and a declared-empty one are different
#: claims.
REQUIRED_ANNOTATIONS = (
    "summary",
    "carrier_class",
    "rule",
    "removed_by",
    "implemented_by",
    "policy",
    "cleaned_under_default",
    "expected_removed_codepoints",
    "expected_removed_keys",
    "expected_residue_codepoints",
    "expected_residue_keys",
    "residue_protected_by",
    "residue_rule",
    "encoding",
    "line_endings",
    "trailing_newline",
)

#: The carrier classes tasks.md 1.4 and design.md "Carrier Corpus" enumerate.
#: A class with no entry is a hole in Requirement 11.4's coverage.
REQUIRED_CARRIER_CLASSES = frozenset(
    {
        "zero_width",
        "tag_block",
        "variation_selector",
        "bidi_override",
        "private_use",
        "byte_order_mark",
        "provenance_key",
    }
)

#: Criteria that mandate a removal somewhere in this corpus.
REQUIRED_REMOVAL_CRITERIA = frozenset(
    {
        "2.1",  # zero-width carriers
        "2.2",  # tag characters outside a complete subdivision flag
        "2.3",  # selectors with no base they can legally modify
        "2.4",  # bidi overrides, unconditionally
        "2.5",  # the Cf catch-all
        "2.6",  # whole runs, in one pass
        "5.1",  # provenance keys with their nested blocks
        "5.3",  # an ambiguous key corroborated by its value
        "5.6",  # provenance hidden behind a mark or an invisible character
        "7.3",  # one class concealing another, removed together
        "9.1",  # a transformation disabled independently of the others
        "9.2",  # a disabled transformation changes nothing
    }
)

#: Criteria that protect the residue this corpus legitimately retains. Every
#: one of these is a rule an over-eager cleaner would violate.
REQUIRED_RESIDUE_CRITERIA = frozenset(
    {
        "2.2",  # a conforming subdivision-flag payload survives
        "2.3",  # the first selector after a legal base survives
        "3.2",  # a presentation selector in a genuine keycap sequence
        "3.7",  # directional marks and a balanced isolate
        "5.2",  # a vendor name in a value is not a provenance key
        "5.3",  # an uncorroborated ambiguous key survives
        "6.5",  # a byte-order mark at offset zero
    }
)

#: tasks.md implementation tasks an entry may name.
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

# Loaded at import: a missing corpus, an unannotated file or an annotation
# without a file must break collection rather than quietly shrink this module.
ENTRIES = load_corpus(CARRIERS_CORPUS)
BY_NAME = {entry.name: entry for entry in ENTRIES}
NAMES = tuple(BY_NAME)


# --------------------------------------------------------------------------
# A model of the documented classification rules
#
# This is the machinery that makes the observable mechanical. It is not the
# Cleaner — it is a restatement of the rules Requirements 2 and 3 and the
# design's classifier notes already fix, applied to a fixture's actual bytes
# under a fixture's annotated policy. Its only job is to decide, per position,
# preserved or contraband, so that an annotation can be checked against it
# instead of against the author's intentions.
# --------------------------------------------------------------------------

#: Scripts that use U+200B as their word or line-break separator (Req 3.4).
_ZWSP_SCRIPT_RANGES = (
    ("\u0e01", "\u0e5b"),  # Thai
    ("\u0e80", "\u0edf"),  # Lao
    ("\u1780", "\u17ff"),  # Khmer
    ("\u1000", "\u109f"),  # Myanmar
)

#: Scripts in which a joiner is orthographic (Requirement 3.3).
_JOINING_SCRIPT_RANGES = (
    ("\u0600", "\u06ff"),  # Arabic
    ("\u0750", "\u077f"),  # Arabic Supplement
    ("\u0870", "\u08ff"),  # Arabic Extended-A/B
    ("\u0900", "\u097f"),  # Devanagari
    ("\ufb50", "\ufdff"),  # Arabic Presentation Forms-A
    ("\ufe70", "\ufefc"),  # Arabic Presentation Forms-B, short of U+FEFF
)

#: Preserved by default, removed only under ``strip_bidi`` (Requirement 3.7).
#: The overrides U+202D and U+202E are deliberately absent: Requirement 2.4
#: removes them whatever the policy says.
_BIDI_PRESERVED_BY_DEFAULT = "\u200e\u200f\u202a\u202b\u202c\u2066\u2067\u2068\u2069"

#: The five bases design.md widens ``_is_emoji_base`` to include.
_WIDENED_EMOJI_BASES = "\u2139\u203c\u2049\u2934\u2935"

#: Bases that count only inside a genuine keycap sequence (design.md).
_KEYCAP_BASES = "0123456789#*"


def _in_ranges(ch: str, ranges: tuple[tuple[str, str], ...]) -> bool:
    return any(low <= ch <= high for low, high in ranges)


def _is_variation_selector(ch: str) -> bool:
    return "\ufe00" <= ch <= "\ufe0f" or "\U000e0100" <= ch <= "\U000e01ef"


def _is_tag_character(ch: str) -> bool:
    return "\U000e0000" <= ch <= "\U000e007f"


def _is_cjk_ideograph(ch: str) -> bool:
    return (
        "\u3400" <= ch <= "\u9fff"
        or "\uf900" <= ch <= "\ufaff"
        or "\U00020000" <= ch <= "\U0003ffff"
    )


def _is_carrier_class(ch: str) -> bool:
    """True for anything invisible, private-use or a space homoglyph.

    The same set the preservation corpus declares against, so the two corpora
    account for exactly the same population of characters.
    """
    if _is_variation_selector(ch):
        return True
    category = unicodedata.category(ch)
    if category in ("Cf", "Co"):
        return True
    return category == "Zs" and ch != " "


def _previous_base_index(text: str, index: int) -> int | None:
    """Index of the last non-carrier character before *index* (Req 3.6)."""
    for candidate in range(index - 1, -1, -1):
        if not _is_carrier_class(text[candidate]):
            return candidate
    return None


def _next_base_index(text: str, index: int) -> int | None:
    for candidate in range(index + 1, len(text)):
        if not _is_carrier_class(text[candidate]):
            return candidate
    return None


def _starts_keycap(text: str, index: int) -> bool:
    """True when *index* opens ``base [VS16] U+20E3`` — a genuine keycap."""
    tail = text[index + 1 : index + 3]
    return tail.startswith(_KEYCAP) or tail.startswith(_VS16 + _KEYCAP)


def _is_emoji_base(text: str, index: int | None) -> bool:
    if index is None:
        return False
    ch = text[index]
    if ch in _WIDENED_EMOJI_BASES:
        return True
    if ch in _KEYCAP_BASES:
        # Narrowed: a digit, hash or asterisk is a base only in a keycap.
        return _starts_keycap(text, index)
    return unicodedata.category(ch) in ("So", "Sk")


def _flag_sequence_indices(text: str) -> frozenset[int]:
    """Indices of tag characters inside a *conforming* subdivision flag.

    Requirement 2.2 and design.md: ``U+1F3F4`` followed by two to six tag
    letters from the ISO 3166-2 alphabet and terminated by ``U+E007F``.
    Anything longer, shorter or drawn from outside that alphabet is
    contraband, and so is a tag character with no flag base at all.
    """
    kept: set[int] = set()
    index = 0
    while index < len(text):
        if text[index] == _BLACK_FLAG:
            end = index + 1
            while end < len(text) and "\U000e0061" <= text[end] <= "\U000e007a":
                end += 1
            payload = end - (index + 1)
            if 2 <= payload <= 6 and end < len(text) and text[end] == _TAG_CANCEL:
                kept.update(range(index + 1, end + 1))
                index = end + 1
                continue
        index += 1
    return frozenset(kept)


def _selector_run_starts(text: str) -> frozenset[int]:
    """Indices at which a run of variation selectors begins."""
    return frozenset(
        index
        for index, ch in enumerate(text)
        if _is_variation_selector(ch)
        and (index == 0 or not _is_variation_selector(text[index - 1]))
    )


def _selector_is_preserved(text: str, index: int) -> bool:
    """The selector-run rule (design.md, ``classify.py`` Implementation Notes).

    A *single* selector after a base it can legally modify is preserved; every
    subsequent selector in the same run is contraband. That is what separates
    ideographic variation from byte smuggling on the very same bases.
    """
    start = index
    while start > 0 and _is_variation_selector(text[start - 1]):
        start -= 1
    if index != start or start == 0:
        return False
    base_index = start - 1
    if _is_cjk_ideograph(text[base_index]):
        return True
    return _is_emoji_base(text, base_index)


def _is_preserved(text: str, index: int, policy: dict) -> bool:
    """Whether the carrier at *index* survives cleaning under *policy*."""
    ch = text[index]

    if ch == _BOM:
        # Position, not format: offset zero is a signature, the rest are
        # carriers (design.md, the byte-order-mark rule; Req 2.1 and 6.5).
        return index == 0 and not policy.get("strip_bom", False)
    if ch in (_LRO, _RLO):
        return False  # Requirement 2.4, whatever the policy says
    if unicodedata.category(ch) == "Co":
        return not policy.get("strip_private_use", False)  # Requirement 3.5
    if _is_tag_character(ch):
        return index in _flag_sequence_indices(text)  # Requirement 2.2
    if _is_variation_selector(ch):
        return _selector_is_preserved(text, index)  # Requirement 2.3
    if ch == _ZWJ:
        if policy.get("strip_emoji_glue", False):
            return False
        previous = _previous_base_index(text, index)
        if previous is not None and _in_ranges(text[previous], _JOINING_SCRIPT_RANGES):
            return True  # Requirement 3.3
        return _is_emoji_base(text, previous) and _is_emoji_base(
            text, _next_base_index(text, index)
        )  # Requirement 3.1
    if ch == _ZWNJ:
        neighbours = (_previous_base_index(text, index), _next_base_index(text, index))
        return any(
            side is not None and _in_ranges(text[side], _JOINING_SCRIPT_RANGES)
            for side in neighbours
        )  # Requirement 3.3
    if ch == _ZWSP:
        neighbours = (_previous_base_index(text, index), _next_base_index(text, index))
        return all(
            side is not None and _in_ranges(text[side], _ZWSP_SCRIPT_RANGES)
            for side in neighbours
        )  # Requirement 3.4
    if ch in _BIDI_PRESERVED_BY_DEFAULT:
        return not policy.get("strip_bidi", False)  # Requirement 3.7
    if unicodedata.category(ch) == "Cf":
        return False  # Requirement 2.5, the catch-all
    raise ValueError(
        f"the rule model has no branch for U+{ord(ch):04X}; a space homoglyph "
        "is a REPLACE, not a removal, and has no place in this corpus"
    )


def _carrier_positions(text: str) -> tuple[int, ...]:
    return tuple(i for i, ch in enumerate(text) if _is_carrier_class(ch))


def _contraband_positions(text: str, policy: dict) -> frozenset[int]:
    return frozenset(
        i for i in _carrier_positions(text) if not _is_preserved(text, i, policy)
    )


def _preserved_positions(text: str, policy: dict) -> frozenset[int]:
    return frozenset(
        i for i in _carrier_positions(text) if _is_preserved(text, i, policy)
    )


def _carrier_kind(ch: str) -> str:
    """Which documented carrier class *ch* belongs to.

    Ordered, because the classes overlap in Unicode terms: tag characters,
    the byte-order mark and the bidi overrides are all category ``Cf``, so the
    specific tests have to run before the zero-width catch-all.
    """
    if _is_tag_character(ch):
        return "tag_block"
    if _is_variation_selector(ch):
        return "variation_selector"
    if ch in (_LRO, _RLO):
        return "bidi_override"
    if ch == _BOM:
        return "byte_order_mark"
    if unicodedata.category(ch) == "Co":
        return "private_use"
    return "zero_width"


def _dominant_carrier_class(text: str, policy: dict) -> str | None:
    """The class an entry's contraband actually belongs to.

    A dropped provenance key outranks any codepoint: an entry that loses a
    frontmatter key is a provenance entry whatever invisible characters were
    used to conceal it. Otherwise the class holding a strict majority of the
    contraband positions wins, and an entry with no clear winner returns
    ``None`` so the caller fails loudly rather than picking one.
    """
    if _dropped_keys(text, policy):
        return "provenance_key"
    tally: dict[str, int] = {}
    for index in _contraband_positions(text, policy):
        kind = _carrier_kind(text[index])
        tally[kind] = tally.get(kind, 0) + 1
    if not tally:
        return None
    ranked = sorted(tally.items(), key=lambda item: -item[1])
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return None
    return ranked[0][0]


# --------------------------------------------------------------------------
# A model of the provenance key policy
# --------------------------------------------------------------------------

#: Names that always indicate provenance, from the vendored vocabulary that
#: design.md splits in task 2.8.
_UNCONDITIONAL_PROVENANCE_KEYS = frozenset(
    {
        "generator",
        "ai_generated",
        "ai-generated",
        "claude",
        "anthropic",
        "openai",
        "gemini",
        "synthid",
        "c2pa",
        "content_credentials",
        "contentcredentials",
        "provenance",
        "digital_source_type",
        "digitalsourcetype",
        "created_with",
        "createdwith",
    }
)

#: Common domain terms that need a corroborating value (Requirement 5.3).
_AMBIGUOUS_PROVENANCE_KEYS = frozenset({"ai", "model", "llm"})

_VALUE_CORROBORATION = re.compile(
    r"claude|anthropic|openai|gemini|gpt|synthid|c2pa|ai[-_ ]?generated|"
    r"generator|provenance|content.?credential|digital.?source",
    re.I,
)


def _strip_carriers(text: str) -> str:
    return "".join(ch for ch in text if not _is_carrier_class(ch))


def _frontmatter_pairs(text: str) -> tuple[tuple[str, str], ...]:
    """Top-level ``key: value`` pairs of the frontmatter block, if there is one.

    Carriers are stripped before the line is read, which is what lets a key
    concealed behind a byte-order mark or an invisible character be found on
    the first pass (Requirement 5.6, design.md "Preamble" tolerance).
    """
    lines = [line.rstrip("\r") for line in text.split("\n")]
    if not lines or _strip_carriers(lines[0]).strip() != "---":
        return ()
    pairs: list[tuple[str, str]] = []
    for line in lines[1:]:
        bare = _strip_carriers(line)
        if bare.strip() == "---":
            break
        if not bare or bare[0].isspace() or ":" not in bare:
            continue  # continuation, list item or blank line
        key, _, value = bare.partition(":")
        pairs.append((key.strip(), value.strip()))
    return tuple(pairs)


def _dropped_keys(text: str, policy: dict) -> frozenset[str]:
    if not policy.get("drop_frontmatter_keys", True):
        return frozenset()
    dropped = set()
    for key, value in _frontmatter_pairs(text):
        lowered = key.lower()
        if lowered in _UNCONDITIONAL_PROVENANCE_KEYS:
            dropped.add(key)  # Requirement 5.1
        elif lowered in _AMBIGUOUS_PROVENANCE_KEYS and _VALUE_CORROBORATION.search(
            value
        ):
            dropped.add(key)  # Requirement 5.3
    return frozenset(dropped)


def _kept_keys(text: str, policy: dict) -> frozenset[str]:
    return frozenset(key for key, _ in _frontmatter_pairs(text)) - _dropped_keys(
        text, policy
    )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _decode(name: str) -> str:
    """Decode an entry the way the Cleaner will (Requirement 6.6)."""
    return BY_NAME[name].read_bytes().decode("utf-8", "surrogateescape")


def _codepoint(ch: str) -> str:
    return f"U+{ord(ch):04X}"


def _codepoints_at(text: str, positions: frozenset[int]) -> list[str]:
    """The distinct codepoints occupying *positions*, ordered by codepoint.

    Set-valued on purpose: the same codepoint may be contraband at one
    position and legitimate at another — a tag letter inside a conforming flag
    and again in the payload smuggled after it, a byte-order mark at offset
    zero and again mid-line — so a codepoint can appear in both an entry's
    removal list and its residue list. That is the annotation saying "by
    position, not by codepoint".
    """
    return [_codepoint(ch) for ch in sorted({text[i] for i in positions}, key=ord)]


def _policy_of(name: str) -> dict:
    return dict(BY_NAME[name].annotation("policy"))


def _entry_ids() -> list[str]:
    return sorted(EXPECTED_BYTES)


# --------------------------------------------------------------------------
# Enumeration and annotations
# --------------------------------------------------------------------------


def test_corpus_holds_exactly_the_authored_entries():
    # Not a subset check. An entry that appeared without a recorded literal
    # would be enumerated by the loader and byte-checked by nothing.
    assert set(NAMES) == set(EXPECTED_BYTES)


@pytest.mark.parametrize("name", _entry_ids())
def test_entry_bytes_match_the_recorded_literal(name):
    assert BY_NAME[name].read_bytes() == EXPECTED_BYTES[name]


@pytest.mark.parametrize("name", _entry_ids())
def test_entry_is_not_a_placeholder(name):
    data = BY_NAME[name].read_bytes()

    assert len(data) >= 40
    assert data.strip()


@pytest.mark.parametrize("name", _entry_ids())
def test_entry_carries_every_required_annotation(name):
    entry = BY_NAME[name]

    for key in REQUIRED_ANNOTATIONS:
        entry.annotation(key)  # raises, naming the entry, when absent
    assert entry.annotation("summary").strip()
    assert entry.annotation("rule").strip()
    assert entry.annotation("residue_rule").strip()


@pytest.mark.parametrize("name", _entry_ids())
def test_entry_names_the_criteria_that_mandate_its_removal(name):
    removed_by = BY_NAME[name].annotation("removed_by")

    assert isinstance(removed_by, list) and removed_by
    for criterion in removed_by:
        requirement, _, item = criterion.partition(".")
        assert requirement.isdigit() and item.isdigit(), criterion
        assert 1 <= int(requirement) <= 11, criterion


@pytest.mark.parametrize("name", _entry_ids())
def test_entry_names_the_task_that_implements_its_removal(name):
    implemented_by = BY_NAME[name].annotation("implemented_by")

    assert isinstance(implemented_by, list) and implemented_by
    assert set(implemented_by) <= IMPLEMENTING_TASKS


@pytest.mark.parametrize("name", _entry_ids())
def test_entry_names_a_documented_carrier_class(name):
    assert BY_NAME[name].annotation("carrier_class") in REQUIRED_CARRIER_CLASSES


@pytest.mark.parametrize("name", _entry_ids())
def test_carrier_class_matches_what_the_entry_actually_carries(name):
    text = _decode(name)

    # Naming a class the file does not hold would let an entry be filed under
    # a class it never exercises while the coverage test above still passed on
    # the strength of some other entry.
    assert BY_NAME[name].annotation("carrier_class") == _dominant_carrier_class(
        text, _policy_of(name)
    )


def test_corpus_covers_every_carrier_class_requirement_11_4_names():
    covered = {entry.annotation("carrier_class") for entry in ENTRIES}

    assert REQUIRED_CARRIER_CLASSES <= covered


def test_corpus_covers_every_removal_criterion_it_is_answerable_for():
    cited = {c for entry in ENTRIES for c in entry.annotation("removed_by")}

    assert REQUIRED_REMOVAL_CRITERIA <= cited


def test_corpus_covers_every_residue_criterion_it_is_answerable_for():
    cited = {c for entry in ENTRIES for c in entry.annotation("residue_protected_by")}

    assert REQUIRED_RESIDUE_CRITERIA <= cited


@pytest.mark.parametrize("name", _entry_ids())
def test_policy_annotation_names_only_documented_flags(name, policy_variant):
    overrides = BY_NAME[name].annotation("policy")

    assert isinstance(overrides, dict)
    assert set(overrides) <= POLICY_FLAGS
    # Round-trips through the harness factory, which is what task 4.3 will
    # splat into the real CleanPolicy.
    policy_variant(**overrides)


# --------------------------------------------------------------------------
# The manifest describes the actual bytes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", _entry_ids())
def test_declared_encoding_matches_the_bytes(name):
    data = BY_NAME[name].read_bytes()
    encoding = BY_NAME[name].annotation("encoding")

    if encoding == "utf-8-sig":
        assert data.startswith(b"\xef\xbb\xbf")
    else:
        assert encoding == "utf-8"
        assert not data.startswith(b"\xef\xbb\xbf")
    assert data.decode("utf-8")


@pytest.mark.parametrize("name", _entry_ids())
def test_declared_line_endings_match_the_bytes(name):
    data = BY_NAME[name].read_bytes()
    line_endings = BY_NAME[name].annotation("line_endings")

    if line_endings == "CRLF":
        assert b"\r\n" in data
        assert b"\r" not in data.replace(b"\r\n", b"")
        assert b"\n" not in data.replace(b"\r\n", b"")
    else:
        assert line_endings == "LF"
        assert b"\n" in data
        assert b"\r" not in data


@pytest.mark.parametrize("name", _entry_ids())
def test_declared_trailing_newline_matches_the_bytes(name):
    data = BY_NAME[name].read_bytes()

    assert BY_NAME[name].annotation("trailing_newline") is data.endswith(b"\n")


# --------------------------------------------------------------------------
# The observable of tasks.md 1.4
#
# Every entry carries an expected-policy and an expected-residue annotation,
# and no entry asserts removal under a policy that preserves it.
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", _entry_ids())
def test_every_entry_carries_an_expected_policy_annotation(name):
    entry = BY_NAME[name]

    assert isinstance(entry.annotation("policy"), dict)
    assert isinstance(entry.annotation("cleaned_under_default"), bool)


@pytest.mark.parametrize("name", _entry_ids())
def test_every_entry_carries_an_expected_residue_annotation(name):
    entry = BY_NAME[name]

    # Present on every entry, including the ones that keep nothing: "this
    # entry retains no residue" is a claim, and an absent key is not.
    assert isinstance(entry.annotation("expected_residue_codepoints"), list)
    assert isinstance(entry.annotation("expected_residue_keys"), list)
    assert entry.annotation("residue_rule").strip()


@pytest.mark.parametrize("name", _entry_ids())
def test_every_entry_actually_removes_something(name):
    entry = BY_NAME[name]

    # A "carrier" entry that loses nothing under its own policy would be a
    # preservation entry filed in the wrong corpus.
    assert entry.annotation("expected_removed_codepoints") or entry.annotation(
        "expected_removed_keys"
    )


@pytest.mark.parametrize("name", _entry_ids())
def test_no_entry_asserts_removal_of_a_codepoint_its_policy_preserves(name):
    text = _decode(name)
    policy = _policy_of(name)
    declared = set(BY_NAME[name].annotation("expected_removed_codepoints"))

    contraband = set(_codepoints_at(text, _contraband_positions(text, policy)))
    overclaimed = sorted(declared - contraband)

    # The observable of tasks.md 1.4, stated directly: a codepoint may only be
    # claimed as removed if at least one of its occurrences is contraband
    # under this entry's own policy.
    assert not overclaimed, (
        f"{name} claims removal of {overclaimed}, but the policy it names "
        f"({policy or 'the default'}) preserves every occurrence of them"
    )


@pytest.mark.parametrize("name", _entry_ids())
def test_no_entry_asserts_removal_of_a_key_its_policy_preserves(name):
    text = _decode(name)
    policy = _policy_of(name)
    declared = set(BY_NAME[name].annotation("expected_removed_keys"))

    overclaimed = sorted(declared - _dropped_keys(text, policy))

    assert not overclaimed, (
        f"{name} claims removal of frontmatter key(s) {overclaimed} that the "
        f"key policy under {policy or 'the default'} keeps"
    )


@pytest.mark.parametrize("name", _entry_ids())
def test_declared_removed_codepoints_are_exactly_the_contraband_ones(name):
    text = _decode(name)

    assert BY_NAME[name].annotation("expected_removed_codepoints") == _codepoints_at(
        text, _contraband_positions(text, _policy_of(name))
    )


@pytest.mark.parametrize("name", _entry_ids())
def test_declared_residue_codepoints_are_exactly_the_preserved_ones(name):
    text = _decode(name)

    assert BY_NAME[name].annotation("expected_residue_codepoints") == _codepoints_at(
        text, _preserved_positions(text, _policy_of(name))
    )


@pytest.mark.parametrize("name", _entry_ids())
def test_declared_removed_keys_are_exactly_the_provenance_ones(name):
    text = _decode(name)

    assert BY_NAME[name].annotation("expected_removed_keys") == sorted(
        _dropped_keys(text, _policy_of(name))
    )


@pytest.mark.parametrize("name", _entry_ids())
def test_declared_residue_keys_are_exactly_the_surviving_ones(name):
    text = _decode(name)

    assert BY_NAME[name].annotation("expected_residue_keys") == sorted(
        _kept_keys(text, _policy_of(name))
    )


@pytest.mark.parametrize("name", _entry_ids())
def test_every_carrier_in_an_entry_is_either_removed_or_declared_residue(name):
    text = _decode(name)
    entry = BY_NAME[name]

    declared = set(entry.annotation("expected_removed_codepoints")) | set(
        entry.annotation("expected_residue_codepoints")
    )
    present = {_codepoint(text[i]) for i in _carrier_positions(text)}

    # No third category. Every invisible, private-use or homoglyph character
    # in the file is accounted for by one of the two claims.
    assert declared == present


@pytest.mark.parametrize("name", _entry_ids())
def test_residue_is_justified_exactly_when_it_exists(name):
    entry = BY_NAME[name]

    has_residue = bool(
        entry.annotation("expected_residue_codepoints")
        or entry.annotation("expected_residue_keys")
    )
    protected_by = entry.annotation("residue_protected_by")

    assert isinstance(protected_by, list)
    assert bool(protected_by) is has_residue
    for criterion in protected_by:
        requirement, _, item = criterion.partition(".")
        assert requirement.isdigit() and item.isdigit(), criterion


# --------------------------------------------------------------------------
# Policy variance: which entries the default policy leaves alone, and why
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", _entry_ids())
def test_cleaned_under_default_matches_what_the_default_policy_does(name):
    text = _decode(name)

    touched = bool(_contraband_positions(text, {}) or _dropped_keys(text, {}))

    assert BY_NAME[name].annotation("cleaned_under_default") is touched


@pytest.mark.parametrize("name", _entry_ids())
def test_an_entry_the_default_policy_preserves_names_the_flag_that_cleans_it(name):
    entry = BY_NAME[name]

    if entry.annotation("cleaned_under_default"):
        return
    # Requirement 3.5 and 6.5 flip two defaults towards preservation. An entry
    # built on either one is a carrier only under an explicit opt-in, and the
    # annotation has to say which one.
    assert entry.annotation("policy"), (
        f"{name} is not cleaned under the default policy, so it must name the "
        "flag that does clean it"
    )


@pytest.mark.parametrize("name", _entry_ids())
def test_every_policy_override_an_entry_names_is_load_bearing(name):
    text = _decode(name)
    policy = _policy_of(name)
    baseline = (_contraband_positions(text, policy), _dropped_keys(text, policy))

    for flag in policy:
        without = {k: v for k, v in policy.items() if k != flag}
        assert (
            _contraband_positions(text, without),
            _dropped_keys(text, without),
        ) != baseline, f"{name} names {flag!r} but the outcome is the same without it"


def test_the_corpus_contains_at_least_one_entry_of_each_policy_disposition():
    dispositions = {entry.annotation("cleaned_under_default") for entry in ENTRIES}

    # Both halves of the tension tasks.md 1.4 names must actually be present,
    # or the consistency machinery above would never be exercised.
    assert dispositions == {True, False}


def test_the_corpus_contains_an_entry_that_legitimately_retains_residue():
    with_residue = [
        entry.name
        for entry in ENTRIES
        if entry.annotation("expected_residue_codepoints")
        or entry.annotation("expected_residue_keys")
    ]

    assert len(with_residue) >= 2


# --------------------------------------------------------------------------
# Preconditions the rule model relies on
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", _entry_ids())
def test_no_entry_holds_a_space_homoglyph(name):
    text = _decode(name)

    # A space homoglyph is normalised to U+0020, not removed. It is neither a
    # removal nor residue, so admitting one would break the two-way partition
    # every annotation above depends on.
    homoglyphs = [
        _codepoint(ch)
        for ch in text
        if unicodedata.category(ch) == "Zs" and ch != " "
    ]
    assert not homoglyphs


@pytest.mark.parametrize("name", _entry_ids())
def test_directional_embeddings_and_isolates_are_balanced(name):
    text = _decode(name)

    # The model preserves an embedding or isolate because Requirement 3.7
    # preserves *correctly paired* ones. An unbalanced fixture would make that
    # branch claim more than the requirement does.
    assert text.count("\u202a") + text.count("\u202b") == text.count("\u202c")
    opened = text.count("\u2066") + text.count("\u2067") + text.count("\u2068")
    assert opened == text.count("\u2069")


# --------------------------------------------------------------------------
# Per-entry content: the techniques tasks.md 1.4 enumerates
# --------------------------------------------------------------------------


def test_zero_width_entry_holds_a_payload_run_of_every_zero_width_carrier():
    text = _decode("zero_width_binary_payload.txt")

    # Requirement 2.1 names five; all five are here, none in a context that
    # would protect it.
    for carrier in (_ZWSP, _ZWNJ, _ZWJ, _WJ, _BOM):
        assert carrier in text
    # Requirement 2.6: a consecutive run, not one isolated character.
    assert max(len(run) for run in re.findall(f"[{_ZWSP}{_ZWNJ}]+", text)) >= 8
    assert _WJ * 3 in text
    # The one byte-order mark is interior, so no part of this entry survives.
    assert text.index(_BOM) > 0


def test_digit_joiner_entry_separates_ascii_digits_and_keeps_real_keycaps():
    text = _decode("joiners_between_ascii_digits.txt")

    assert re.search(f"[0-9]{_ZWJ}[0-9]", text)
    assert re.search(f"[0-9]{_ZWNJ}[0-9]", text)
    # design.md narrows the base set so a digit is a base only in a genuine
    # keycap; those selectors are the residue (Requirement 3.2).
    for base in "17#":
        assert base + _VS16 + _KEYCAP in text
    assert _KEYCAP + _ZWJ in text


def test_bare_tag_entry_has_no_flag_base_at_all():
    text = _decode("tag_block_bare_payload.txt")

    assert _BLACK_FLAG not in text
    assert _tag("hidden") in text
    # Tag digits and a tag space, so the entry is not only the letter range.
    assert _tag("42") in text and _TAG_SPACE in text
    assert _TAG_CANCEL in text


def test_flag_entry_holds_a_conforming_sequence_and_three_smuggled_ones():
    text = _decode("tag_block_behind_flag.txt")

    # Conforming: two to six letters, terminated (Requirement 2.2).
    assert _BLACK_FLAG + _tag("gbsct") + _TAG_CANCEL in text
    # Over-long, trailing beyond the terminator, and empty — all contraband.
    assert _BLACK_FLAG + _tag("gbsctgbsctxy") + _TAG_CANCEL in text
    assert _TAG_CANCEL + _tag("hi") in text
    assert _BLACK_FLAG + _TAG_CANCEL in text
    # The same tag letters appear on both sides of the verdict, which is what
    # makes the annotation position-derived rather than codepoint-derived.
    residue = set(BY_NAME["tag_block_behind_flag.txt"].annotation(
        "expected_residue_codepoints"
    ))
    removed = set(BY_NAME["tag_block_behind_flag.txt"].annotation(
        "expected_removed_codepoints"
    ))
    assert residue & removed


def test_selector_entry_smuggles_runs_on_legal_ideographic_bases():
    text = _decode("variation_selector_smuggling.txt")
    runs = re.findall("[\ufe00-\ufe0f\U000e0100-\U000e01ef]+", text)

    assert len(runs) >= 4
    for run in runs:
        assert len(run) >= 2  # a run, not a single legal selector
    assert max(len(run) for run in runs) >= 6  # Requirement 2.6
    for index in _selector_run_starts(text):
        # Every run opens on a base that could legally carry one selector,
        # which is exactly what makes the rest of the run smuggling.
        assert _is_cjk_ideograph(text[index - 1])


def test_selector_entry_retains_the_first_selector_of_every_run():
    entry = BY_NAME["variation_selector_smuggling.txt"]
    text = _decode(entry.name)

    starts = _selector_run_starts(text)
    # The selector-run rule in the design's classifier notes, stated as an
    # expected residue rather than as a failure.
    assert _preserved_positions(text, {}) == frozenset(starts)
    assert entry.annotation("expected_residue_codepoints")


def test_orphan_selector_entry_has_no_legal_base_anywhere():
    text = _decode("orphan_variation_selectors.txt")
    positions = [i for i, ch in enumerate(text) if _is_variation_selector(ch)]

    assert len(positions) >= 4
    for index in positions:
        assert not _selector_is_preserved(text, index)
    # After a letter, after a space, at the start of a line, and after a digit
    # that is not opening a keycap.
    assert f"a{_VS16}\n" in text
    assert f" {_VS15}" in text
    assert f"\n{_VS16}" in text
    assert f"7{_VS16}\n" in text


def test_bidi_entry_holds_both_overrides_and_content_that_must_stay():
    text = _decode("bidi_override_trojan_source.txt")

    assert _RLO in text and _LRO in text  # Requirement 2.4
    assert _LRM in text and _RLM in text  # Requirement 3.7
    assert _RLI in text and _PDI in text


def test_private_use_entry_is_free_floating_across_all_three_areas():
    text = _decode("private_use_floating.txt")
    private_use = [ch for ch in text if unicodedata.category(ch) == "Co"]

    assert any("\ue000" <= ch <= "\uf8ff" for ch in private_use)
    assert any("\U000f0000" <= ch <= "\U000ffffd" for ch in private_use)
    assert any(ch >= "\U00100000" for ch in private_use)
    # Requirement 3.5: nothing here is contraband until the flag is set.
    assert not _contraband_positions(text, {})
    assert _policy_of("private_use_floating.txt") == {"strip_private_use": True}


def test_interior_bom_entry_keeps_its_signature_and_loses_the_rest():
    text = _decode("bom_interior_smuggling.csv")
    positions = [i for i, ch in enumerate(text) if ch == _BOM]

    assert positions[0] == 0 and len(positions) >= 3
    # One codepoint, two verdicts, decided by position (design.md's
    # byte-order-mark rule).
    assert _preserved_positions(text, {}) == frozenset({0})
    assert _contraband_positions(text, {}) == frozenset(positions[1:])
    # A signature is only meaningful over content that needs one.
    assert any(ord(ch) > 0x7F for ch in text[1:])


def test_leading_bom_entry_is_a_carrier_only_under_strip_bom():
    text = _decode("bom_signature_only.txt")

    assert text.startswith(_BOM) and _BOM not in text[1:]
    assert not _contraband_positions(text, {})
    assert _contraband_positions(text, {"strip_bom": True}) == frozenset({0})
    assert _policy_of("bom_signature_only.txt") == {"strip_bom": True}


def test_frontmatter_entry_drops_provenance_keys_and_keeps_the_rest():
    text = _decode("frontmatter_provenance_keys.md")
    pairs = dict(_frontmatter_pairs(text))

    # A nested block and a list block, both of which Requirement 5.1 takes
    # with their key.
    assert "generator:\n  name: Claude Opus 4.1\n  vendor: Anthropic\n" in text
    assert "created_with:\n  - claude-code\n  - wm-hook\n" in text
    # The corrections: a vendor named in a *value* keeps its key (5.2), and an
    # ambiguous name with an ordinary value keeps its key (5.3).
    assert "Claude" in pairs["title"] and "Gemini" in pairs["title"]
    assert pairs["model"] == "linear"
    assert not [i for i, ch in enumerate(text) if _is_carrier_class(ch)]


def test_concealed_frontmatter_entry_hides_its_keys_behind_invisibles():
    entry = BY_NAME["frontmatter_keys_concealed.md"]
    text = _decode(entry.name)

    # A byte-order mark before the opening delimiter and an invisible
    # character inside a key name: Requirement 5.6 and 7.3, found on pass one.
    assert text.startswith(_BOM + "---\n")
    assert f"gene{_ZWSP}rator:" in text
    assert f"\n{_ZWNJ}ai-generated:" in text
    assert "generator" in entry.annotation("expected_removed_keys")
    assert "ai-generated" in entry.annotation("expected_removed_keys")
    # The ambiguous key that its value does corroborate (Requirement 5.3).
    assert dict(_frontmatter_pairs(text))["model"] == "claude-opus-4"
    assert "model" in entry.annotation("expected_removed_keys")


# --------------------------------------------------------------------------
# The annotation contract is enforced, not merely present
# --------------------------------------------------------------------------


def _clone_corpus(work_tree) -> dict:
    for entry in ENTRIES:
        work_tree.write_bytes(f"carriers/{entry.name}", entry.read_bytes())
    return json.loads(
        (CARRIERS_CORPUS / CORPUS_MANIFEST_NAME).read_text(encoding="utf-8")
    )


def test_dropping_an_annotation_breaks_the_corpus(work_tree):
    manifest = _clone_corpus(work_tree)
    victim = sorted(manifest)[0]
    del manifest[victim]
    work_tree.write_bytes(
        f"carriers/{CORPUS_MANIFEST_NAME}", json.dumps(manifest).encode()
    )

    with pytest.raises(ValueError, match=victim):
        load_corpus(work_tree.path("carriers"))


def test_dropping_a_file_breaks_the_corpus(work_tree):
    manifest = _clone_corpus(work_tree)
    work_tree.write_bytes(
        f"carriers/{CORPUS_MANIFEST_NAME}", json.dumps(manifest).encode()
    )
    victim = sorted(manifest)[0]
    work_tree.path(f"carriers/{victim}").unlink()

    with pytest.raises(ValueError, match=victim):
        load_corpus(work_tree.path("carriers"))


def test_the_corpus_lives_where_the_design_says_it_does():
    # design.md "File Structure Plan": tests/corpus/carriers.
    assert CARRIERS_CORPUS.is_dir()
    assert CARRIERS_CORPUS.name == "carriers"
    assert (CARRIERS_CORPUS / CORPUS_MANIFEST_NAME).is_file()
    # Files only: a nested directory would be skipped by the loader and so
    # would never be annotated or asserted on.
    assert all(child.is_file() for child in CARRIERS_CORPUS.iterdir())


def test_gitattributes_pins_the_carrier_corpus_against_translation():
    # Without this, the CRLF entry is rewritten to LF on checkout and its
    # line-ending declaration becomes untestable.
    gitattributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    relative = CARRIERS_CORPUS.relative_to(REPO_ROOT).as_posix()

    assert "tests/corpus/** -text" in gitattributes
    assert fnmatch(f"{relative}/bom_interior_smuggling.csv", "tests/corpus/**")


def test_this_repositorys_own_hook_excludes_the_carrier_corpus():
    # These fixtures hold live payloads. Both hook ids must skip them, or the
    # autofix id rewrites the corpus and the check id reports it forever.
    manifest = (REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    ids = re.findall(r"^- id: (\S+)", manifest, re.M)
    excludes = re.findall(r"^  exclude: (\S+)", manifest, re.M)
    relative = CARRIERS_CORPUS.relative_to(REPO_ROOT).as_posix() + "/"

    assert len(ids) == 2
    assert len(excludes) == len(ids)
    for pattern in excludes:
        assert re.search(pattern, relative), pattern
