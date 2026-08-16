# watermarks-remover

An experiment in measuring how much invisible AI provenance marking is actually
present in real codebases, and removing it losslessly where it is.

!!! warning "Read this before anything else"

    This is a measurement experiment, not an evasion tool. It exists to answer
    a question with data: *are coding agents marking their output, and if so,
    how much and how detectably?*

    Provided **without warranty of any kind**. See
    [Limits and disclaimer](disclaimer.md).

## The headline result

**Baseline measured 2026-08-16**, across 11 repositories and 1,268 text files
on one developer workstation.

| Finding | Result |
| --- | --- |
| Private-use codepoints found | **0** |
| Unexplained carriers in a Codex-authored repo | **0** of 703 files |
| Carriers that turned out to be legitimate | **100%** in the Codex repo |
| Attribution possible from hidden marks | **no** |
| Attribution possible from declared artifacts | **yes** |

The hypothesis that started this project was that coding agents hide payloads
in unassigned or private-use Unicode space. In this corpus, they do not. Every
invisible character found was doing a job: emoji presentation, script
orthography, or an encoding signature.

That is a negative result, and it is the most useful thing here. Tools that
claim to strip AI watermarks from text are, against this sample, solving a
problem that has not yet appeared.

## What the three channels are

Confusing them is why people over- and under-estimate tools like this one.

| Channel | Carrier | Detect | Remove | Covered here |
| --- | --- | --- | --- | --- |
| **A. Format** | Codepoints that render as nothing or as a lookalike | scan codepoints, deterministic | delete them, lossless | **yes, only this** |
| **B. Statistical** | Which words the model chose | statistical test over tokens, needs the key | paraphrase, destroys the prose | no |
| **C. Declared metadata** | A field that says so | parse the container | delete the field | no |

!!! info "Channel A only, deliberately"

    Images, C2PA manifests, container metadata, YAML frontmatter keys and
    stylometry were all removed. Each was a different medium or a different
    kind of evidence.

    The test for anything readmitted: *does it change what invisible material
    is in the text, and can it be removed without changing what the text
    says?* See `.kiro/steering/scope.md`.

    Narrowing was not a retreat. Residual covert-channel capacity fell from
    2405 to 142 bits per kilobyte and detection recall rose from 85% to 100%
    in the same period, because the effort went into the one channel this tool
    claims.

Channel A is what this project removes. It is the only one where removal costs
nothing, because deleting a character that renders as nothing cannot change
what the text says.

Channel B is out of scope permanently. Removing a statistical watermark means
running a paraphrase model over your prose and accepting whatever comes back.
That has no place in a commit hook.

!!! note "Channel B detection does exist, upstream"

    The upstream project this borrows from,
    [`guillaumemeyer/watermarks-remover`](https://github.com/guillaumemeyer/watermarks-remover),
    ships `detect_text_watermark.py`: a harness that imports
    [THU-BPM/MarkLLM](https://github.com/THU-BPM/MarkLLM) from a user-supplied
    checkout at runtime and runs statistical detection.

    Its own documentation carries the caveat that matters: detection is valid
    only against the **same scheme configuration and keys used at generation**,
    and it cannot certify that a vendor's detector would fail on a given text.
    It is a research harness for controlled before/after experiments, not a
    general-purpose detector.

    Nothing in this repository invokes it.

## Where it stands

Measured against a catalogue of 24 published carrier techniques:

| | |
| --- | --- |
| Detection recall, in-scope techniques | **21 / 21 (100%)** |
| Residual covert-channel capacity | **142 bits/KB (1.0% of unfiltered)** |
| Largest remaining channel | braille blank, deliberately left open |
| Layer B | 0 of 1, and undetectable by anyone today |

Two fixes closed 94% of the residual: **bounding emoji tag payloads** (the
subdivision-flag exemption accepted any length, worth 1535 b/KB) and
**deriving the strip rule from `Default_Ignorable_Code_Point`** rather than
category `Cf`, which had been blind to invisible characters classified as
letters (728 b/KB).

Neither would have been prioritised by counting techniques. Both were obvious
once capacity was measured in bits.

## What this repository contains

- **A pre-commit hook** that strips Channel A carriers. See
  [The hook](usage/hook.md).
- **A survey tool** that measures how much signal is present and attributes
  authorship where evidence supports it. See [The survey](usage/survey.md).
- **A dated baseline** of what was actually found. See
  [What we measured](experiment/baseline.md).
- **A catalogue** of the characters involved and what each one indicates. See
  [Invisible characters](reference/characters.md).

## The uncomfortable finding

The hook damages real files. Measured, not hypothesised: on a third-party
Sanskrit stemmer checked into a Codex-authored repository, it deleted five
zero-width non-joiners that were legitimate Devanagari orthography.

That is documented in full at [What breaks](reference/breakage.md), because a
tool that rewrites source files in place has an obligation to be honest about
when it is wrong.
