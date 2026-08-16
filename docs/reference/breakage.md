# What breaks

`wm-hook <dir>` rewrites your files in place. It has defects that damage
correct text. This page lists every one we have reproduced.

`--detect` and `--check` never write. If you only want to know whether hidden
data is present, use one of those. Then nothing on this page can happen to your
files.

Measured 2026-08-16 against the released version, v0.1.0a1. Every case here
comes from running the tool and reading the bytes afterwards.

## Triage in ten seconds

| Defect | What it damages | Status |
| --- | --- | --- |
| [Joiner at the end of a word deleted](#joiners-at-the-end-of-a-word) | Spelling in Sanskrit, Hindi, Marathi, Persian, Urdu and Arabic | Fix specified, task 2.4(c) |
| [Word separator deleted](#word-separators-in-thai-lao-and-khmer) | Word and line breaking in Thai, Lao, Khmer and Myanmar | Fix specified, task 2.4(c) |
| [Ideographic space flattened](#spaces-that-are-not-interchangeable) | Japanese and Chinese typesetting | Fix specified, task 2.4(d) |
| [No-break space flattened in prose](#spaces-that-are-not-interchangeable) | French and other typography | Fix specified, task 2.4(d) |
| [Soft hyphen and word joiner deleted](#line-break-controls) | Line breaking in typeset text | No fix specified yet |
| [Byte-order mark deleted](#the-byte-order-mark) | Any format that needs one, such as a CSV read by Excel | Flag exists, the cleaner ignores it |
| [No-break space at the start of a YAML line flattened](#yaml-a-file-that-stops-parsing) | The file stops parsing | Fix specified, task 2.4(d) |
| [No-break space used as YAML indentation flattened](#yaml-a-file-that-parses-into-a-different-shape) | The file parses into a different shape | Found during review, no fix specified yet |
| [Private-use characters deleted](#private-use-characters) | Icon fonts, and CJK gaiji characters | Fix specified, the default changes to keeping them |
| [Vendored and built files cleaned](#vendored-and-built-files) | Third-party code you did not write | No fix planned. Use `exclude:` |
| [Detection and cleaning disagree](#word-separators-in-thai-lao-and-khmer) | `--detect` calls a character legitimate, the cleaner deletes it | Fix specified, one shared rule in task 2.4(a) |
| [Files the tool never opens](#what-the-tool-never-looks-at) | You cannot tell "clean" from "never checked" | No fix specified yet |
| [The tool cannot see its own damage](#the-tool-cannot-see-its-own-damage) | A second run calls the broken file clean | Inherent. Git is your only record |

Three further defects are already gone. They were fixed by
[deleting the feature](#three-defects-fixed-by-deleting-a-feature) that caused
them.

## How to limit the damage

Do all four before you turn on the rewriting hook.

1. Commit everything first. The tool writes no `.bak` file. Git is the backup.
2. Run `pre-commit run --all-files` once, and read the whole diff. That shows
   the full blast radius in one place instead of one commit at a time.
3. Exclude built docs, vendored code, translations and byte-exact test
   fixtures. The [hook page](../usage/hook.md) has the list to copy.
4. When you are not sure, run `--detect` instead. It only reads.

## Joiners at the end of a word

A zero-width joiner (`U+200D`) or non-joiner (`U+200C`) is a character you
cannot see that controls how the letters around it are shaped.

The tool keeps one only when a letter of the same script sits on **both** sides
of it. At the end of a word nothing follows, so the rule does not fire and the
character is deleted. Several scripts put a joiner exactly there.

| Input | What it is | Result |
| --- | --- | --- |
| `क्‍ष` | ZWJ forcing the half-form of क instead of the क्ष ligature | preserved |
| `र्‍य` | eyelash reph | preserved |
| `हिन्दी` | Hindi with no joiners | preserved |
| `अयम्‌` | Sanskrit: virama plus ZWNJ, explicit halant at the end of a word | **deleted** |
| `می‌روم` | Persian: ZWNJ inside a word | preserved |
| `می‌` | Persian: ZWNJ at the end of a value | **deleted** |
| `العربية‍.` | Arabic: ZWJ before punctuation | **deleted** |

In Devanagari the non-joiner follows a virama (`U+094D`) and forces the
explicit halant form. The next consonant then does not fuse into a conjunct
ligature. That is spelling, not decoration.

### The real file this damaged

A third-party Sanskrit stemmer, `lunr.sa.min.js`, inside built MkDocs output in
a Codex-authored repository. Re-run on 2026-08-16 against this repository's own
copy of that file:

```console
$ wm-hook lunr.sa.min.js
wm-hook: lunr.sa.min.js: changed — cleaned (unicode removed=23 replaced=0)
```

4901 bytes before, 4832 after. 23 non-joiners deleted.

```text
before  'तथा अयम्〈U+200C〉 एकम्〈U+200C〉 इत्यस्मिन्〈U+200C〉 तथा तत्〈U+200C〉 वा
after   'तथा अयम् एकम् इत्यस्मिन् तथा तत् वा
```

These are stop-word tokens. The search index was built from strings that
contain the non-joiner, and the filter list no longer does.

Nothing raises an error, so search quality drops silently.

The file is also a vendored third-party asset. The tool cannot tell "invisible
character in a file the author wrote" from "invisible character in a library
the author copied in". Nothing in the file suggests AI authorship at all.

!!! danger "Any MkDocs project is affected"

    MkDocs Material ships 32 lunr search language packs. Counted in this
    repository's own `site/` directory: only the Sanskrit pack contains
    joiners, and it contains 23. The Hindi pack contains none.

    A directory walk skips `site/`, so `wm-hook .` leaves the packs alone.
    pre-commit does not walk. It passes each changed file by name, and a named
    file is always read.

    So a committed `site/` tree is still cleaned.

    Add `site/` to `.gitignore`, build it in CI, and exclude it from the hook
    as well.

## Word separators in Thai, Lao and Khmer

Thai, Lao, Khmer and Myanmar are written without spaces between words. They use
the zero-width space (`U+200B`) to mark where a word ends and a line may break.
The tool deletes it.

| Script | Input | Reported |
| --- | --- | --- |
| Thai | ภาษา 〈U+200B〉 ไทย 〈U+200B〉 สวย | `removed=2` |
| Lao | ລາວ 〈U+200B〉 ພາສາ | `removed=1` |
| Khmer | ខ្មែរ 〈U+200B〉 ភាសា | `removed=1` |
| Myanmar | မြန်မာ 〈U+200B〉 ဘာသာ 〈U+200B〉 စကား | `removed=2` |

The words are still readable. The line-breaking information is gone.

!!! danger "Detection and cleaning disagree about this file"

    The two halves of the tool give opposite answers on the same Thai file.
    `--detect` calls the separators legitimate. The cleaner deletes them.

    ```console
    $ wm-hook --detect thai.txt
          1  benign   invisible characters, all legitimate
    ```

    ```console
    $ wm-hook --check thai.txt
    wm-hook: thai.txt: changed — would clean (unicode removed=2 replaced=0)
    ```

    The first block is trimmed to the verdict line. The detector has a rule for
    word separators in these scripts, and the cleaner does not use it.

    Task 2.4(a) replaces both with one shared decision function. A disagreement
    like this then becomes impossible.

## Spaces that are not interchangeable

Sixteen codepoints look like a space. The tool replaces them with a plain
`U+0020`. Three of those replacements damage correct text.

| Input | What it is | Result |
| --- | --- | --- |
| `こんにちは　世界` | `U+3000` ideographic space between clauses | **replaced** |
| `　　这是段落开头` | two `U+3000`, the normal Chinese paragraph indent | **replaced** |
| Bonjour 〈U+00A0〉 ! | no-break space before French punctuation | **replaced** |
| 12 〈U+202F〉 345 | narrow no-break space between digit groups | **replaced** |
| `辻󠄀子` | `U+E0100` ideographic variation sequence | preserved |
| `葛︀城` | `U+FE00` after an ideograph | preserved |
| `你好，世界！` | fullwidth punctuation | preserved |
| `한국어` | Hangul | preserved |

The ideographic space is the wide space used in Japanese and Chinese
typesetting. Flattening it to `U+0020` changes how the text sets on the page.

French style requires a no-break space before `!`, `?`, `;` and `:`. After the
replacement, that punctuation can wrap onto the next line on its own. The
narrow no-break space holds digit groups together and has the same problem.

```text
Bonjour〈U+00A0〉! Attention danger〈U+00A0〉: oui.      replaced=2
12〈U+202F〉345〈U+202F〉678                            replaced=2
```

Variation selectors are handled correctly. That matters, because Japanese
personal names depend on them.

## Line-break controls

Two more characters exist only to control where a line may break. Both are
deleted.

```text
encyclo〈U+00AD〉paedia and hy〈U+00AD〉phenation    removed=2
1〈U+2060〉000 km                                  removed=1
```

The soft hyphen (`U+00AD`) marks a place where a word may be split across two
lines. The word joiner (`U+2060`) forbids a break. Deleting them changes how
the text wraps, and nothing else.

You may decide that is acceptable in a code repository. It is not acceptable in
typeset prose. No fix is specified.

## The byte-order mark

A byte-order mark (`U+FEFF`) at the very start of a file is an encoding signal.
Several formats need it. Excel needs one to read a UTF-8 CSV correctly.

The cleaner deletes it from every file:

```console
$ wm-hook --check bom_a.md
wm-hook: bom_a.md: changed — would clean (unicode removed=1 replaced=0)
$ wm-hook --check bom_b.csv
wm-hook: bom_b.csv: changed — would clean (unicode removed=1 replaced=0)
```

Reproduced on `.md`, `.txt` and `.csv` files. The behaviour does not depend on
the extension.

The newer policy object already has a `strip_bom` flag, and it defaults to off.
The shipped cleaner does not read it. A mark inside the file, rather than at
offset zero, is a genuine carrier and should be removed.

!!! warning "This clashes with `fix-byte-order-marker`"

    That pre-commit hook preserves a required mark. This one removes it.

    Whichever hook runs later wins, and your files change on every commit. Pick
    one of the two.

## YAML: a file that stops parsing

This is the worst behaviour found, because it is silent and permanent.

A `U+00A0` at the start of a YAML line is *content*. A plain space there is
*indentation*. Replacing one with the other changes how the file parses.

```text
before  jobs:\n  build:\n    steps: []\n〈U+00A0〉notify: true\n
after   jobs:\n  build:\n    steps: []\n notify: true\n
```

Reported as `replaced=1`. One character. Parsed with PyYAML before and after:

```text
before  {'jobs': {'build': {'steps': []}}, '\xa0notify': True}
after   ParserError: while parsing a block mapping
```

The file parsed before the run. It does not parse after it.

## YAML: a file that parses into a different shape

The same replacement can also leave a file that still parses. That is worse,
because no error tells you anything happened.

Here four no-break spaces are used as indentation:

```text
before  jobs:\n  build:\n〈U+00A0〉〈U+00A0〉〈U+00A0〉〈U+00A0〉steps: []\n
after   jobs:\n  build:\n    steps: []\n
```

Reported as `replaced=4`. Both versions parse. They mean different things:

```text
before  {'jobs': {'build': None}, '\xa0\xa0\xa0\xa0steps': []}
after   {'jobs': {'build': {'steps': []}}}
```

A top-level key moved inside a nested block. Nothing in the output says so.
This case was found during review and no fix is specified for it yet.

## Private-use characters

The three private-use areas are `U+E000`–`U+F8FF`, `U+F0000`–`U+FFFFD` and
`U+100000`–`U+10FFFD`. They have no assigned meaning, so the current default
deletes them.

They are not empty in practice. Nerd Fonts and Powerline put icon glyphs there.
CJK font vendors put gaiji there, which are characters Unicode has not
assigned.

```text
Deploy now.〈U+E000〉〈U+E001〉〈U+F8FF〉    removed=3
日本〈U+F0030〉語                          removed=1
```

The default is specified to change to keeping them. Until it does, exclude your
terminal configuration and any CJK text that uses gaiji.

## Vendored and built files

The tool reads text. It has no idea who wrote it.

A vendored library, a generated file and a byte-exact test fixture all look
like ordinary text to it. The Sanskrit stemmer above is the clearest case: zero
watermarks removed, one third-party library damaged. That removal run is
described in [Results](../experiment/baseline.md).

No fix is planned, because there is no reliable signal to fix it with. Scope
the hook with `exclude:` instead. The [hook page](../usage/hook.md) lists the
paths to exclude.

## What the tool never looks at

This is the opposite problem. These files are never checked, and the exit code
does not say so.

| Skipped | When | Exit code |
| --- | --- | --- |
| Any extension outside a fixed list of 40 | Walking a directory | `0` |
| Dot files and dot directories | Walking a directory, unless `--include-hidden-files` | `0` |
| `.git`, `node_modules`, `.venv`, `dist`, `build`, `target`, `site` and cache directories | Walking a directory | `0` |
| A file with a NUL byte in its first 8 KiB | Always | `0` when cleaning, `2` under `--detect` |
| A file larger than 256 MiB | Always | `2` |

Two consequences worth knowing.

**A directory walk and pre-commit do not cover the same files.** The walk
filters by extension and skips those directories. pre-commit passes every
changed file by name, and a named file is always read whatever its extension.

So `wm-hook --detect .` can look clean while the hook rewrites files the walk
never saw. A `.csv` file is one example: skipped by the walk, cleaned when
named.

**A skipped file looks like a clean file.** Cleaning mode exits `0` for both.

```console
$ wm-hook --check utf16.txt
wm-hook: utf16.txt: skipped — looks like binary data (contains NUL bytes) — left untouched
$ echo $?
0
```

That file was UTF-16 text holding a real zero-width payload. UTF-16 stores
ASCII with NUL bytes, so every UTF-16 document is skipped this way. `--detect`
handles it better: it exits `2` and prints an error instead of counting the
file as clean.

Bytes that are not valid UTF-8 are a separate case. Those files are scanned,
and the undecodable bytes survive the rewrite unchanged.

## The tool cannot see its own damage

Once a file has been rewritten, the tool has no memory of what it did.

Run it a second time on the YAML file it just broke. It reports nothing and
exits `0`. `--detect` reports the same file as `none`, meaning no invisible
characters at all.

Both statements are true about the file as it now stands. Neither tells you the
file is broken.

This is why step 1 of [how to limit the damage](#how-to-limit-the-damage) is to
commit first. The diff is the only record.

## Three defects fixed by deleting a feature

Frontmatter key removal is gone. Deleting it resolved three defects at once,
recorded here because older documentation described them.

| Defect | Status |
| --- | --- |
| A value that merely mentioned a vendor deleted the whole key, so `title: Comparing Claude and Gemini` lost its title | Fixed, feature deleted |
| CRLF frontmatter blocks were rebuilt with line feeds, rewriting files that held no marks at all | Fixed, feature deleted |
| A leading `---` thematic break was read as a frontmatter delimiter, deleting body prose | Fixed, feature deleted |

The second one is the "six churned files" in the
[Results](../experiment/baseline.md) removal run. A CRLF file with frontmatter
is now left byte-identical, verified on 2026-08-16.

Frontmatter *recognition* stays. The tool still locates the block, because a
space homoglyph at the start of a YAML line is structurally significant. See
`.kiro/steering/scope.md`.

## Reproducing all of this

Every case above came from directories of small fixtures. One of them:

```console
$ wm-hook --check .
wm-hook: cjk.txt: changed — would clean (unicode removed=0 replaced=3)
wm-hook: conf.yaml: changed — would clean (unicode removed=0 replaced=1)
wm-hook: french.txt: changed — would clean (unicode removed=0 replaced=2)
wm-hook: gaiji.txt: changed — would clean (unicode removed=1 replaced=0)
wm-hook: nested.yaml: changed — would clean (unicode removed=0 replaced=4)
wm-hook: payload.md: changed — would clean (unicode removed=8 replaced=0)
wm-hook: pua.txt: changed — would clean (unicode removed=3 replaced=0)
wm-hook: sa_stopwords.js: changed — would clean (unicode removed=3 replaced=0)
```

`payload.md` is the one correct result in that list. It held a real zero-width
binary run of eight characters. The other seven files are defects on this page.

Three files in that directory are missing from the output. The tool left them
alone, and that is correct: Devanagari with joiners inside words, CJK variation
sequences, and a CRLF file with frontmatter.

Right-to-left marks, balanced embeddings and isolates are also left alone. A
right-to-left override in source code is correctly removed.

```console
uv run --python 3.12 wm-hook --check path/to/file    # report, never writes
uv run --python 3.12 wm-hook path/to/file            # rewrite in place
```
