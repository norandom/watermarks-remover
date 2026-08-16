# Detect carriers

`wm-hook --detect` answers one question: is a carrier present? A carrier is a
character you cannot see that hides data. `--detect` only reads files, and it
never writes.

For install and a first run, see [Quickstart](quickstart.md).

## Which files are scanned

Point it at a directory and it walks the tree. It skips `.git`,
`node_modules`, `.venv`, `dist`, `build`, `target` and a built `site/`.

Dot files and dot directories are skipped too. Without that, scanning a project
root reports on `.claude/`, `.kiro/` and every other tool's configuration. On
this repository that was 74 of 161 files, none of them written by the author.

```bash
wm-hook --detect .                        # your files
wm-hook --detect --include-hidden-files . # plus .claude/, .kiro/ and friends
```

A file you name directly is always scanned, whatever its extension and whether
or not it starts with a dot. Asking for a specific file is an instruction.

## The five verdict levels

Every file gets one level. Two of them are positives.

| Level | What it means | Exit code |
| --- | --- | --- |
| `none` | No invisible characters at all. | 0 |
| `benign` | Invisible characters are present, and the tool explains all of them. | 0 |
| `anomaly` | Invisible characters are unexplained, but isolated and unstructured. | 0 |
| `carrier` | Unexplained characters form a structure. Something embedded hidden data. | 1 |
| `payload` | The same, and the hidden data decodes into readable text. | 1 |

Exit code `2` means a file could not be read, or that no text files were found
at all. The second case is an error on purpose. A scan that never happened must
not report "0 of 0 files are clean".

A positive says that something embedded hidden data. It does not say who, and
it does not say an AI wrote the text. A clean result says even less: see
[What it means](../experiment/what-it-means.md).

## Why structure decides the verdict, not presence

Almost every invisible character in a real source tree is legitimate. Counting
characters alone reports roughly a hundred times more hits than the truth.

So the tool first explains what it can, using the rules in
[Invisible characters](../reference/characters.md). Whatever is left over goes
into a score.

| Signal | Weight | Why it is not an accident |
| --- | --- | --- |
| `run` | 2 | Debris is isolated. A payload is a block of characters in a row. |
| `binary_alphabet` | 3 | Exactly two codepoints repeating is a bit stream. |
| `byte_aligned` | 1 | A run length that divides by 8 was packed into bytes. |
| `latin_context` | 2 | Joiners belong in Indic, Arabic and Thai text. They never belong between two ASCII letters. |
| `periodic` | 2 | Evenly spaced marks encode one mark per token. |
| `tag_outside_flag` | 3 | The Unicode tag block has one legitimate use, and that use is already exempt. |
| `private_use_in_text` | 2 | These codepoints have no assigned meaning at all. |

The weights that fire are added together:

| Score | Level | Confidence |
| --- | --- | --- |
| 4 or more | `carrier` | high |
| 2 or 3 | `carrier` | moderate |
| 1 or less | `anomaly` | low |

There is one shortcut. If the hidden data decodes, the level is `payload` and
the score is not used. Confidence then comes from the decoder: `high` if the
scheme is confirmed, `moderate` if it is only probable.

## Why the anomaly tier exists

An anomaly is an unexplained character with no structure around it. Copy-paste
debris from a web page, an editor artifact and a stray BOM inside a string
literal all look like this.

They are worth removing. They do not support any conclusion.

```console
$ wm-hook --detect -v pasted.md
ANOMALY  pasted.md: unexplained carrier, but no structure to call it payload
         1 carrier(s), 0 explained, 1 unexplained
         confidence: low; capacity 1 bits
```

The tool also prints a paragraph after each file saying what the level means,
and a run summary at the end. Both are cut from the console blocks on this page.

Without this tier, every stray character becomes a finding, and most findings
would be wrong. In the 1,155-file corpus the two unexplained characters both
landed here, and zero carriers were established: see
[Results](../experiment/baseline.md).

## Worked example

`-v` prints the reasons: the signals from the table above, with their weights.

```console
$ wm-hook --detect -v changelog.md stemmer.py
CARRIER! changelog.md: covert carrier present, and it decodes
         24 carrier(s), 0 explained, 24 unexplained
         + run (+2): 24 consecutive unexplained zero_width at offset 33
         + binary_alphabet (+3): run of 24 uses exactly two codepoints (U+200B U+200C) -- a bit stream
         + byte_aligned (+1): run length 24 is a multiple of 8
         > zero-width binary (ZWSP/ZWNJ) @33 [probable]
           'v41'
         confidence: moderate; capacity 24 bits
CLEAN    stemmer.py: invisible characters present, all legitimate
         1 carrier(s), 1 explained, 0 unexplained
         confidence: n/a; capacity 0 bits
```

`stemmer.py` holds a Devanagari joiner after a virama. That joiner is correct
spelling, so the file is `benign`. Getting that right is harder than catching
the file that decodes.

## JSON output

`--detect --json` prints an array to standard output, one object per file. The
exit codes are the same. A clean file still gets an object, with `0` counters
and empty arrays.

| Field | Type | Use it for |
| --- | --- | --- |
| `path` | string | The file that was scanned. |
| `level` | string | One of the five levels above. |
| `carrier_present` | boolean | True only for `carrier` and `payload`. Branch on this field. |
| `confidence` | string | `high`, `moderate`, `low` or `n/a`. |
| `carriers`, `explained`, `unexplained` | integer | Counts of invisible characters. |
| `score` | integer | The total from the weights table. |
| `bits_available` | integer | How many bits the unexplained characters could hold. |
| `by_class` | object | Unexplained characters grouped by family, for example `zero_width`. |
| `evidence` | array | One entry per signal that fired, with `name`, `weight` and `detail`. |
| `payloads` | array | One entry per decoded payload, with `scheme`, `decoded`, `offset` and `identifiers`. |
| `headline`, `means` | string | Text for people to read. Do not parse these. |
| `error` | string | Present only when the file could not be read. No other field is present then. |

!!! warning "`--detect` never writes. Bare `wm-hook` does."

    `wm-hook <dir>` rewrites the whole tree in place. It damages Devanagari
    spelling and CJK typography. Read
    [What breaks](../reference/breakage.md) before you run it.
