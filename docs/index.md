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
| **A. Format** | Codepoints that render as nothing or as a lookalike | scan codepoints, deterministic | delete them, lossless | yes |
| **B. Statistical** | Which words the model chose | statistical test over tokens | paraphrase, destroys the prose | **no, deliberately** |
| **C. Declared metadata** | A field that says so | parse the container | delete the field | frontmatter and containers |

Channel A is what this project removes. It is the only one where removal costs
nothing, because deleting a character that renders as nothing cannot change
what the text says.

Channel B is out of scope permanently. Removing a statistical watermark means
running a paraphrase model over your prose and accepting whatever comes back.
That has no place in a commit hook.

## What this repository contains

- **A pre-commit hook** that strips Channel A carriers and Channel C
  frontmatter keys. See [The hook](usage/hook.md).
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
