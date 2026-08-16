# Limits and disclaimer

## No warranty

This software is provided under the MIT licence, **without warranty of any
kind**, express or implied, including but not limited to the warranties of
merchantability, fitness for a particular purpose and noninfringement. In no
event shall the authors be liable for any claim, damages or other liability
arising from the software or its use.

That is the licence text. Here is what it means in practice for this particular
tool:

**Its default mode rewrites your source files in place.** It has documented,
reproduced defects that corrupt legitimate content — Devanagari orthography,
CJK typography, YAML structure. See [What breaks](reference/breakage.md) before
enabling it. Run `pre-commit run --all-files` once and read the diff.

## Why this exists

To answer a question with measurements: **are coding agents marking their
output with invisible characters, and if so, how much and how detectably?**

The [baseline](experiment/baseline.md) answers it for one corpus on one day:
essentially not at all. Zero private-use codepoints across 1,268 files. Zero
watermark candidates in either public repository examined. Every invisible
character found was doing legitimate work.

The interesting number going forward is whether that stays true. This is set up
to be re-run and compared, which is why every finding carries a date and a
commit SHA.

## What this is not for

**This is not a tool for passing AI-generated work off as human.**

Stating that plainly because the capability is dual-use and pretending
otherwise would be dishonest. A tool that removes provenance marks can be used
to defeat provenance checks. That is inherent, not incidental.

Three reasons the concern is narrower than it looks, and one reason it is real:

- The marks it removes **are not present** in the corpus measured. There is
  currently little to defeat.
- Detection that matters in practice — academic integrity tooling, content
  provenance systems — largely does not rely on Layer A invisible characters.
  It relies on statistical analysis of word choice, which this tool explicitly
  does not touch and never will.
- Removing an invisible character is not forgery. It does not add a false
  claim of human authorship; it removes an undisclosed marker.

The real concern: if a vendor ships deterministic marking and someone uses this
to strip it before submitting work as their own, that is misuse. Do not do
that. If you are subject to a disclosure requirement, disclose.

## What it does not detect

A clean result from this tool means **no deterministic invisible carriers were
found**. It does not mean text was written by a human.

Explicitly out of reach:

| Not detected | Why |
| --- | --- |
| Statistical watermarks (SynthID-Text, green-list biasing) | Encoded in token choice; needs a statistical test and a key, not a codepoint scan |
| Stylistic tells | Not marks. Em dashes and word choice prove nothing |
| Pixel-domain image watermarks | Different medium, different tooling |
| Anything in a format not scanned | Binary files are skipped by design |

Known blind spots in what it *does* cover are recorded in
[What breaks](reference/breakage.md) and tracked as specifications in `.kiro/`.

## On the measurements

Every figure here is a **dated snapshot of one developer's workstation**, not a
standing claim about any vendor.

Specific limits of the sample:

- 11 repositories, 1,268 files, one machine, one person's habits. Small and
  non-random.
- It measures **agent output committed to git**, which is not the same
  distribution as text pasted out of a chat interface. The latter is the more
  likely place to find marking and is not covered.
- The survey's own explanation layer had a measured false-positive rate. It was
  wrong 15 times before being corrected, and it is certainly still wrong
  somewhere.
- Absence of evidence over one corpus on one day is weak evidence of absence.

## Reproducing and disputing

```bash
python scripts/wm-survey.py /path/to/repo --json > findings.json
```

If your findings differ, they are probably more current than these. The point
of dating everything is to make disagreement checkable rather than rhetorical.

---

*Baseline measured 2026-08-16. Documentation current as of the same date.*
