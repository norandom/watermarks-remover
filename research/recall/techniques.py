#!/usr/bin/env python3
"""The catalogue of published Layer A carrier techniques, as test vectors.

Each entry is a construction, a payload, and an expectation. The point is to
answer "what fraction of known techniques do we catch" with a number instead of
a shrug.

An entry declares two independent expectations:

  detect  -- the scanner should surface it as a finding
  remove  -- the cleaner should strip it under the stated policy

They come apart. Private-use characters are detectable but preserved by default
(Requirement 3.5). A single variation selector after a legal base is neither
detected nor removed, correctly. Recording both keeps the benchmark honest
about which is which.

`residue` names codepoints that legitimately survive removal, so a partial
strip is not scored as a failure when partial is the correct answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Technique:
    key: str
    name: str
    reference: str
    payload: str
    #: Full document as it would appear in a repository.
    text: str
    detect: bool = True
    remove: bool = True
    #: Codepoints that may legitimately remain after a correct clean.
    residue: tuple[int, ...] = ()
    #: Non-default policy under which `remove` is expected to hold.
    policy: dict = field(default_factory=dict)
    note: str = ""


def _tags(s: str) -> str:
    return "".join(chr(0xE0000 + ord(c)) for c in s)


def _zw_bits(bits: str) -> str:
    return "".join("​" if b == "0" else "‌" for b in bits)


TECHNIQUES: tuple[Technique, ...] = (
    Technique(
        key="zw_binary",
        name="Zero-width binary encoding",
        reference="ZWSP/ZWNJ as 0/1; the oldest and most widely deployed scheme",
        payload="01001101",
        text="The release ships on Tuesday." + _zw_bits("01001101") + "\n",
    ),
    Technique(
        key="zw_joiner_channel",
        name="Zero-width joiner and word-joiner channel",
        reference="U+200D and U+2060 used as carriers between Latin letters",
        payload="4 bits",
        text="Deploy‍ment sched⁠ule con‍firm⁠ed.\n",
    ),
    Technique(
        key="tag_bare",
        name="Unicode Tag block, bare",
        reference="U+E0000-E007F mirrors ASCII invisibly (ASCII smuggling)",
        payload="gen=2026-08-16",
        text="# Release notes\n\nShipped today." + _tags("gen=2026-08-16") + "\n",
    ),
    Technique(
        key="tag_behind_flag",
        name="Tag block hidden behind a flag emoji",
        reference="Overlong payload between U+1F3F4 and U+E007F, abusing the "
                  "subdivision-flag exemption",
        payload="secret-payload",
        text="Status \U0001F3F4" + _tags("secret-payload") + "\U000E007F ok\n",
    ),
    Technique(
        key="vs_bmp_run",
        name="Variation selector run, VS1-VS16",
        reference="U+FE00-FE0F chained after one base; one byte per selector",
        payload="3 bytes",
        text="日︀︁︂ build notes\n",
        residue=(0xFE00,),
        note="the first selector after a legal ideographic base is orthography",
    ),
    Technique(
        key="vs_supplement_run",
        name="Variation selector run, VS17-VS256",
        reference="U+E0100-E01EF; the emoji-smuggling scheme, 240 selectors",
        payload="4 bytes",
        text="本\U000E0100\U000E0101\U000E0102\U000E0103 notes\n",
        residue=(0xE0100,),
    ),
    Technique(
        key="vs_orphan",
        name="Orphan variation selectors",
        reference="Selectors with no legal base at all",
        payload="3 bytes",
        text="plain text️︎\U000E0105 here\n",
    ),
    Technique(
        key="private_use",
        name="Private-use area payload",
        reference="U+E000-F8FF and planes 15-16 have no assigned meaning",
        payload="5 codepoints",
        text="Deploy now.\U000F0000\U0010FFFD\n",
        remove=False,
        policy={"strip_private_use": True},
        note="preserved by default (Req 3.5): this range carries icon-font "
             "glyphs and CJK gaiji",
    ),
    Technique(
        key="bidi_override",
        name="Bidi override, Trojan Source",
        reference="Boucher & Anderson, CVE-2021-42574; U+202D/U+202E",
        payload="source reorder",
        text='if (level == "user") {‮ // ‬admin only\n',
    ),
    Technique(
        key="bidi_isolate",
        name="Bidi isolate, Trojan Source variant",
        reference="U+2066-U+2069 achieve a similar reorder",
        payload="source reorder",
        text="x = 1 /* ⁦ if (a) ⁩ */\n",
        remove=False,
        policy={"strip_bidi": True},
        note="isolates are legitimate in mixed-direction prose and are "
             "preserved by default (Req 3.7)",
    ),
    Technique(
        key="space_nbsp",
        name="No-break space substitution",
        reference="U+00A0 for U+0020 encodes one bit per space",
        payload="4 bits",
        text="the quick brown fox jumps over the dog\n",
    ),
    Technique(
        key="space_thin",
        name="Thin and hair space substitution",
        reference="U+2009/U+200A/U+202F are visually near-identical to U+0020",
        payload="3 bits",
        text="alpha beta gamma delta\n",
    ),
    Technique(
        key="soft_hyphen",
        name="Soft hyphen insertion",
        reference="U+00AD renders as nothing unless a line breaks there",
        payload="3 positions",
        text="encyclo­pedia refer­ence mate­rial\n",
    ),
    Technique(
        key="cgj",
        name="Combining grapheme joiner",
        reference="U+034F has no visible effect in most contexts",
        payload="2 positions",
        text="data͏base sche͏ma\n",
    ),
    Technique(
        key="interlinear",
        name="Interlinear annotation anchors",
        reference="U+FFF9-U+FFFB, deprecated and invisible",
        payload="1 annotation",
        text="config￹hidden￺value￻ here\n",
    ),
    Technique(
        key="deprecated_format",
        name="Deprecated format controls",
        reference="U+206A-U+206F, symmetric swapping and digit shapes",
        payload="3 codepoints",
        text="total⁪ count⁬ value⁮\n",
    ),
    Technique(
        key="mongolian_vs",
        name="Mongolian vowel separator",
        reference="U+180E, invisible and outside its own script",
        payload="2 positions",
        text="build᠎ step᠎ two\n",
    ),
    Technique(
        key="cyrillic_homoglyph",
        name="Cyrillic homoglyph substitution",
        reference="U+0430 for 'a', U+0435 for 'e', and friends",
        payload="3 substitutions",
        text='HOST = "pаypаl.cоm"\n',
        remove=False,
        policy={"aggressive_homoglyphs": True},
        note="detected via mixed-script analysis; rewriting stays off by "
             "default because the false-positive cost on multilingual source "
             "is unacceptable for an unattended edit",
    ),
    Technique(
        key="fullwidth_homoglyph",
        name="Fullwidth Latin substitution",
        reference="U+FF21-U+FF5A render as wide but read as Latin",
        payload="2 substitutions",
        # Mixed within the token, which is what makes it an attack. A wholly
        # fullwidth token is just fullwidth text and is correctly ignored.
        text="import Ａuth from './ｍodule'\n",
        remove=False,
        policy={"aggressive_homoglyphs": True},
    ),
    Technique(
        key="hangul_filler",
        name="Hangul filler as an invisible character",
        reference="U+3164 and U+FFA0 render as nothing but are category Lo",
        payload="2 positions",
        text="heㅤllo worﾠld\n",
        note="CLOSED. Category Lo, so the old category-Cf rule could never "
             "see it; the strip rule now derives from "
             "Default_Ignorable_Code_Point, which covers it. Was 728 bits/KB, "
             "84% of residual capacity",
    ),
    Technique(
        key="braille_blank",
        name="Braille pattern blank",
        reference="U+2800 renders as whitespace, category So",
        payload="2 positions",
        text="value⠀here⠀now\n",
        detect=False,
        remove=False,
        note="category So: not a format character. Known gap",
    ),
    Technique(
        key="line_separator",
        name="Line and paragraph separator",
        reference="U+2028/U+2029 break lines in some renderers, not others",
        payload="2 positions",
        text="first second third\n",
        detect=False,
        remove=False,
        note="categories Zl/Zp. Known gap, and removal would alter layout",
    ),
    Technique(
        key="trailing_whitespace",
        name="Trailing-whitespace count encoding",
        reference="Number of trailing spaces per line carries bits",
        payload="3 bits",
        text="line one   \nline two \nline three    \n",
        detect=False,
        remove=False,
        note="out of scope by design: this is a whitespace *count*, not a "
             "codepoint. Pair with a trailing-whitespace hook",
    ),
    Technique(
        key="bom_interior",
        name="Interior byte-order mark",
        reference="U+FEFF anywhere but offset zero is a carrier",
        payload="2 positions",
        text="name,value\nalpha,﻿one\nbeta,﻿two\n",
    ),
)


def by_key() -> dict[str, Technique]:
    return {t.key: t for t in TECHNIQUES}
