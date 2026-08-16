# Method

This page describes how we produced the numbers. Read it if you want to repeat
the work, or to dispute it.

The numbers themselves are on [Results](baseline.md). What they mean is on
[What it means](what-it-means.md).

All measurements are dated **2026-08-16**. They describe one developer's machine
on that day. Re-run them and compare.

## Two separate measurements

We ran two scans. They asked different questions, so we keep them apart and
never add their numbers together.

| Scan | Question |
| --- | --- |
| Verdict corpus | How often does the tool call a clean file a carrier? |
| Earlier private-use scan | Do private-use codepoints appear in real code? |

Corpus sizes and results are on [Results](baseline.md).

## Choosing the repositories

We scanned repositories that already existed on one developer's machine, under a
single `Source/` folder. We did not drop a repository for turning out clean, and
we did not add one for looking interesting.

The verdict corpus holds external repositories only. This project is left out
because its own test fixtures contain deliberate payloads, and they would
dominate every count. Inside each repository we excluded nothing: we used no
`--exclude` flag, so the only files left out are the ones the tool always skips.

This is a convenience sample: we used the repositories that were to hand, not a
random selection. Its weaknesses:

- One machine and one person's habits.
- Mixed authorship. "Written with Claude Code" means the agent was used. It does
  not mean every line came from the agent.
- Weighted towards Python, PowerShell and Markdown.
- It measures agent output committed to git. Text pasted out of a chat window in
  a browser is a different kind of text, and copy-paste is where invisible
  characters most often survive. That case is not covered here.

## Choosing the files

The tool walks each directory and picks files by extension from a list of text
formats. It then decodes each file as UTF-8.

It skips:

- files it cannot decode as UTF-8;
- files with a NUL byte in the first 8 KiB, which are binary;
- `.git`, `node_modules`, `.venv`, `dist`, `build`, `target`, a built `site/`,
  and the usual cache directories;
- dot files and dot directories, unless you pass `--include-hidden-files`.

A file you name on the command line is always read, whatever its extension.

!!! note "Both tools share one skip list"

    The survey once skipped `site/` while the cleaner did not, so the two
    disagreed about which files existed. They now import the same list. The
    removal experiment found this, and [Results](baseline.md) describes it.

## Classifying each character

Every invisible or format character gets one class:

```
private_use | tag_chars | variation_selector | zero_width
| bidi | space_homoglyph | other_format
```

`other_format` is Unicode general category `Cf`, the format characters. It acts
as a catch-all, so a codepoint added to Unicode after this was written is still
caught.

## Explaining a carrier

A carrier is a character you cannot see that could hide data. We test each one
against documented legitimate uses: emoji presentation, script orthography, word
separation in scripts without spaces, encoding signatures, typographic spacing
and flag sequences.

To judge a carrier we look back to the nearest visible character before it,
skipping any carriers in between. That visible character is the **base**.

Looking back only one character gets chains wrong. In
`U+2764 U+FE0F U+200D U+1F525` the joiner follows a variation selector, not the
heart.

If we cannot show that a carrier is legitimate, we count it as **unexplained**.
Ambiguity counts against the tool, not in its favour. How an unexplained carrier
becomes a verdict is described in
[Detect carriers](../usage/detect.md).

## Known error in the instrument

The first version of the explanation layer produced 15 false positives across 4
files. There were two causes:

1. Five emoji bases outside the Symbol categories (`ℹ` `‼` `⁉` `⤴` `⤵`) were
   unrecognised, so their presentation selectors looked like payloads.
2. Context resolution stopped one character back.

Both are fixed. Both came from the cleaner's own blind spots. An explanation
layer built on the same assumptions as the detector shares its mistakes.

**A gap the corpus exposed.** Source code can escape a character and leave its
combining mark literal. In one repository a real `U+FE0F` followed
`\U0001f441` written as an escape sequence. No base character existed in the
file, so the selector looked orphaned.

The layer now accepts one selector after an escaped codepoint. Only one: a
second selector would sit after the first selector, not after the escape text.
An exemption with no length limit would itself become a place to hide data.

The instrument has a known error rate. So we treat the unexplained count as an
**upper bound that needs review**, not as a finding. We reviewed every
unexplained hit by hand.

## The removal experiment

To measure what removal achieves, we copied a repository at a known commit, ran
the hook over the copy, then surveyed the copy again. The original was never
modified. We confirmed that afterwards with file sizes, carrier counts and
`git status`.

Comparing before and after on the same input isolates the effect of the removal
pass. Comparing two different repositories would not.

## Recall, and the room left for hidden data

Two benchmarks run over the same catalogue of published techniques, in
`research/recall/`:

- `benchmark.py` runs every published technique through the tool. It scores
  detection and removal separately, because they are different questions.
- `capacity.py` measures how much room an attacker still has after cleaning.
  Each channel is a real codec. It encodes a maximal payload into 4 KB of
  carrier-free ASCII text, runs the cleaner, then decodes whatever survived.
  Capacity is measured, not estimated.

## Attribution

We use overt evidence only:

- declared configuration directories and instruction files;
- commit trailers, over the most recent 1,000 commits.

We deliberately do **not** use writing style, formatting habits, comment density
or commit-message phrasing. Nobody can disprove such a signal. It is unfair to
the author, and it would turn a measurement tool into an accusation engine.

## Reproducing

Install the tool first, as described in
[Quickstart](../usage/quickstart.md).

```bash
# Is hidden data present in this tree?
wm-hook --detect /path/to/repo

# How many carriers, and how many are explained?
python scripts/wm-survey.py /path/to/repo --json > findings.json

# Skip a project's own carrier fixtures, or they dominate the numbers.
python scripts/wm-survey.py . --exclude tests/corpus/

# The two benchmarks.
python research/recall/benchmark.py
python research/recall/capacity.py
```

Findings are dated and pinned to commit SHAs. A later run can then be compared
with an earlier one instead of argued about.
