"""The only owned module that reaches into ``_vendor/``.

The vendored modules are byte-exact copies of upstream's ``service/scripts/``
and import each other by bare name (``from common import ...``). That works
only with ``_vendor/`` on ``sys.path``, and until now the sole insertion lived
inside ``cli.py`` — which would force every owned module and every test to
import the command-line entry point just to see a codepoint table. The
insertion therefore lives here, and everything else imports its constants from
this module (design.md "File Structure Plan").

What this module may pull in is settled by measurement, not preference
(research.md "Validating the central bet before implementation"):

===================  ==================================================
``text_unicode``     stdlib only, imports no sibling, mutates nothing.
                     Imported here; all fifteen codepoint tables are free.
``container_meta``   Pulls ``image_meta`` **and** ``common``, and
``common``           reconfigures process stdin/stdout/stderr to UTF-8 as an
                     import side effect. Never imported in production code;
                     the frontmatter key vocabulary is re-declared in
                     ``frontmatter.py`` and drift-tested instead.
===================  ==================================================

So importing this module is observably inert: it adds one ``sys.path`` entry
and one stdlib-only module, and leaves the process's stdio encoding exactly as
it found it. ``tests/test_tables.py`` asserts that in a bare subprocess.

Only *data* crosses this boundary. The vendored decision functions
(``_decide``, ``clean_text``, ``clean_markdown``, ``inspect_text``) are
deliberately not re-exported: owning those decisions is the point of this
spec, and tests may import them only to measure divergence.

Names are kept exactly as upstream spells them, underscore prefixes included,
so that a reader comparing this module against ``_vendor/text_unicode.py`` — or
a reviewer of the next ``refresh.sh`` bump — has no rename table to consult.
"""

from __future__ import annotations

import sys
from pathlib import Path

_VENDOR_DIR = Path(__file__).resolve().parent / "_vendor"


def _ensure_vendor_importable() -> None:
    """Make ``_vendor/`` resolvable by bare module name, at most once.

    Idempotent because ``cli.py`` performs the identical insertion today; the
    two must not stack up duplicate entries while both exist.
    """
    entry = str(_VENDOR_DIR)
    if entry not in sys.path:
        sys.path.insert(0, entry)


_ensure_vendor_importable()

import text_unicode as _text_unicode  # noqa: E402  (needs the path insertion above)

# --- Strip and replacement tables -----------------------------------------

#: Format / invisible controls treated as carriers.
STRIP_CODEPOINTS: frozenset[int] = _text_unicode.STRIP_CODEPOINTS

#: Space lookalikes and the ASCII space each maps to.
SPACE_HOMOGLYPHS: dict[int, str] = _text_unicode.SPACE_HOMOGLYPHS

#: Cyrillic/fullwidth Latin lookalikes and their ASCII equivalents.
LATIN_CONFUSABLES: dict[int, str] = _text_unicode.LATIN_CONFUSABLES

#: Variation selectors VS17-VS256 (Supplementary Special-purpose plane).
_VS_SUPPLEMENT: range = _text_unicode._VS_SUPPLEMENT

# --- Bidi sets -------------------------------------------------------------

#: Every bidi / directional format control.
_BIDI_CPS: frozenset[int] = _text_unicode._BIDI_CPS

#: The subset that is legitimate in mixed RTL/LTR prose: marks and isolates,
#: but not the embeddings and overrides that can reorder unrelated spans.
_PRESERVABLE_BIDI_CPS: frozenset[int] = _text_unicode._PRESERVABLE_BIDI_CPS

# --- Glue: invisibles that are load-bearing next to the right base ---------

#: Zero-width family, the common edit-based carriers.
_ZW_FAMILY: frozenset[int] = _text_unicode._ZW_FAMILY

#: Zero-width joiner and the text/emoji variation selectors.
EMOJI_GLUE_CODEPOINTS: frozenset[int] = _text_unicode.EMOJI_GLUE_CODEPOINTS

#: ZWNJ/ZWJ, orthographic inside complex scripts.
_SCRIPT_JOINERS: frozenset[int] = _text_unicode._SCRIPT_JOINERS

#: Tag characters, which spell out subdivision-flag sequences.
_TAG_RANGE: range = _text_unicode._TAG_RANGE

#: Arabic/Syriac Cf codepoints that are normal orthography, not carriers.
_ORTHOGRAPHIC_CF: frozenset[int] = _text_unicode._ORTHOGRAPHIC_CF

#: Mongolian free variation selectors.
_MONGOLIAN_FVS: frozenset[int] = _text_unicode._MONGOLIAN_FVS

#: Khmer inherent vowels: invisible but phonemic.
_KHMER_VOWELS: frozenset[int] = _text_unicode._KHMER_VOWELS

#: Hangul fillers, which hold a jamo slot in a partial syllable.
_HANGUL_FILLERS: frozenset[int] = _text_unicode._HANGUL_FILLERS

#: The same-script fillers and selectors, unioned.
_SCRIPT_GLUE: frozenset[int] = _text_unicode._SCRIPT_GLUE

#: The complete vendored table inventory. Tests hold this in step with
#: ``_vendor/text_unicode.py``, so a refresh that adds a table fails loudly
#: instead of leaving owned modules working from a stale inventory.
__all__ = [
    "STRIP_CODEPOINTS",
    "SPACE_HOMOGLYPHS",
    "LATIN_CONFUSABLES",
    "_VS_SUPPLEMENT",
    "_BIDI_CPS",
    "_PRESERVABLE_BIDI_CPS",
    "_ZW_FAMILY",
    "EMOJI_GLUE_CODEPOINTS",
    "_SCRIPT_JOINERS",
    "_TAG_RANGE",
    "_ORTHOGRAPHIC_CF",
    "_MONGOLIAN_FVS",
    "_KHMER_VOWELS",
    "_HANGUL_FILLERS",
    "_SCRIPT_GLUE",
]
