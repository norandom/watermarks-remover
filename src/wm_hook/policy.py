"""The set of transforms the cleaner may perform, and their defaults.

One immutable flag per transformation that carries a documented false-positive
risk (Requirement 9.1). Constructed once per run and threaded through the
classifier; nothing mutates it mid-document.

Three defaults differ from the shipped behaviour, each mandated by a
requirement rather than chosen for taste:

- ``strip_private_use`` is off (3.5). Private-use codepoints are where Nerd
  Font and Powerline glyphs live, and the shipped cleaner deletes them with no
  preservation rule at all.
- ``strip_bom`` is off (6.5). A leading byte-order mark is a required encoding
  signal for several formats; only interior occurrences are carriers.
- ``normalize_spaces`` stays on, but Requirement 4.1 makes it *position-aware*
  rather than unconditional. That is enforced in the classifier, not here --
  see the class docstring note on why this object cannot express it.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace

__all__ = ["CleanPolicy"]


@dataclass(frozen=True)
class CleanPolicy:
    """Which transformations are enabled for a run.

    Frozen: a policy is decided once and read many times, and an accidental
    mid-document mutation would make a cleaning run unreproducible.

    **This object cannot express a correctness rule, only a preference.**
    Requirement 4.1 forbids replacing a space homoglyph at a structurally
    significant position *regardless of policy*, and 4.3 requires stripping
    rather than replacing where a replacement would conceal provenance. Both
    are decided by position and so live in the classifier, which is the only
    component that knows where a character sits. No flag here can re-enable
    them; that asymmetry is deliberate -- correctness outranks configuration.
    """

    #: Replace the sixteen space homoglyphs with U+0020, except where position
    #: makes the substitution structurally unsafe (Requirements 4.1, 4.4, 4.5).
    normalize_spaces: bool = True

    #: Delete private-use codepoints. Off by default: they carry icon-font
    #: glyphs in tracked text files (Requirement 3.5).
    strip_private_use: bool = False

    #: Delete a byte-order mark at offset zero. Off by default: several formats
    #: require it as an encoding signal (Requirement 6.5). Interior occurrences
    #: are carriers regardless of this flag.
    strip_bom: bool = False

    #: Delete directional marks and correctly paired embeddings. Off by
    #: default: both are legitimate in mixed RTL/LTR prose (Requirement 3.7).
    #: Overrides are removed unconditionally and are not governed by this flag.
    strip_bidi: bool = False

    #: Delete emoji joiners and presentation selectors. Off by default:
    #: stripping them visibly alters rendered sequences (Requirements 3.1, 3.2).
    strip_emoji_glue: bool = False

    #: Fold confusable Latin lookalikes to ASCII. Off by default: the
    #: false-positive rate on real multilingual source is unacceptable for an
    #: unattended commit-time rewrite.
    aggressive_homoglyphs: bool = False

    # NOTE: `drop_frontmatter_keys` was removed with the frontmatter feature.
    # Provenance metadata is a different channel from text carriers, and the
    # feature was the source of three defects that deletion resolved outright.

    @classmethod
    def default(cls) -> CleanPolicy:
        """The safe default set applied when no configuration is supplied.

        Requirement 9.3. Equivalent to ``CleanPolicy()``; named so that callers
        state the intent explicitly rather than relying on bare construction.
        """
        return cls()

    @classmethod
    def field_names(cls) -> tuple[str, ...]:
        """Every transform flag, in declaration order (Requirement 9.4)."""
        return tuple(f.name for f in fields(cls))

    def with_overrides(self, **overrides: bool) -> CleanPolicy:
        """Return a copy with *overrides* applied.

        Rejects unknown flags rather than silently ignoring them: a typo in a
        hook argument must fail loudly, not quietly leave a risky transform on.
        """
        unknown = set(overrides) - set(self.field_names())
        if unknown:
            raise ValueError(
                f"unknown policy flag(s): {', '.join(sorted(unknown))}; "
                f"known flags are {', '.join(self.field_names())}"
            )
        for name, value in overrides.items():
            if not isinstance(value, bool):
                raise TypeError(
                    f"policy flag {name!r} must be a bool, got {type(value).__name__}"
                )
        return replace(self, **overrides)
