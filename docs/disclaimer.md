# Limits and disclaimer

## No warranty

This software is under the MIT licence. It comes **without warranty of any
kind**, express or implied. The authors are not liable for any claim or damage
that arises from the software or its use.

!!! danger "The default mode rewrites your files"

    Running `wm-hook <dir>` edits the tree in place. It has known defects that
    damage real content, including Devanagari spelling and CJK typography. Read
    [What breaks](reference/breakage.md) first.

    If you only want a report, run `wm-hook --detect <dir>`. That mode never
    writes.

## Why this exists

We wanted to answer one question with measurements: do coding agents mark their
output with invisible characters? In the files we scanned, they did not.
[Results](experiment/baseline.md) has the corpus, the numbers and the date.

Every finding carries a date, so you can run the scan again and compare.

## What this is not for

**This is not a tool for passing AI-generated work off as human.**

The capability is dual-use, so we say that plainly. A tool that removes
provenance marks can also defeat a provenance check. Three reasons the risk is
smaller than it looks:

- The marks were not there. In the files we scanned there was nothing to strip.
- Real detection tools mostly ignore invisible characters. They analyse word
  choice, and this tool never touches word choice.
- Removing an invisible character adds no false claim of human authorship.

One reason the risk is real. If a vendor ships deterministic marking, someone
could strip it and submit the work as their own.

Do not do that. If you have a duty to disclose, disclose.

## What it does not detect

A clean result means we found no carrier. A carrier is a character you cannot
see that hides data. A clean result does not prove a human wrote the text.

| Not detected | Why |
| --- | --- |
| Statistical watermarks (SynthID-Text, green-list biasing) | Hidden in word choice. Needs a statistical test and a key, not a character scan |
| Writing style | Style is not a mark. Em dashes and word choice prove nothing |
| Watermarks inside images | Different medium, different tooling |
| Anything in a file we do not read | The tool skips binary files by design |

Known gaps in what it does cover are in [What breaks](reference/breakage.md).

## On the measurements

Every number in these docs is a dated snapshot from one workstation, measured on
2026-08-16. It is not a standing claim about any vendor.

- One machine, one person's habits. The sample is small and not random.
- We measured agent output committed to git, not text pasted out of a chat
  window. Chat text is the more likely place to find marking.
- The tool's own explanation layer makes mistakes. Its measured error rate is in
  [Results](experiment/baseline.md).
- A clean scan is weak proof. [What it means](experiment/what-it-means.md)
  explains why a positive result is strong and a negative one is not.

If your own scan finds something different, it is probably more current than
ours. [Survey a tree](usage/survey.md) shows how to run it.
