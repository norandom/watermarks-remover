# Invisible characters and what they indicate

A catalogue of the codepoints involved, what each one legitimately does, and
what its presence in an unexpected place suggests.

The central point of this page: **almost every one of these has a legitimate
use.** Presence alone indicates nothing. Position and context are what carry
information.

## Zero-width family

| Codepoint | Name | Legitimate use | Suspicious when |
| --- | --- | --- | --- |
| `U+200B` | Zero width space | Word separator in Thai, Lao, Khmer, Myanmar. Soft break hint in HTML. | Between Latin letters, or in runs |
| `U+200C` | Zero width non-joiner | Persian/Urdu word-internal breaks. After a Devanagari virama to force an explicit halant. | Between Latin letters |
| `U+200D` | Zero width joiner | Emoji sequences (`👨‍👩‍👧`). Devanagari half-forms and the eyelash reph. | Between ASCII digits or Latin letters |
| `U+2060` | Word joiner | Prevents a line break without a space. | In runs, or in source code |
| `U+FEFF` | BOM / zero width no-break space | Encoding signature **at offset zero only** | Anywhere else in the file |

A run of these between Latin letters is the classic binary-encoding channel:
two distinct codepoints give you one bit each.

## The Unicode Tag block

`U+E0000`–`U+E007F` mirrors ASCII one-to-one and renders as nothing. `U+E0041`
is an invisible `A`.

Its only sanctioned modern use is subdivision flag sequences: `U+1F3F4`
followed by 2–6 tag letters and terminated by `U+E007F CANCEL TAG`. That is how
`🏴󠁧󠁢󠁳󠁣󠁴󠁿` is encoded.

Anywhere else, a tag character does not belong. A whole readable string can be
carried invisibly, and it survives copy and paste.

!!! danger "The bounded-payload subtlety"

    A cleaner that preserves "a complete flag sequence" without bounding the
    payload length can be defeated by putting an arbitrary string between
    `U+1F3F4` and `U+E007F`. A conforming subdivision code is 2–6 characters
    from a restricted alphabet. Longer or non-conforming runs are payload.

## Variation selectors

| Range | Count | Purpose |
| --- | --- | --- |
| `U+FE00`–`U+FE0F` | 16 | VS1–VS16. VS16 forces emoji presentation, VS15 text presentation |
| `U+E0100`–`U+E01EF` | 240 | VS17–VS256, ideographic variation sequences |

256 invisible selectors means one arbitrary byte each, chained after any base
character. This is the "emoji smuggling" scheme.

The legitimate uses are real and common: `ℹ️` is `U+2139` plus VS16, and
Japanese personal names depend on ideographic variants of kanji such as 辻 and 葛.

**Run length is what tells the two apart.** One selector after a legal base is
spelling. A run of them on the same base is a payload, because no base takes
two.

## Private-use areas

`U+E000`–`U+F8FF`, `U+F0000`–`U+FFFFD`, `U+100000`–`U+10FFFD`.

No assigned meaning, so a natural hiding place. This was the starting
hypothesis of this project, and the [baseline](../experiment/baseline.md) found
**zero occurrences** across 1,268 files.

They are not empty in practice. Nerd Fonts and Powerline put icon glyphs here,
and CJK font vendors use them for gaiji, characters with no Unicode assignment.
Deleting the range unconditionally destroys those.

## Bidirectional controls

| Codepoints | Name | Note |
| --- | --- | --- |
| `U+202D` `U+202E` | LRO, RLO overrides | The classic Trojan Source vector (CVE-2021-42574) |
| `U+202A` `U+202B` `U+202C` | LRE, RLE, PDF embeddings | Legitimate when balanced |
| `U+2066`–`U+2069` | Isolates | Legitimate in mixed-direction text |
| `U+200E` `U+200F` `U+061C` | Directional marks | Ordinary in RTL prose |

Overrides can make source code render differently than it compiles. Isolates
can do the same and are far harder to justify deleting, because mixed-direction
prose needs them.

## Space homoglyphs

Sixteen codepoints that look like a space: `U+00A0` no-break, `U+2000`–`U+200A`
the quad and em/en family, `U+202F` narrow no-break, `U+205F` medium
mathematical, `U+3000` ideographic, `U+1680` Ogham.

Choosing among them encodes information without anything looking wrong.

They are also correct typography. French requires `U+00A0` before `!` and `:`
and `U+202F` in some house styles. Chinese and Japanese use `U+3000` for
paragraph indents and clause spacing.

!!! warning "The structural case"

    `U+00A0` at the start of a YAML line is content; a plain space there is
    *indentation*. Replacing one with the other changes how the file parses. A
    cleaner that normalises spaces without knowing position can turn a valid
    config file into an invalid one.

## Other format characters

Unicode general category `Cf` is the catch-all: soft hyphen `U+00AD`,
combining grapheme joiner `U+034F`, the invisible math operators
`U+2061`–`U+2064`, interlinear annotation `U+FFF9`–`U+FFFB`, and the deprecated
controls `U+206A`–`U+206F`.

We use the whole category as the rule instead of listing each member. New
Unicode assignments are then covered without a code change.

The cost is that a few `Cf` characters are ordinary spelling in Arabic, Syriac
and Kaithi. Those have to be named as exceptions.

## What does *not* indicate AI authorship

People cite these as signs of AI writing. They are not:

- **Em dashes, curly quotes, ellipsis characters.** Typography, not marks. No
  detector should treat them as evidence, and this project does not touch them.
- **Emoji with presentation selectors.** The single most common finding in the
  baseline, and entirely ordinary.
- **A byte-order mark.** An encoding signature.
- **Non-breaking spaces in prose.** Correct typography in several languages.

## Summary: presence versus position

| Signal | Weak | Strong |
| --- | --- | --- |
| Zero-width | after a Thai or Devanagari base | run between Latin letters |
| Variation selector | one after an emoji or ideograph | run on one base |
| Tag characters | inside a complete short flag sequence | anywhere else |
| Private use | beside CJK, or in a terminal config | in ordinary English prose |
| Bidi | marks and isolates in RTL text | override in source code |
| Space homoglyph | French or CJK typography | alternating with plain spaces |

Everything in the "weak" column appeared in the baseline corpus. Nothing in the
"strong" column did.
