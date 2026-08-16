# What a result means

`wm-hook --detect` answers one question. Did something hide data in this text?
It does not answer who or what wrote the text.

This page explains what you may say after a positive result, and what you may
not say after a negative one. The numbers themselves are in
[Results](baseline.md).

## The test is one-sided

!!! success "A positive is strong"

    Text does not grow byte-aligned runs of zero-width characters between
    Latin letters by itself. A zero-width character is one you cannot see. When
    the detector fires, something put hidden data there on purpose.

!!! danger "A negative is worthless as evidence of human authorship"

    A statistical watermark (Channel B below) lives in which words the model
    chose. It leaves no trace in the codepoints. A clean scan is exactly what
    an AI-written file is expected to look like.

The tool never prints a "% AI" number, and it never will. The two sides of the
test measure different things: 0 false positives in 1,155 files, and both
agent-written repositories in that corpus scanned clean
([Results](baseline.md)).

One percentage cannot carry both results. A reader would take it as a score for
authorship, and that is the one thing this test cannot measure.

The tool is good at confirming hidden data and bad at ruling it out. It says
that in words instead of printing a number.

## What a positive proves

| Question | Can the tool answer it? |
| --- | --- |
| Did something hide data here on purpose? | **yes** |
| Where is it, and how many bits does it carry? | **yes** |
| What does it say? | yes, if the encoding is one of four published ones |
| Which tool put it there? | only if the payload says so |
| Was this text written by an AI? | **no** |

A model vendor, a watermarking service, a content system, a plagiarism tracker
and an attacker all leave the same evidence. The tool reports that a carrier is
present. It never says who put it there.

If the payload decodes, the decoded text is the attribution. That is evidence
you can read, not an inference from writing style.

## The three channels

A watermark can live in three places. Only the first one is in scope here.

| Channel | Where the mark lives | How you remove it | In scope |
| --- | --- | --- | --- |
| **A. Format** | codepoints that render as nothing | delete them, the visible text does not change | **yes, only this** |
| **B. Statistical** | which words the model chose | rewrite the text with a paraphrase model | no |
| **C. Declared metadata** | a field that says so | delete the field | no |

Channel A is the only one you can clean without changing what the text says.
That is the test for what belongs in this project.

Channel B is out of scope permanently. Removing a statistical watermark means
running your prose through a paraphrase model and keeping whatever comes back.
A commit hook must not do that.

Channel B *detection* does exist upstream, in a
[MarkLLM](https://github.com/THU-BPM/MarkLLM) harness. It only works against the
same scheme and keys used when the text was generated. That makes it a research
instrument rather than a general detector, and nothing here calls it.

Images, C2PA manifests, container metadata and stylometry were all dropped for
the same reason. Narrowing the scope raised detection recall and cut the hidden
capacity that survives cleaning. Figures: [Results](baseline.md).

## "But this repository is AI-written and scans clean"

This is the sharpest objection to the whole result. The argument runs:

1. An agent wrote almost all of this repository.
2. The detector finds no carrier in it.
3. So the detector is broken.

Step 3 needs a fourth premise that nobody stated: *AI writing contains a
carrier*. That premise is the claim under test. If you assume it, every clean
result becomes proof of a broken tool, and no measurement could ever count
against it.

Two hypotheses have to be told apart by measurement instead:

| | |
| --- | --- |
| **H1** | There is no carrier here. |
| **H2** | There is one, and the detector cannot see it. |

Three measurements separate them.

### 1. There is nothing to hide in

This repository's own agent-written text is **0.17%** non-ASCII, and the most
common non-ASCII character is the em dash. The full inventory is in
[Results](baseline.md#this-repositorys-own-text).

A codepoint carrier needs codepoints. This text is 99.83% ASCII, and most of
the rest is em dashes. There is nowhere for a carrier to sit.

### 2. The same files react when a carrier is added

If the detector were blind, adding a carrier would change nothing. It changes
the verdict every time. A tag block, a zero-width bit stream and a private-use
run each move agent-written source from `none` to `carrier`.

`tests/test_verdict.py` enforces this. You can run the argument instead of
believing it.

### 3. Recall is 21 out of 21

The detector finds every one of the 21 published embedding techniques it was
tested against ([Results](baseline.md)). H2 then survives only in the form *a
carrier using a scheme nobody has published*. Nothing can test that, so it is
not a finding.

### What is detectable here

AI use of this repository is easy to detect. It is just not detectable in the
codepoints.

| Evidence | Present here | Channel |
| --- | --- | --- |
| `.claude/` and `CLAUDE.md` on disk | yes | C, declared |
| `Co-Authored-By` commit trailers | yes | C, declared |
| Em dashes, arrows, writing style | yes | stylometry, a prior only, not evidence |
| Invisible codepoint carrier | **no** | A |
| Statistical token watermark | unknown, and undetectable from the text | B |

The marking is not where a codepoint scan looks. Claude Code writes plain UTF-8
through a file-write tool. There is no embedding step between the model and the
disk.

Anthropic
[documents](https://support.claude.com/en/articles/16266773-how-claude-marks-ai-generated-content)
a statistical mark. It excludes very short passages, which carry too little text
for a reliable signal. That exclusion is how a Channel B scheme behaves.

A clean Channel A result and heavy AI authorship fit together. Both are true of
this repository.
