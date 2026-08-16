"""Document segmentation (tasks.md 2.2).

``wm_hook.regions`` answers one question — *what is every offset in this
document?* — and four confirmed defects in the shipped implementation are all
the same failure to ask it:

* a no-break space at column 0 of a YAML line replaced with an ASCII space,
  turning a parseable file into an unparseable one (Requirement 4.1, 4.2);
* CRLF frontmatter rewritten to LF on a file carrying no marks at all, because
  the block was reassembled from a hard-coded line feed (Requirement 6.1, 6.2);
* a leading ``---`` **thematic break** consumed as a frontmatter delimiter
  (Requirement 5.4);
* frontmatter hidden behind a byte-order mark, so pass one saw no block and
  pass two did (Requirement 5.6, 7.3).

Every assertion below is therefore positional. Three shapes recur:

* **Tiling.** Regions must cover ``[0, len(text))`` exactly, in order, with no
  gap, no overlap and no empty span. Anything else means some offset has no
  answer, and the classifier would have to invent one.
* **Coarse structure.** ``_merged`` collapses the structural splitting so a
  test can state "delimiter, body, delimiter, body" without restating every
  line start; ``_structural_offsets`` states the line starts on their own.
* **Corpus agreement.** ``crlf_markdown_frontmatter.md``,
  ``frontmatter_keys_concealed.md`` and ``bom_prefixed.csv`` are the committed
  reproductions of three of the four defects, and are segmented here directly
  rather than paraphrased.

Every invisible character in this module is written as a ``\\uXXXX`` escape.
A literal one would be rewritten by this repository's own pre-commit hook, and
the constant it was meant to pin would silently become something else. The
corpus data files are the deliberate exception and are excluded from the hook.
"""

from __future__ import annotations

import re

import pytest
from conftest import CARRIERS_CORPUS, PRESERVATION_CORPUS, load_corpus

from wm_hook.regions import (
    CR,
    CRLF,
    LF,
    LineEndingStyle,
    Region,
    RegionKind,
    Segmentation,
    segment,
)

# --------------------------------------------------------------------------
# Named invisibles, so the fixtures below read as intent rather than escapes
# --------------------------------------------------------------------------

_BOM = "\ufeff"
_ZWSP = "\u200b"
_ZWNJ = "\u200c"
_NBSP = "\u00a0"
_LINE_SEP = "\u2028"

_MD = {"is_markdown": True, "is_yaml": False}
_PLAIN = {"is_markdown": False, "is_yaml": False}
_YAML = {"is_markdown": False, "is_yaml": True}


# --------------------------------------------------------------------------
# Shared assertions
# --------------------------------------------------------------------------


def _assert_tiles(seg: Segmentation, text: str) -> None:
    """Regions cover ``[0, len(text))`` exactly, in order, none empty."""
    cursor = 0
    for region in seg.regions:
        assert region.start == cursor, f"gap or overlap before {region}"
        assert region.start < region.end, f"empty region {region}"
        cursor = region.end
    assert cursor == len(text), "regions do not reach the end of the document"


def _merged(seg: Segmentation) -> list[tuple[RegionKind, int, int]]:
    """Coarse structure: adjacent same-kind regions collapsed into one span."""
    out: list[tuple[RegionKind, int, int]] = []
    for region in seg.regions:
        if out and out[-1][0] is region.kind and out[-1][2] == region.start:
            kind, start, _ = out[-1]
            out[-1] = (kind, start, region.end)
        else:
            out.append((region.kind, region.start, region.end))
    return out


def _structural_offsets(seg: Segmentation) -> list[int]:
    """Every offset at which an ASCII space would carry structure."""
    offsets = []
    for region in seg.regions:
        if region.structural:
            assert region.end == region.start + 1, (
                f"a structural mark covers one position, got {region}"
            )
            offsets.append(region.start)
    return offsets


def _line_starts(text: str) -> list[int]:
    """Offsets that begin a line, splitting on CRLF / LF / CR only."""
    starts = [0] if text else []
    for match in re.finditer(r"\r\n|\n|\r", text):
        if match.end() < len(text):
            starts.append(match.end())
    return starts


def _corpus_text(directory, name: str) -> str:
    for entry in load_corpus(directory):
        if entry.name == name:
            return entry.read_bytes().decode("utf-8")
    raise AssertionError(f"corpus entry {name!r} is missing from {directory}")


# --------------------------------------------------------------------------
# Tiling: the postcondition every other assertion rests on
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "",
        "\n",
        "hello",
        "hello\n",
        "---\ntitle: x\n---\nbody\n",
        "---\r\ntitle: x\r\n---\r\nbody\r\n",
        f"{_BOM}---\ntitle: x\n---\n",
        f"{_BOM}{_ZWSP}",
        "---\n\nthematic break\n",
        "---\ntitle: unterminated\n",
        f"{_BOM}name,role\r\nada,pioneer\r\n",
    ],
    ids=[
        "empty",
        "bare-newline",
        "no-terminator",
        "one-line",
        "frontmatter-lf",
        "frontmatter-crlf",
        "bom-frontmatter",
        "invisibles-only",
        "thematic-break",
        "unterminated",
        "bom-csv",
    ],
)
@pytest.mark.parametrize("kinds", [_MD, _PLAIN, _YAML], ids=["md", "plain", "yaml"])
def test_regions_tile_the_document_exactly(text: str, kinds: dict) -> None:
    """Requirement 1.3 — every offset has exactly one answer."""
    _assert_tiles(segment(text, **kinds), text)


def test_empty_document_has_no_regions() -> None:
    seg = segment("", **_MD)
    assert seg.regions == ()
    assert seg.has_frontmatter is False


# --------------------------------------------------------------------------
# Frontmatter recognition
# --------------------------------------------------------------------------


def test_frontmatter_block_is_delimited_body_delimited() -> None:
    text = "---\ntitle: x\ntags:\n  - a\n---\n\n# Heading\n"
    seg = segment(text, **_MD)

    open_end = len("---\n")
    close_start = text.index("---\n", 1)
    close_end = close_start + len("---\n")

    assert seg.has_frontmatter is True
    assert _merged(seg) == [
        (RegionKind.FRONTMATTER_DELIM, 0, open_end),
        (RegionKind.FRONTMATTER_BODY, open_end, close_start),
        (RegionKind.FRONTMATTER_DELIM, close_start, close_end),
        (RegionKind.BODY, close_end, len(text)),
    ]
    assert seg.spans(RegionKind.FRONTMATTER_BODY) == ((open_end, close_start),)
    assert seg.spans(RegionKind.FRONTMATTER_DELIM) == (
        (0, open_end),
        (close_start, close_end),
    )


def test_frontmatter_closing_delimiter_may_end_the_document() -> None:
    text = "---\ntitle: x\n---"
    seg = segment(text, **_MD)

    assert seg.has_frontmatter is True
    assert _merged(seg)[-1] == (
        RegionKind.FRONTMATTER_DELIM,
        text.index("---", 1),
        len(text),
    )
    assert seg.spans(RegionKind.BODY) == ()


def test_frontmatter_is_found_only_in_markdown() -> None:
    text = "---\ntitle: x\n---\nbody\n"

    assert segment(text, **_MD).has_frontmatter is True
    assert segment(text, **_PLAIN).has_frontmatter is False
    assert _merged(segment(text, **_PLAIN)) == [(RegionKind.BODY, 0, len(text))]


def test_a_standalone_configuration_document_has_no_frontmatter() -> None:
    """``---`` in a YAML file is a document marker, not a frontmatter fence."""
    text = "---\ntitle: x\n---\nother: y\n"

    seg = segment(text, **_YAML)
    assert seg.has_frontmatter is False
    assert _merged(seg) == [(RegionKind.BODY, 0, len(text))]

    both = segment(text, is_markdown=True, is_yaml=True)
    assert both.has_frontmatter is False


# --------------------------------------------------------------------------
# Requirement 5.4 — a leading thematic break is not frontmatter
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "---\n\nProse under a thematic break.\n",
        "---\n# Heading\n\nProse.\n---\n",
        "---\nJust prose, no key.\n---\n",
        "---\n- a list item\n---\n",
        "---\n---\n",
        "---\nhttp://example.com/not-a-key\n---\n",
        "---\n",
        "---",
    ],
    ids=[
        "blank-follows",
        "heading-follows",
        "prose-follows",
        "list-follows",
        "empty-block",
        "colon-without-space",
        "delimiter-only-newline",
        "delimiter-only",
    ],
)
def test_leading_thematic_break_reports_no_frontmatter(text: str) -> None:
    """Requirement 5.4 — no key-like line, so the body is left whole."""
    seg = segment(text, **_MD)
    assert seg.has_frontmatter is False
    assert _merged(seg) == [(RegionKind.BODY, 0, len(text))]
    assert _structural_offsets(seg) == []


def test_unterminated_block_is_ordinary_body() -> None:
    """Design "Error Handling": no closing delimiter, so no frontmatter."""
    text = "---\ntitle: x\ntags:\n  - a\n\nStill going.\n"
    seg = segment(text, **_MD)

    assert seg.has_frontmatter is False
    assert _merged(seg) == [(RegionKind.BODY, 0, len(text))]


def test_a_thematic_break_later_in_the_body_does_not_close_anything() -> None:
    text = "# Title\n\nProse.\n\n---\n\nMore prose.\n"
    seg = segment(text, **_MD)

    assert seg.has_frontmatter is False
    assert _merged(seg) == [(RegionKind.BODY, 0, len(text))]


# --------------------------------------------------------------------------
# Requirement 5.6 / 7.3 — nothing may hide the block from the first pass
# --------------------------------------------------------------------------


def test_preamble_absorbs_a_leading_byte_order_mark() -> None:
    text = f"{_BOM}---\ntitle: x\n---\n"
    seg = segment(text, **_MD)

    assert seg.has_frontmatter is True
    assert _merged(seg)[0] == (RegionKind.PREAMBLE, 0, 1)
    assert seg.region_at(0).kind is RegionKind.PREAMBLE
    assert seg.spans(RegionKind.FRONTMATTER_DELIM)[0] == (1, 1 + len("---\n"))


def test_preamble_absorbs_a_run_of_invisibles_before_the_delimiter() -> None:
    text = f"{_BOM}{_ZWSP}{_ZWNJ}---\ntitle: x\n---\n"
    seg = segment(text, **_MD)

    assert seg.has_frontmatter is True
    assert _merged(seg)[0] == (RegionKind.PREAMBLE, 0, 3)


def test_invisibles_inside_the_delimiter_do_not_hide_it() -> None:
    text = f"-{_ZWSP}--\ntitle: x\n-{_ZWNJ}--\n"
    seg = segment(text, **_MD)

    assert seg.has_frontmatter is True
    assert _merged(seg)[0] == (RegionKind.FRONTMATTER_DELIM, 0, len(f"-{_ZWSP}--\n"))


def test_a_concealed_key_still_opens_the_block() -> None:
    """7.3 — the zero-width space inside ``generator`` must not cost a pass."""
    text = f"---\ngene{_ZWSP}rator: Claude\n---\n"
    seg = segment(text, **_MD)

    assert seg.has_frontmatter is True
    assert seg.spans(RegionKind.FRONTMATTER_BODY) == (
        (len("---\n"), text.index("---\n", 1)),
    )


def test_a_space_homoglyph_before_the_first_key_still_opens_the_block() -> None:
    text = f"---\n{_NBSP}generator: Claude\n---\n"
    seg = segment(text, **_MD)

    assert seg.has_frontmatter is True


def test_a_preamble_with_no_document_after_it_is_still_a_preamble() -> None:
    text = f"{_BOM}{_ZWSP}"
    seg = segment(text, **_PLAIN)

    assert _merged(seg) == [(RegionKind.PREAMBLE, 0, 2)]
    assert seg.has_frontmatter is False


def test_a_space_is_not_invisible_and_does_not_start_a_preamble() -> None:
    """A leading NBSP is visible whitespace: the line is not a delimiter."""
    text = f"{_NBSP}---\ntitle: x\n---\n"
    seg = segment(text, **_MD)

    assert seg.has_frontmatter is False
    assert _merged(seg) == [(RegionKind.BODY, 0, len(text))]


# --------------------------------------------------------------------------
# Requirement 4.1 / 4.2 — where a space would be structurally significant
# --------------------------------------------------------------------------


def test_line_starts_inside_frontmatter_are_structural() -> None:
    text = "---\ntitle: x\ntags:\n  - a\n---\n\n# Heading\n"
    seg = segment(text, **_MD)

    frontmatter_end = text.index("---\n", 1) + len("---\n")
    expected = [start for start in _line_starts(text) if start < frontmatter_end]

    assert _structural_offsets(seg) == expected
    assert seg.is_structural(0) is True
    assert seg.is_structural(len("---\n")) is True
    assert seg.is_structural(len("---\nt")) is False
    assert seg.is_structural(frontmatter_end) is False


def test_the_column_zero_no_break_space_defect_is_marked() -> None:
    """The reproduction: replacing this NBSP with a space breaks the parse."""
    text = f"---\ntitle: x\n{_NBSP}generator: Claude\n---\n"
    seg = segment(text, **_MD)

    nbsp_at = text.index(_NBSP)
    assert seg.is_structural(nbsp_at) is True
    assert seg.region_at(nbsp_at).kind is RegionKind.FRONTMATTER_BODY
    # One position further along the same line is ordinary text.
    assert seg.is_structural(nbsp_at + 1) is False


def test_body_of_a_markdown_document_is_never_structural() -> None:
    text = "---\ntitle: x\n---\n\nProse with a space.\n"
    seg = segment(text, **_MD)

    body_start = seg.spans(RegionKind.BODY)[0][0]
    assert all(offset < body_start for offset in _structural_offsets(seg))


def test_every_line_start_of_a_configuration_document_is_structural() -> None:
    text = "name: hook\nnested:\n  key: value\n\ntrailing: true\n"
    seg = segment(text, **_YAML)

    assert _structural_offsets(seg) == _line_starts(text)
    assert all(region.kind is RegionKind.BODY for region in seg.regions)


def test_a_preamble_is_not_structural() -> None:
    text = f"{_BOM}name: hook\n"
    seg = segment(text, **_YAML)

    assert seg.is_structural(0) is False
    assert seg.region_at(0).kind is RegionKind.PREAMBLE
    assert seg.is_structural(1) is True


def test_plain_text_has_no_structural_positions() -> None:
    seg = segment("a line\nanother line\n", **_PLAIN)
    assert _structural_offsets(seg) == []


# --------------------------------------------------------------------------
# Requirement 6.1 / 6.2 / 6.3 — line endings and the trailing newline
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "newline", "uniform", "trailing"),
    [
        ("a\nb\n", LF, True, True),
        ("a\r\nb\r\n", CRLF, True, True),
        ("a\rb\r", CR, True, True),
        ("a\nb", LF, True, False),
        ("a\r\nb", CRLF, True, False),
        ("", LF, True, False),
        ("no terminator at all", LF, True, False),
        ("a\r\nb\r\nc\n", CRLF, False, True),
        ("a\nb\r\nc\r\n", CRLF, False, True),
        ("a\nb\r\n", LF, False, True),
    ],
    ids=[
        "lf",
        "crlf",
        "cr",
        "lf-no-trailing",
        "crlf-no-trailing",
        "empty",
        "single-line",
        "mixed-crlf-dominant",
        "mixed-crlf-dominant-late",
        "mixed-tie-first-wins",
    ],
)
def test_line_ending_detection(
    text: str, newline: str, uniform: bool, trailing: bool
) -> None:
    style = segment(text, **_PLAIN).line_endings

    assert style.newline == newline
    assert style.uniform is uniform
    assert style.ends_with_newline is trailing
    assert style == LineEndingStyle.detect(text)


def test_a_unicode_line_separator_is_not_a_line_break() -> None:
    """``str.splitlines`` would split here; YAML and Markdown do not."""
    text = f"---{_LINE_SEP}title: x\n---\n"
    seg = segment(text, **_MD)

    assert seg.has_frontmatter is False
    assert segment(f"a{_LINE_SEP}b", **_YAML).line_endings.ends_with_newline is False
    assert _structural_offsets(segment(f"a{_LINE_SEP}b", **_YAML)) == [0]


def test_crlf_frontmatter_keeps_its_convention() -> None:
    text = "---\r\ntitle: x\r\n---\r\nbody\r\n"
    seg = segment(text, **_MD)

    assert seg.has_frontmatter is True
    assert seg.line_endings.newline == CRLF
    assert seg.line_endings.uniform is True
    assert _structural_offsets(seg) == [0, len("---\r\n"), text.index("---\r\n", 1)]


# --------------------------------------------------------------------------
# Positional lookups
# --------------------------------------------------------------------------


def test_region_at_returns_the_region_containing_the_offset() -> None:
    text = f"{_BOM}---\ntitle: x\n---\nbody\n"
    seg = segment(text, **_MD)

    for region in seg.regions:
        for offset in range(region.start, region.end):
            assert seg.region_at(offset) is region


@pytest.mark.parametrize("offset", [-1, 6])
def test_region_at_rejects_an_offset_outside_the_document(offset: int) -> None:
    seg = segment("hello\n", **_PLAIN)
    with pytest.raises(IndexError):
        seg.region_at(offset)


def test_offset_zero_is_marked_so_the_byte_order_mark_rule_needs_no_format() -> None:
    """Task 2.4(a): a mark at offset zero is preserved, interior ones are not."""
    text = f"{_BOM}id,name\r\n1,{_BOM}Ada\r\n"
    seg = segment(text, **_PLAIN)

    interior = text.index(_BOM, 1)
    assert seg.at_document_start(0) is True
    assert seg.at_document_start(interior) is False
    assert seg.region_at(0).kind is RegionKind.PREAMBLE
    assert seg.region_at(interior).kind is RegionKind.BODY


def test_value_objects_are_immutable() -> None:
    seg = segment("hello\n", **_PLAIN)
    with pytest.raises(Exception):
        seg.regions[0].start = 1  # type: ignore[misc]
    with pytest.raises(Exception):
        seg.has_frontmatter = True  # type: ignore[misc]
    assert isinstance(seg.regions[0], Region)
    assert isinstance(seg.line_endings, LineEndingStyle)


# --------------------------------------------------------------------------
# The committed defect reproductions
# --------------------------------------------------------------------------


def test_corpus_crlf_markdown_frontmatter() -> None:
    """The CRLF-churn reproduction: frontmatter *and* a body thematic break."""
    text = _corpus_text(PRESERVATION_CORPUS, "crlf_markdown_frontmatter.md")
    seg = segment(text, **_MD)
    _assert_tiles(seg, text)

    close_start = text.index("---\r\n", 1)
    assert seg.has_frontmatter is True
    assert seg.line_endings.newline == CRLF
    assert seg.line_endings.uniform is True
    assert seg.line_endings.ends_with_newline is True
    assert _merged(seg) == [
        (RegionKind.FRONTMATTER_DELIM, 0, len("---\r\n")),
        (RegionKind.FRONTMATTER_BODY, len("---\r\n"), close_start),
        (RegionKind.FRONTMATTER_DELIM, close_start, close_start + len("---\r\n")),
        (RegionKind.BODY, close_start + len("---\r\n"), len(text)),
    ]
    # The second `---` in the file is a thematic break inside the body.
    thematic = text.index("---\r\n", close_start + 1)
    assert seg.region_at(thematic).kind is RegionKind.BODY


def test_corpus_bom_prefixed_csv() -> None:
    """A byte-order-marked data file: preamble, then body, no frontmatter."""
    text = _corpus_text(PRESERVATION_CORPUS, "bom_prefixed.csv")
    seg = segment(text, **_PLAIN)
    _assert_tiles(seg, text)

    assert seg.has_frontmatter is False
    assert _merged(seg) == [
        (RegionKind.PREAMBLE, 0, 1),
        (RegionKind.BODY, 1, len(text)),
    ]
    assert seg.line_endings.newline == CRLF
    assert seg.line_endings.ends_with_newline is True
    assert _structural_offsets(seg) == []


def test_corpus_persian_frontmatter_values() -> None:
    """Joiners inside values must not disturb the block's boundaries."""
    text = _corpus_text(PRESERVATION_CORPUS, "persian_frontmatter_values.md")
    seg = segment(text, **_MD)
    _assert_tiles(seg, text)

    assert seg.has_frontmatter is True
    assert seg.line_endings.newline == LF
    body_start, body_end = seg.spans(RegionKind.FRONTMATTER_BODY)[0]
    assert text[body_start:body_end].startswith("title: ")


@pytest.mark.parametrize("directory", [PRESERVATION_CORPUS, CARRIERS_CORPUS])
def test_every_corpus_entry_segments_into_a_complete_tiling(directory) -> None:
    for entry in load_corpus(directory):
        text = entry.read_bytes().decode("utf-8", errors="surrogateescape")
        for kinds in (_MD, _PLAIN, _YAML):
            seg = segment(text, **kinds)
            _assert_tiles(seg, text)
