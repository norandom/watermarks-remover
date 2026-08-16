"""Decide, once, what every offset in a document *is* (tasks.md 2.2).

Four confirmed defects in the shipped implementation share one cause: it acts
on characters without knowing where they are. A no-break space at column 0 of a
YAML line is replaced with an ASCII space and the file stops parsing; a CRLF
frontmatter block is reassembled from a hard-coded line feed and a mark-free
file is rewritten; a leading ``---`` thematic break is eaten as a frontmatter
delimiter; a byte-order mark hides the frontmatter from pass one, so pass two
finds it and the commit fails twice.

This module is the shared answer. It reads the document once and returns a
positional map: which offsets are preamble, which are frontmatter delimiters,
which are frontmatter body, which are ordinary body, and -- the part the
classifier depends on -- which offsets are places where an ASCII space would
carry structure rather than typography.

Three decisions are worth stating outright, because each one is a defect fix:

* **The preamble tolerates a leading byte-order mark and a run of invisible
  characters.** Nothing placed in front of the opening delimiter can hide the
  block from the first pass (Requirements 5.6, 7.3), and the delimiter test
  itself ignores format characters, so ``-<ZWSP>--`` still opens a block.

* **A leading ``---`` is a frontmatter delimiter only if a key-like line
  follows it.** A blank line, a heading, a list item or plain prose means the
  document opened with a thematic break and the body must be left whole
  (Requirement 5.4). An unterminated block is likewise ordinary body: no
  closing delimiter, no frontmatter processing.

* **``structural`` marks single positions, not whole spans.** The rule is
  "the first content position of a line", and a frontmatter region is split so
  that exactly those positions carry the flag. A space in the *middle* of a
  frontmatter line is ordinary typography and may be normalised; a space at the
  start of one is indentation, and changing it changes the parse
  (Requirements 4.1, 4.2). Position-blindness is what this module exists to
  remove, so it does not hand back a coarse per-block flag that would be wrong
  for most of the block.

Deliberately dependency-free: stdlib only, no policy, no vendored tables
(design.md "Components and Interfaces", ``regions.py`` -- Key Dependencies:
none). Segmentation is about *where things are*, and nothing about where a
character sits depends on which transforms an adopter enabled.
"""

from __future__ import annotations

import re
import unicodedata
from bisect import bisect_right
from collections.abc import Collection
from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "CR",
    "CRLF",
    "LF",
    "LineEndingStyle",
    "Region",
    "RegionKind",
    "Segmentation",
    "segment",
]

#: The three line terminators a text file may use. ``U+2028`` and ``U+2029``
#: are deliberately absent: ``str.splitlines`` treats them as line breaks and
#: YAML 1.2 and Markdown do not, so splitting on them would invent a line start
#: -- and therefore a structural position -- that no parser agrees with.
LF = "\n"
CRLF = "\r\n"
CR = "\r"

_LINE_BREAK_RE = re.compile(r"\r\n|\n|\r")

#: The literal opening and closing fence. Only three hyphens: upstream's
#: ``_FM_RE`` accepts nothing else, and a block this module declines to
#: recognise is treated as body and left untouched, which is the safe
#: direction for anything ambiguous.
_DELIMITER = "---"

#: A top-level mapping entry: a key, a colon, then whitespace or end of line.
#: ``#`` and ``-`` are excluded as the first character so a Markdown heading
#: and a list item cannot be mistaken for a key (design.md "Region
#: segmentation": ``MaybeDelim --> Body`` on ``blank / heading / prose``).
_KEY_LINE_RE = re.compile(r"[^\s:#-][^:]*:(?:\s|$)")


class RegionKind(Enum):
    """What a span of the document is."""

    PREAMBLE = "preamble"  # BOM / invisibles before anything
    FRONTMATTER_DELIM = "fm_delim"
    FRONTMATTER_BODY = "fm_body"
    BODY = "body"


@dataclass(frozen=True)
class Region:
    """A half-open span of the document that is all one thing."""

    kind: RegionKind
    start: int  # inclusive char offset
    end: int  # exclusive
    structural: bool  # spaces here carry meaning


@dataclass(frozen=True)
class LineEndingStyle:
    """The document's line-ending convention and trailing-newline state.

    Both halves exist to be *preserved*, not corrected (Requirements 6.1-6.3).
    ``uniform`` is recorded rather than inferred so a caller can honour 6.2 --
    a file whose endings were uniform before cleaning must still be uniform
    after -- without re-scanning the text.
    """

    #: The terminator to use when one has to be written: the most common in
    #: the document, earliest-seen breaking a tie, and LF when the document
    #: contains none at all.
    newline: str = LF

    #: Every terminator in the document is the same one (vacuously true when
    #: there are none).
    uniform: bool = True

    #: The document ends with a line terminator.
    ends_with_newline: bool = False

    @classmethod
    def detect(cls, text: str) -> "LineEndingStyle":
        """Read the convention off *text* without altering it."""
        counts: dict[str, int] = {}
        for match in _LINE_BREAK_RE.finditer(text):
            terminator = match.group()
            counts[terminator] = counts.get(terminator, 0) + 1
        if not counts:
            return cls(newline=LF, uniform=True, ends_with_newline=False)

        order = list(counts)
        newline = min(order, key=lambda nl: (-counts[nl], order.index(nl)))
        return cls(
            newline=newline,
            uniform=len(counts) == 1,
            ends_with_newline=text.endswith((LF, CR)),
        )


@dataclass(frozen=True)
class Segmentation:
    """The document's positional map. Derived, immutable, computed once."""

    regions: tuple[Region, ...]
    has_frontmatter: bool
    line_endings: LineEndingStyle

    #: Region start offsets, so ``region_at`` is a binary search rather than a
    #: scan. The pipeline asks once per character, so an O(n) lookup would make
    #: cleaning quadratic in file size. Not part of the interface: derived in
    #: ``__post_init__``, excluded from the constructor, repr and equality.
    _starts: tuple[int, ...] = field(
        init=False, repr=False, compare=False, default=()
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "_starts", tuple(region.start for region in self.regions)
        )

    def region_at(self, offset: int) -> Region:
        """The region containing *offset*.

        Total over ``[0, len(text))`` by construction -- the regions tile the
        document -- so a caller never has to handle a missing answer. An
        offset outside the document is a caller bug, not a document property,
        and raises.
        """
        index = bisect_right(self._starts, offset) - 1
        if index < 0 or offset >= self.regions[index].end or offset < 0:
            raise IndexError(f"offset {offset} is outside the segmented document")
        return self.regions[index]

    def is_structural(self, offset: int) -> bool:
        """True when an ASCII space at *offset* would carry structure.

        This is the mechanism that stops space normalisation from changing how
        a file parses (Requirements 4.1, 4.2). No policy flag may override it:
        correctness outranks configuration.
        """
        return self.region_at(offset).structural

    def at_document_start(self, offset: int) -> bool:
        """True only at offset zero.

        The byte-order-mark rule is positional, not format-conditional: a mark
        at offset zero is a required encoding signal and is preserved, every
        interior occurrence is a carrier (Requirements 2.1, 6.5). The
        classifier is never told the file's format, so it asks this instead --
        and asking segmentation keeps the whole positional vocabulary in one
        place rather than opening a second channel into the classifier.
        """
        return offset == 0

    def spans(self, kind: RegionKind) -> tuple[tuple[int, int], ...]:
        """The document's spans of *kind*, adjacent regions merged.

        ``structural`` splits a frontmatter block into many one-position
        regions; a consumer that wants the block itself -- the key policy, for
        one -- wants it back in one piece.
        """
        out: list[list[int]] = []
        for region in self.regions:
            if region.kind is not kind:
                continue
            if out and out[-1][1] == region.start:
                out[-1][1] = region.end
            else:
                out.append([region.start, region.end])
        return tuple((start, end) for start, end in out)


@dataclass(frozen=True)
class _Line:
    """One line: where it begins, where its content ends, where it ends."""

    start: int
    content_end: int  # exclusive, before the terminator
    end: int  # exclusive, after the terminator


def segment(text: str, *, is_markdown: bool, is_yaml: bool) -> Segmentation:
    """Segment *text* into typed regions that tile it exactly.

    *is_markdown* enables frontmatter recognition; *is_yaml* declares a
    standalone configuration document, in which every line start is
    structural and a ``---`` is a YAML document marker rather than a
    frontmatter fence. When both are set the document is treated as
    configuration: mis-reading a config file's own document markers as
    frontmatter is the more damaging of the two mistakes.

    Postcondition: the returned regions cover ``[0, len(text))`` with no gap,
    no overlap and no empty span. ``has_frontmatter`` is true only when a
    closing delimiter was found and a key-like line sits between the
    delimiters.
    """
    line_endings = LineEndingStyle.detect(text)
    if not text:
        return Segmentation(
            regions=(), has_frontmatter=False, line_endings=line_endings
        )

    lines = _split_lines(text)
    preamble_end = _preamble_end(text)
    marks = _structural_positions(lines, preamble_end)

    frontmatter = None
    if is_markdown and not is_yaml:
        frontmatter = _find_frontmatter(text, lines)

    # Ordinary body text is structural only in a standalone configuration
    # document; in Markdown prose a leading space is typography, not syntax.
    body_marks = marks if is_yaml else frozenset()

    regions: list[Region] = []
    if preamble_end > 0:
        # Never structural: the preamble is what sits *before* content, so
        # nothing in it occupies a column that a parser is counting.
        regions.append(Region(RegionKind.PREAMBLE, 0, preamble_end, False))

    if frontmatter is not None:
        opening, closing = frontmatter
        delim = RegionKind.FRONTMATTER_DELIM
        _extend(regions, delim, preamble_end, opening.end, marks)
        _extend(regions, RegionKind.FRONTMATTER_BODY, opening.end, closing.start, marks)
        _extend(regions, delim, closing.start, closing.end, marks)
        _extend(regions, RegionKind.BODY, closing.end, len(text), body_marks)
    else:
        _extend(regions, RegionKind.BODY, preamble_end, len(text), body_marks)

    return Segmentation(
        regions=tuple(regions),
        has_frontmatter=frontmatter is not None,
        line_endings=line_endings,
    )


# --------------------------------------------------------------------------
# Lines
# --------------------------------------------------------------------------


def _split_lines(text: str) -> tuple[_Line, ...]:
    """Split *text* on CRLF / LF / CR only, keeping every offset accountable.

    ``str.splitlines`` also breaks on ``U+000B``, ``U+000C``, ``U+001C``-
    ``U+001E``, ``U+0085``, ``U+2028`` and ``U+2029``. Using it here would
    manufacture line starts that no YAML or Markdown parser recognises, and a
    line start is a structural position -- so the error would propagate
    straight into what the cleaner refuses to touch.
    """
    lines: list[_Line] = []
    cursor = 0
    for match in _LINE_BREAK_RE.finditer(text):
        lines.append(_Line(cursor, match.start(), match.end()))
        cursor = match.end()
    if cursor < len(text):
        lines.append(_Line(cursor, len(text), len(text)))
    return tuple(lines)


def _structural_positions(
    lines: tuple[_Line, ...], preamble_end: int
) -> frozenset[int]:
    """The first content position of every line.

    Column 0 of a line is where indentation is measured from, which is why a
    space there is load-bearing in YAML. The preamble is not content -- with a
    byte-order mark at offset zero the first *content* position of line one is
    offset one, and that is the position an indentation-sensitive parser sees.
    """
    positions = set()
    for line in lines:
        first = max(line.start, preamble_end)
        if first < line.end:
            positions.add(first)
    return frozenset(positions)


def _extend(
    regions: list[Region],
    kind: RegionKind,
    start: int,
    end: int,
    marks: Collection[int],
) -> None:
    """Append ``[start, end)`` as *kind*, split so each mark stands alone.

    Empty spans are dropped rather than appended: a zero-length region would
    satisfy "tiles the document" while telling a consumer nothing, and would
    make ``region_at`` ambiguous at its boundary.
    """
    if start >= end:
        return
    cursor = start
    for position in sorted(position for position in marks if start <= position < end):
        if position > cursor:
            regions.append(Region(kind, cursor, position, False))
        regions.append(Region(kind, position, position + 1, True))
        cursor = position + 1
    if cursor < end:
        regions.append(Region(kind, cursor, end, False))


# --------------------------------------------------------------------------
# Invisibles
# --------------------------------------------------------------------------


def _is_invisible(char: str) -> bool:
    """True for a Unicode format character (general category ``Cf``).

    That is the whole zero-width family, the byte-order mark, the bidi
    controls and the tag block -- everything that can sit in front of a
    delimiter without showing. Category rather than an enumerated table, so a
    newly assigned format character is tolerated without a change here, and
    stdlib rather than the vendored codepoint tables, which segmentation must
    not depend on.
    """
    return unicodedata.category(char) == "Cf"


def _visible(text: str) -> str:
    """*text* with its format characters removed."""
    return "".join(char for char in text if not _is_invisible(char))


def _preamble_end(text: str) -> int:
    """Length of the leading run of invisible characters.

    Bounded to the first line by construction: no line terminator is a format
    character, so the preamble can never swallow one.
    """
    index = 0
    while index < len(text) and _is_invisible(text[index]):
        index += 1
    return index


# --------------------------------------------------------------------------
# Frontmatter
# --------------------------------------------------------------------------


def _is_delimiter(content: str) -> bool:
    """True when *content* is a ``---`` fence, invisibles notwithstanding."""
    return _visible(content) == _DELIMITER


def _is_key_like(content: str) -> bool:
    """True when *content* could be the first entry of a YAML mapping.

    Invisibles are removed and leading whitespace -- including space
    homoglyphs -- is skipped before the test, so a key concealed behind a
    zero-width space or a no-break space still opens the block on pass one
    (Requirements 5.6, 7.3). This is the segmentation half of the concealed-key
    behaviour; the key *policy* half lands in ``frontmatter.py``.
    """
    return _KEY_LINE_RE.match(_visible(content).lstrip()) is not None


def _find_frontmatter(
    text: str, lines: tuple[_Line, ...]
) -> tuple[_Line, _Line] | None:
    """Locate the opening and closing delimiter lines, or report none.

    Follows design.md's "Region segmentation" state machine exactly: an
    opening fence, then a key-like line or it was a thematic break, then a
    closing fence or it was never frontmatter at all.
    """
    if len(lines) < 3:
        return None

    opening = lines[0]
    if not _is_delimiter(text[opening.start : opening.content_end]):
        return None

    first_entry = lines[1]
    if not _is_key_like(text[first_entry.start : first_entry.content_end]):
        return None  # a thematic break: blank, heading, list or prose follows

    for closing in lines[2:]:
        if _is_delimiter(text[closing.start : closing.content_end]):
            return opening, closing
    return None  # unterminated: ordinary body text
