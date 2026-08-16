# Method

How the [baseline](baseline.md) was produced, so you can dispute it.

## Corpus selection

Every directory under one developer's `Source/` folder containing a git
repository. No filtering for interesting results, no exclusion of repositories
that turned out to be clean. Eleven repositories, 1,268 text files.

This is a **convenience sample**, and its weaknesses are worth naming:

- One machine, one person's tooling habits.
- Mixed and often unrecorded authorship. "Written with Claude Code" means the
  agent was used, not that every line came from it.
- Weighted toward Python, PowerShell and Markdown.
- It measures **agent output committed to git**, which is not the same
  distribution as text pasted out of a chat interface. Copy-paste from a
  browser is where invisible characters are most likely to survive, and it is
  not represented here.

## Scanning

Files are matched by extension against a text-format list, then decoded as
UTF-8. Undecodable files and files containing NUL in the first 8 KiB are
skipped. `.git`, `node_modules`, virtual environments, and build output are
excluded.

Each character is classified:

```
private_use | tag_chars | variation_selector | zero_width
| bidi | space_homoglyph | other_format
```

`other_format` is Unicode general category `Cf`, which makes the classifier
forward-compatible: a codepoint assigned after this was written is still
caught.

## Explanation

Each carrier is then tested against documented legitimate uses — emoji
presentation, script orthography, word separation in scripts without spaces,
encoding signatures, typographic spacing, flag sequences.

Context resolves against the nearest preceding **base**, skipping intervening
carriers. Stopping at the previous character misreads chained sequences: in
`U+2764 U+FE0F U+200D U+1F525` the joiner follows a variation selector, not the
heart.

If legitimacy cannot be determined, the carrier is counted as **unexplained**.
Ambiguity counts against the tool, not in its favour.

## Known error in the instrument

The first version of the explanation layer produced 15 false positives across 4
files, from two causes:

1. Five emoji bases outside the Symbol categories (`ℹ` `‼` `⁉` `⤴` `⤵`) were
   unrecognised, so their presentation selectors looked like payloads.
2. Context resolution stopped one character back.

Both are fixed. Both were inherited from the cleaner's own blind spots, which
is the more interesting fact: an explanation layer built from the same
assumptions as the detector shares its failures.

**Remaining known limitation.** Source that escapes a character but leaves its
combining mark literal. Two hits were `U+FE0F` after `\U0001f441` written as an
escape sequence — no base exists in the file to resolve against.

Because the instrument has a measured error rate, the unexplained count is an
**upper bound requiring review**, not a finding. Every unexplained hit in the
baseline was reviewed by hand, and all resolved to benign causes.

## Removal experiment

To measure what removal accomplishes, the hook was run over a **copy** of a
repository at a known commit, then the copy re-surveyed. The original was never
modified, which was verified afterwards by checking file sizes, carrier counts
and `git status`.

Comparing before and after on identical input isolates the effect of the
removal pass from any difference between repositories.

## A scope disagreement the experiment exposed

The survey skips `site/` as build output. The hook does not. So the survey
never counted the one file the hook damaged.

Two tools in the same repository disagreeing about which files exist is a
defect in its own right, and it is the reason the removal experiment was worth
running rather than reasoning about. Reasoning would have missed it.

## Attribution

Overt evidence only:

- declared configuration directories and instruction files;
- commit trailers, over the most recent 1,000 commits.

Deliberately **not** used: writing style, formatting habits, comment density,
commit-message phrasing. Those signals are unfalsifiable, prejudicial, and
would make the tool an accusation engine rather than a measurement.

## Reproducing

```bash
python scripts/wm-survey.py /path/to/repo --json > findings.json
```

Findings are dated and pinned to commit SHAs so a later run can be compared
rather than argued with.
