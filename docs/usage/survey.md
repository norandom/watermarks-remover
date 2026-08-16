# The survey

A read-only research instrument. It measures how much AI provenance signal is
present in a tree and attributes authorship where evidence supports it.

It never modifies anything.

## Running it

```bash
python scripts/wm-survey.py /path/to/repo
python scripts/wm-survey.py repo-a repo-b --json > findings.json
python scripts/wm-survey.py . --exclude tests/corpus/
```

Exclude your own carrier fixtures, or they dominate the numbers. This project's
test corpus contains deliberate payloads; without `--exclude` they account for
80 of 95 findings.

## Reading the output

```
files scanned                 703
files with any carrier        3  (0.43%)
files with UNEXPLAINED        0  (0.0%)

carriers found                6
  explained as legitimate     6  (100.0%)
  unexplained (candidates)    0
```

Three numbers, never collapsed into one:

| Quantity | Meaning |
| --- | --- |
| **carriers found** | Every invisible or format codepoint present |
| **explained** | Attributable to a documented legitimate cause |
| **unexplained** | The residual. The only watermark candidates |

!!! danger "Carriers found is not a detection rate"

    On the repository above, reporting "carriers found" as a detection rate
    claims 0.43%. The honest answer is **0%** — all six were emoji presentation
    selectors.

    Any tool that reports a single "watermarks detected" figure without
    separating these is overstating by roughly two orders of magnitude against
    this corpus.

## What counts as explained

| Carrier | Explained when |
| --- | --- |
| Variation selector | follows an emoji, symbol or ideograph base |
| `U+200C` / `U+200D` | between letters of a script where it is orthographic, or at a word boundary after one |
| `U+200B` | after a base in a script that uses it as a word separator |
| `U+FEFF` | at offset zero |
| Space homoglyph | typographic, or an ideographic space in CJK |
| Tag characters | inside a subdivision flag sequence |
| Directional marks | in mixed-direction text |

Context resolves against the nearest preceding **base**, skipping intervening
carriers. Without that, the joiner in `❤️‍🔥` appears to follow a variation
selector rather than the heart, and gets reported as a payload.

## The explanation layer is the weak point

A survey is only as good as its ability to say *this carrier is legitimate*.
Over-explain and real marks vanish; under-explain and every emoji is an alarm.

The first version was wrong 15 times across 4 files, both times by inheriting
the cleaner's own blind spots: five emoji bases outside the Symbol categories
were unrecognised, and context resolution stopped one character back. After
fixing both, false positives on this repository fell to 5, all of them worked
examples inside the documentation.

Known remaining limitation: **source that escapes a character but leaves its
combining mark literal**. Two hits in `x_likes_scraper` were `U+FE0F` following
`\U0001f441` written as an escape sequence. No base exists in the file to find.

Treat the unexplained count as an upper bound needing review, not a verdict.

## Attribution

```
attribution (overt evidence only):
  config on disk              claude
  commit trailers             claude=117 (83.0%)  of 141 commits
```

Two sources, both **overt**:

- **Declared configuration** — `.claude/`, `CLAUDE.md`, `.specify/`, `.agents/`,
  `.cursor/`, `.gemini/`, `.aider.conf.yml`
- **Commit trailers** — `Co-Authored-By: Claude`, and equivalents

Neither survives `rm -rf .claude` and an interactive rebase. Attribution here is
a claim about tidiness, not forensics. There is no covert channel to fall back
on, because the [baseline](../experiment/baseline.md) found none.

!!! note "Do not read a trailer count as authorship share"

    One repository shows 117 Claude trailers and 25 Codex trailers. Another
    shows 55 and 5. Both agents worked on both. And a Codex-authored repository
    here left **zero** trailers across 19 commits, so absence of a trailer says
    nothing at all.

The survey deliberately does **not** infer an agent from writing style or
formatting habits. Those signals are unfalsifiable and prejudicial.

## Scope

Deterministic carriers only. It cannot see statistical token-sampling
watermarks, and a zero result does not mean text was written by a human. See
[Limits and disclaimer](../disclaimer.md).
