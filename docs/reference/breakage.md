# What breaks

**Measured 2026-08-16.** A tool that rewrites source files in place owes you an
honest account of when it is wrong. This page is that account.

Every case below was reproduced by running the shipped hook against real
content, not reasoned about.

## The case that matters most

A third-party Sanskrit stemmer, checked into a Codex-authored repository as
part of built MkDocs output.

**Before** — `site/assets/javascripts/lunr/min/lunr.sa.min.js`:

```
generateStopWordFilter('तथा अयम्‌ एकम्‌ इत्यस्मिन्‌ तथा तत्‌ वा अयम्‌ ...
```

**After** the hook:

```
generateStopWordFilter('तथा अयम् एकम् इत्यस्मिन् तथा तत् वा अयम् ...
```

`165 bytes -> 150 bytes. 5 zero-width non-joiners removed.`

### Why this is damage

Each `U+200C` sat immediately after `U+094D DEVANAGARI SIGN VIRAMA`. The virama
suppresses a consonant's inherent vowel; a ZWNJ after it forces the **explicit
halant** form rather than letting the next consonant fuse into a conjunct
ligature. It is orthography.

Here it is also *data*. These are stop-word tokens. The search index was built
against strings containing the ZWNJ; the filter list no longer does. Nothing
errors. Search quality silently degrades.

### Why it is not a watermark

It is a vendored third-party asset. The hook cannot distinguish "invisible
character in a file the author wrote" from "invisible character in a library
the author vendored". Nothing in the file indicates AI authorship at all.

!!! danger "This affects any MkDocs project"

    MkDocs Material ships **32 lunr search language packs**. If you build the
    site and commit `site/`, this hook will strip characters from them.

    Two mitigations, and take both: `.gitignore` your `site/` directory and
    build it in CI, and exclude vendored or generated assets from the hook.

## Devanagari, tested directly

Relevant if you work in Hindi, Marathi or Sanskrit.

| Input | What it is | Result |
| --- | --- | --- |
| `क्‍ष` | ZWJ forcing the half-form of क rather than the क्ष ligature | preserved |
| `र्‍य` | eyelash reph | preserved |
| `हिन्दी` | no joiners | preserved |
| `अयम्‌` | virama + ZWNJ, explicit halant | **stripped** |

The pattern: a joiner is kept only when it has a same-script letter on **both**
sides. `अयम्‌` ends on the ZWNJ, so nothing follows it, the guard does not fire,
and it goes.

Word-final is exactly where Sanskrit puts it. Hindi's own lunr stop-word pack
contains zero joiners and is unaffected; Sanskrit's contains 23.

## CJK

| Input | What it is | Result |
| --- | --- | --- |
| `こんにちは　世界` | `U+3000` ideographic space between clauses | **replaced with ASCII space** |
| `　　这是段落开头` | two `U+3000`, the conventional Chinese paragraph indent | **replaced** |
| `辻󠄀子` | `U+E0100` ideographic variation sequence | preserved |
| `葛︀城` | `U+FE00` after an ideograph | preserved |
| `你好，世界！` | fullwidth punctuation | preserved |
| `한국어` | Hangul | preserved |
| `日本󠀰語` | private-use gaiji beside CJK | **deleted** |

Ideographic space is the significant one. It is the normal wide space in
Japanese and Chinese typesetting, and flattening it to `U+0020` changes how the
text sets. The variation-selector cases are handled correctly, which matters
because Japanese personal names depend on them.

## Structural damage to configuration files

The worst behaviour found, because it is silent and permanent.

**Before** — a YAML file where `U+00A0` sits at the start of a line:

```yaml
jobs:
  build:
    steps: []
 notify: true      # this line starts with U+00A0, not a space
```

That parses. `notify` is a top-level key whose name begins with a no-break
space.

**After** the hook, the no-break space becomes a plain space. The file no
longer parses at all, and if the affected key had been an AI provenance key,
the hook's own scanner can never see it again, because it now looks like an
indented continuation line.

A second run reports `clean`. The file is broken and the mark is permanent.

## Files rewritten with nothing to remove

CRLF markdown with YAML frontmatter is rewritten even when it contains no
carriers:

```
before: ---\r\ntitle: Hi\r\n---\r\n\r\nbody\r\n
after:  ---\ntitle: Hi\n---\n\r\nbody\r\n
```

The frontmatter block is rebuilt with LF joins while the body keeps CRLF,
producing mixed line endings and a diff on every frontmatter line. Reported as
`unicode removed=0 replaced=0`.

## Content deleted by name matching

A frontmatter value that merely mentions a vendor deletes the whole key:

```yaml
---
title: Comparing Claude and Gemini
---
```

The title is removed. If it was the only key, the entire frontmatter block goes
with it.

## Status

| Behaviour | State |
| --- | --- |
| Word-final joiner stripped | fix specified, `watermark-removal` 2.4(c) |
| Ideographic space flattened | fix specified, 2.4(d) |
| Private use deleted by default | fix specified, default flips to preserve |
| Column-0 NBSP corrupts YAML | fix specified, 2.4(d) |
| NBSP deeper in YAML indentation | **found during review, not yet specified** |
| CRLF frontmatter churn | fix specified, 3.1 |
| Frontmatter value-hit deletion | fix specified, 2.5 |

Until those land, the shipped hook has the behaviour documented above. Scope it
with `exclude:` and run
[`pre-commit run --all-files`](../usage/hook.md) once before trusting it.
