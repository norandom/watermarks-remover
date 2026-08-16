# What we measured

**Measurement date: 2026-08-16.** Everything on this page is a snapshot of one
developer workstation on that day. It is not a claim about coding agents in
general, and it will go stale. Re-run the survey and compare.

## Corpus

Eleven repositories on a single machine, mixed authorship: some written with
Claude Code, one with a Codex-based spec-kit workflow, several by hand, two
third-party. 1,268 text files after excluding `.git`, `node_modules`, virtual
environments and build output.

## Result 1: no private-use watermarking

The starting hypothesis was that agents encode payloads in private-use or
unassigned Unicode space, where nothing legitimate lives.

**Private-use codepoints found across the entire corpus: zero.**

Not "few". None. Across all three private-use areas: `U+E000`–`U+F8FF`,
`U+F0000`–`U+FFFFD`, `U+100000`–`U+10FFFD`.

## Result 2: a Codex-authored repository, scanned

| Metric | Value |
| --- | --- |
| Files scanned | 703 |
| Files with any invisible carrier | 3 (0.43%) |
| Files with an **unexplained** carrier | **0 (0.0%)** |
| Carriers found | 6 |
| Carriers explained as legitimate | 6 (100%) |
| Watermark candidates | **0** |

All six were `U+FE0F VARIATION SELECTOR-16`, the character that forces emoji
presentation. They sit after `⚠` and similar in markdown templates. That is
ordinary content.

!!! note "Why the distinction matters"

    A naive scanner reports "6 invisible characters in 3 files, 0.43% of the
    codebase affected" and that number is worthless. The honest number is
    **zero watermark candidates**. Every tool in this space should be read with
    that distinction in mind.

## Result 2b: two public projects, head to head

Both repositories are public, and both are real work rather than test material.

!!! info "Provenance of this measurement"

    Run **2026-08-16T11:52:44Z**, against these exact commits:

    | Repository | Commit | Commit date |
    | --- | --- | --- |
    | `norandom/DataWorkStation_Powershell` | `12700f6` | 2026-08-16 |
    | `norandom/x_likes_scraper` | `48d1674` | 2026-08-14 |

    Both working trees were clean at measurement time, so the numbers describe
    those commits exactly and are reproducible from them.

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

The four x_likes_scraper flags were reviewed by hand and all four are benign:

- Two `U+FEFF` in `tests/mcp/synthesis/test_mindmap.py` are **deliberate test
  data**. The test builds `"...foo (bar)﻿"` and asserts the renderer
  strips it. A byte-order mark used as a test input, correctly flagged by a
  tool that cannot know intent.
- Two `U+FE0F` in `tests/mcp/test_tree.py` follow `\U0001f441` written as a
  *literal escape sequence in the source*. The emoji is escaped; its variation
  selector is not. No base character exists in the file for the scanner to
  find, so context resolution fails.

That second case is a limitation worth naming: **source code that escapes a
character but leaves its combining mark literal** defeats any context-based
explanation. It is not rare, and it will produce false positives in any tool
built this way.

### What the comparison does and does not show

It does show that neither agent emitted a covert mark in this sample, and that
the difference in carrier density (0.43% versus 4.1%) tracks **emoji usage in
documentation**, not provenance marking.

It does not show that Codex is tidier. The Codex repository is 703 files
largely of generated MkDocs output; the Claude repository is 195 files with a
higher proportion of hand-written markdown containing emoji. Different content,
not different behaviour.

The one genuine behavioural difference is attribution: Codex left **zero**
commit trailers across 19 commits, Claude left them on 83% of 141. If you want
to know which agent touched a repository, that is the signal, and it is a
configuration choice rather than a property of the model.

## Result 2c: what removal actually accomplished

The obvious next experiment: run the removal pass over a repository and measure
the difference. Done on a copy of `DataWorkStation_Powershell` at `12700f6`, so
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

Six of the seven shrank while the hook reported removing **nothing**. That is
the CRLF-frontmatter defect: the block is rebuilt with LF joins, so each
frontmatter line loses a byte, on files that contained no carriers at all.

The seventh is the Sanskrit stemmer described in
[What breaks](../reference/breakage.md).

### Re-measure

| | Before removal | After removal |
| --- | --- | --- |
| Files with any carrier | 3 (0.43%) | 3 (0.43%) |
| Carriers found | 6 | 6 |
| Explained | 6 | 6 |
| **Watermark candidates** | **0** | **0** |

Unchanged. The removal pass removed **zero watermarks**, corrupted one
third-party library, and churned six already-clean files.

!!! warning "A scope disagreement this exposed"

    The survey skips `site/` as build output. The hook does not. So the survey
    never counted the one file the hook damaged, and its "0 candidates" figure
    did not cover it.

    Two tools in the same repository disagreeing about which files exist is its
    own defect, and it is why the removal experiment was worth running rather
    than reasoning about.

## Result 3: attribution works, but only overtly

Since nothing is hidden in the text, attribution has to come from what the
agents declare about themselves.

| Evidence | Claude | Codex |
| --- | --- | --- |
| Config directory on disk | `.claude/`, `CLAUDE.md` | `.specify/`, `.agents/` |
| Commit trailers | 8 of 9 commits (88.9%) here; 117 of 141 in another repo | **0 of 18 commits** |

Two things follow.

**Attribution is a claim about tidiness, not forensics.** Both signals are
removed by `rm -rf .claude` and an interactive rebase. Nothing survives a
determined cleanup, because nothing is hidden.

**Trailer counts misattribute mixed repositories.** One repo here shows 117
Claude trailers and 25 Codex trailers. Another shows 55 and 5. Reading the
larger number as "the author" would be wrong; both agents worked on both.

## Result 4: the survey's own error rate

A survey is only as good as its ability to say *this carrier is legitimate*.
The first version of the tool got that wrong 15 times across 4 files, in both
cases by inheriting the cleaner's own blind spots:

- it did not recognise five emoji bases that sit outside the Symbol categories
  (`ℹ` `‼` `⁉` `⤴` `⤵`), so their presentation selectors looked like payloads;
- it looked back exactly one character for context, so in `❤️‍🔥` the joiner
  appeared to follow a variation selector rather than the heart.

After fixing both, false positives on this repository fell from 15 to 5, and
the remaining 5 are worked examples inside the documentation itself. That is
correct behaviour: those really are carriers sitting in prose.

**The error rate of the explanation layer is the number that determines whether
any other number can be trusted.** It is reported alongside the findings for
that reason.

## How to reproduce

```bash
python scripts/wm-survey.py /path/to/repo
python scripts/wm-survey.py /path/to/repo --json > baseline-$(date +%F).json
```

Exclude a project's own carrier fixtures, or they dominate everything:

```bash
python scripts/wm-survey.py . --exclude tests/corpus/
```

## What would change these numbers

- A vendor shipping deterministic marking in a future model release.
- A different corpus. Eleven repositories on one machine is a small,
  non-random sample, weighted toward one developer's habits.
- Content that passed through a chat web interface rather than a coding agent.
  This corpus is agent output committed to git, which is not the same
  distribution as text pasted out of a browser.

That last one is the most likely place to find something, and it is not covered
here.
