# What we found

The measurements on this page were taken on **2026-08-16**, on one developer's
workstation. They are a snapshot, not a standing claim about coding agents.
Re-run the tools and compare.

This page reports numbers. For what they prove and what they do not, read
[What it means](what-it-means.md). For how they were produced, read
[Method](method.md).

## The short version

| Measurement | Result |
| --- | ---: |
| Files scanned for hidden data, in 8 repositories | 1,155 |
| Files where hidden data was established | **0** |
| Files reported as an anomaly | 1 |
| Upper bound on the false-positive rate per file, 95% confidence | **0.26%** |
| Files scanned for private-use codepoints, in 11 repositories | 1,268 |
| Private-use codepoints found | **0** |
| Published hiding techniques the detector catches | **21 of 21** |
| Room left for hidden data after cleaning | 142 bits/KB, down from 2,405 |

!!! warning "Two corpora. Do not add them together."

    The 1,155-file run and the 1,268-file run are separate measurements. They
    used different tools, different file lists and different repositories, and
    they answer different questions. Treat them as two results, never as one.

## False positives: 8 repositories, 1,155 files

Every text file was scanned. Nothing was excluded.

| Repository | Files | Carriers | Unexplained | Established |
| --- | ---: | ---: | ---: | ---: |
| PowerShell (Codex) | 707 | 6 | 0 | **0** |
| x_likes_scraper (Claude) | 195 | 21 | 2 | **0** |
| Skills | 120 | 0 | 0 | **0** |
| ragflow-claude-desktop-local-mcp | 57 | 2 | 0 | **0** |
| malware_hashes | 46 | 0 | 0 | **0** |
| spec-kit-ears-tdd | 23 | 0 | 0 | **0** |
| nvim-simple | 5 | 0 | 0 | **0** |
| WindowsHardeningScript | 2 | 0 | 0 | **0** |
| **Total** | **1155** | **29** | **2** | **0** |

A carrier is an invisible character that could hide data. Most carriers are
legitimate, so the Carriers column is not a count of findings. The tool
established hidden data in **no file at all**.

Zero positives in 1,155 files bounds the false-positive rate at **0.26%** per
file with 95% confidence. That is the rule of three: 3 divided by 1,155.

Two of these repositories were written almost entirely by coding agents. The
Codex one has 707 files and the Claude one has 195 files. Both scan clean.

What that does and does not show is in [What it means](what-it-means.md).

### The two unexplained characters

Two invisible characters in the whole corpus have no legitimate explanation.
Both sit in the same file. The tool reports that file as an `anomaly`, which is
not a positive result and does not set the exit code.

These are the per-file lines from a real run. It covers that file and the other
file the survey once flagged. The plain-English paragraph printed under each
verdict is trimmed here for length:

```console
$ wm-hook --detect -v tests/mcp/synthesis/test_mindmap.py tests/mcp/test_tree.py
ANOMALY  tests\mcp\synthesis\test_mindmap.py: unexplained carrier, but no structure to call it payload
         2 carrier(s), 0 explained, 2 unexplained
         confidence: low; capacity 2 bits
CLEAN    tests\mcp\test_tree.py: invisible characters present, all legitimate
         4 carrier(s), 4 explained, 0 unexplained
         confidence: n/a; capacity 0 bits
```

**The anomaly is a byte-order mark inside a test about byte-order marks.** The
test builds a string ending in `U+FEFF` and asserts that the renderer strips it.
The input for a BOM test has to be a BOM. The tool cannot know that, so it
reports the file honestly as unexplained and stops there.

**A second case was a half-escaped emoji, and it is now explained.** The source
wrote the base character as the ASCII escape `\U0001f441`. It then left the
variation selector after it as a real codepoint.

No base character existed in the file, so the selector looked orphaned. That gap
is now closed. This is why `test_tree.py` above reports 4 explained and 0
unexplained.

The fix covers one selector, not a run of them. An exemption with no length
limit would become a hiding place of its own.

One limitation stays. Source code can escape a character and still leave the
mark that follows it as a real codepoint. No context check can explain that
mark, because the base it belongs to is not in the file.

This is the shape a real false positive takes, and it is not rare.

## Detection: recall, and the room left for hidden data

| Measurement | Value |
| --- | ---: |
| Published hiding techniques detected | **21 of 21** |
| Room left for hidden data after cleaning | **142 bits/KB** |
| The same figure before the scope was narrowed | 2,405 bits/KB |

Recall is measured in `research/recall/`. The capacity figure is how much data
could still survive a cleaning pass, per kilobyte of text.

The widest single channel closed was the subdivision-flag exemption, worth
1,535 bits/KB on its own. It waved through tag characters of any length as long
as a flag emoji came first.

## Private-use codepoints: 11 repositories, 1,268 files

This was the first measurement, and it is separate from the one above.

The starting idea was that agents hide payloads in private-use or unassigned
Unicode space, where nothing legitimate lives.

**Private-use codepoints found across the whole corpus: zero.** Not few. None.
That covers all three private-use areas: `U+E000`–`U+F8FF`, `U+F0000`–`U+FFFFD`
and `U+100000`–`U+10FFFD`.

The 11 repositories are mixed work: some written with Claude Code, one with a
Codex spec-kit workflow, several by hand, two third-party. The count of 1,268
files is after excluding `.git`, `node_modules`, virtual environments and build
output.

## Two agent-written repositories, side by side

Both repositories are public, and both are real work rather than test material.

!!! info "Provenance of this measurement"

    Run **2026-08-16T11:52:44Z**, against these exact commits:

    | Repository | Commit | Commit date |
    | --- | --- | --- |
    | `norandom/DataWorkStation_Powershell` | `12700f6` | 2026-08-16 |
    | `norandom/x_likes_scraper` | `48d1674` | 2026-08-14 |

    Both working trees were clean, so the numbers describe those commits and can
    be reproduced from them.

| | [`DataWorkStation_Powershell`](https://github.com/norandom/DataWorkStation_Powershell) | [`x_likes_scraper`](https://github.com/norandom/x_likes_scraper) |
| --- | --- | --- |
| Written with | Codex, spec-kit workflow | Claude Code |
| Files scanned | 703 | 195 |
| Files with any carrier | 3 (0.43%) | 8 (4.1%) |
| Carriers found | 6 | 21 |
| Explained as legitimate | 6 (100%) | 17 (81%) |
| Flagged unexplained | 0 | 4 |
| **True candidates after review** | **0** | **0** |
| Config on disk | `.specify/`, `.agents/` | `.claude/`, `CLAUDE.md` |
| Commit trailers | **0 of 19** | 117 of 141 (83%) |

All six carriers in the Codex repository are `U+FE0F VARIATION SELECTOR-16`,
the character that forces emoji presentation. They follow `⚠` and similar signs
in markdown templates. That is ordinary content.

The four flags in the Claude repository were reviewed by hand and all four are
benign. Two are the byte-order marks described above. Two are the half-escaped
emoji, which the tool now explains, so two unexplained characters remain.

The survey counted 703 files in the Codex repository and the detector counted
707. The two tools use different file lists. Same repository, different
instruments.

### What the comparison does not show

It does not show that Codex is tidier. Carrier density (0.43% against 4.1%)
tracks **emoji use in documentation**.

The Codex repository is 703 files that are largely generated MkDocs output. The
Claude repository is 195 files with more hand-written markdown containing emoji.
Different content, not different behaviour.

One behavioural difference is real: attribution. Codex left **zero** commit
trailers across 19 commits. Claude left them on 83% of 141.

That is a configuration choice, not a property of the model.

## What the removal pass accomplished

The hook was run over a copy of `DataWorkStation_Powershell` at `12700f6`, so
nothing was risked.

**576 files processed. 7 modified.**

| File | Delta | Reported by the hook |
| --- | --- | --- |
| `site/.../lunr.sa.min.js` | −69 bytes | `removed=23` |
| `.specify/presets/ears-tdd/.composed/speckit.implement.md` | −8 | `removed=0 replaced=0` |
| `.specify/presets/ears-tdd/.composed/speckit.plan.md` | −8 | `removed=0 replaced=0` |
| `.agents/skills/speckit-ears-validate-validate/SKILL.md` | −7 | `removed=0 replaced=0` |
| `.specify/presets/ears-tdd/.composed/speckit.tasks.md` | −7 | `removed=0 replaced=0` |
| `.specify/presets/ears-tdd/.composed/speckit.specify.md` | −4 | `removed=0 replaced=0` |
| `.specify/templates/tasks-template.md` | −1 | `removed=0 replaced=0` |

Six of the seven shrank while the hook reported removing nothing. That is the
CRLF frontmatter defect. The block is rebuilt with LF line joins, so every
frontmatter line loses one byte, in files that held no carriers at all.

The seventh is a Sanskrit stemmer. The hook damaged its orthography. See
[What breaks](../reference/breakage.md) before running the removal pass on
anything.

### Re-measure after removal

| | Before | After |
| --- | --- | --- |
| Files with any carrier | 3 (0.43%) | 3 (0.43%) |
| Carriers found | 6 | 6 |
| Explained | 6 | 6 |
| **Watermark candidates** | **0** | **0** |

Nothing changed. The removal pass removed zero watermarks, corrupted one
third-party library, and churned six files that were already clean.

!!! warning "A scope disagreement this exposed"

    The survey skips `site/` as build output. The hook does not. So the survey
    never counted the one file the hook damaged, and its "0 candidates" figure
    did not cover that file.

    Two tools in the same repository disagreeing about which files exist is its
    own defect.

## Attribution works, but only from overt evidence

Nothing was hidden in the text of this corpus. So attribution has to come from
what the agents declare about themselves.

| Evidence | Claude | Codex |
| --- | --- | --- |
| Config directory on disk | `.claude/`, `CLAUDE.md` | `.specify/`, `.agents/` |
| Commit trailers | 8 of 9 commits in this repository (88.9%); 117 of 141 in another | **0 of 18 commits** |

Both signals disappear with `rm -rf .claude` and a rebase. Nothing survives a
determined cleanup, because nothing is hidden.

Trailer counts also misattribute mixed repositories. One repository here shows
117 Claude trailers and 25 Codex trailers. Another shows 55 and 5.

Both agents worked on both repositories. Reading the larger number as "the
author" would be wrong.

## The survey's own error rate

The survey has to tell a legitimate carrier from a suspicious one. The first
version of the tool got that wrong 15 times across 4 files.

After the fixes, false positives on this repository fell from 15 to 5. The
remaining 5 are worked examples inside the documentation itself, so they are
real carriers sitting in prose and flagging them is correct. The two causes of
the original 15 are listed in [Method](method.md).

## This repository's own text

An inventory of every codepoint in this repository's agent-written source and
prose, excluding its carrier test fixtures:

| | |
| --- | ---: |
| Characters | 604,030 |
| Non-ASCII | 1,055 (**0.17%**) |
| Invisible (`Cf`/`Co`) | about 40, each a documented example in the detector's own code |
| Most common non-ASCII | em dash (314), rightwards arrow (127), box drawing (101) |

This repository is agent-written and it scans clean. Those two facts do not
conflict. The reason is in [What it means](what-it-means.md).

## How to reproduce

Scan for hidden data. This never writes:

```bash
uvx --from git+https://github.com/norandom/watermarks-remover \
    wm-hook --detect /path/to/repo
```

Count carriers and how many were explained:

```bash
python scripts/wm-survey.py /path/to/repo
python scripts/wm-survey.py /path/to/repo --json > baseline-$(date +%F).json
```

Exclude a project's own carrier fixtures, or they dominate every count:

```bash
python scripts/wm-survey.py . --exclude tests/corpus/
```

Other ways to install are in [Quickstart](../usage/quickstart.md).

## What would change these numbers

- A vendor shipping deterministic marking in a future model release.
- A different corpus. These repositories sit on one machine and follow one
  developer's habits, so the sample is small and not random.
- Text that passed through a chat web interface instead of a coding agent. This
  corpus is agent output committed to git, which is a different distribution.
  That is the most likely place to find something, and it is not covered here.
