# Is a carrier present?

This is the one question in the project that is actually tractable, and
`wm-hook --detect` is the answer to it.

## Running it on another project

You do **not** need to activate this repository's virtualenv. Sourcing
`.venv` works, but it means every future invocation depends on remembering to
do it, and on your shell's current directory. Prefer one of these:

=== "No install (recommended)"

    ```bash
    uvx --from git+https://github.com/norandom/watermarks-remover \
        wm-hook --detect /path/to/project
    ```

    `uvx` builds a throwaway environment and throws it away again. Nothing is
    added to your system or to the target project.

=== "From a checkout, anywhere"

    ```bash
    uv run --project ~/Source/watermarks-remover wm-hook --detect /path/to/project
    ```

    `--project` points at this repository while your shell stays wherever it
    is, so there is nothing to activate and nothing to deactivate.

=== "Installed on your PATH"

    ```bash
    uv tool install git+https://github.com/norandom/watermarks-remover
    wm-hook --detect /path/to/project
    ```

    Then `wm-hook` is just a command. Update with `uv tool upgrade`.

=== "Activated venv"

    ```bash
    source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
    wm-hook --detect /path/to/project
    ```

    Works, and is the option most likely to leave you wondering later why
    `wm-hook` is not found.

**Directories are walked.** Point it at a project root and it finds the text
files itself, skipping `.git`, `node_modules`, `.venv`, `dist`, `build`,
`target` and a built `site/`. A file named explicitly is always scanned,
extension or not — asking for `LICENSE` is an instruction, not a suggestion.

```bash
wm-hook --detect .                # this project
wm-hook --detect src docs         # several roots
wm-hook --detect --json . > r.json
wm-hook --detect -v src           # list clean files too
```

!!! warning "`--detect` never writes. Bare `wm-hook` does."

    `wm-hook /path/to/project` **rewrites the tree in place**. That is the
    autofix path and it is what the pre-commit hook runs. Use `--detect` to
    look, `--check` to see what would change, and neither unless you have read
    [What breaks](../reference/breakage.md) — the cleaner is known to damage
    Devanagari orthography and CJK typography.

    Run it under git, on a clean tree, and read the diff.

Exit codes: `0` no covert carrier established, `1` at least one file carries
one, `2` a file could not be read **or no text files were found at all**. That
last case is an error on purpose: reporting "0 of 0 files are clean" for a scan
that never happened is the manufactured confidence this whole project is built
to avoid.

## The test is one-sided

Everything about this feature follows from one asymmetry, and stating it
plainly is more useful than any accuracy figure:

!!! success "A positive is strong"

    Text does not spontaneously grow byte-aligned runs of zero-width
    characters between Latin letters. When the detector fires, something
    deliberately embedded hidden data.

!!! danger "A negative is worthless as evidence of human authorship"

    A statistical watermark ([Channel B](../index.md#what-the-three-channels-are))
    lives in *which words the model chose* and leaves no codepoint trace
    whatsoever. A clean scan is exactly what an AI-written file is expected to
    look like. In the dated baseline, **every** AI-authored repository scanned
    clean.

Collapsing those two into a single "% AI" number would be the central
dishonesty this project exists to avoid, so no such number is produced.

## What a positive does and does not establish

| Question | Answerable? |
| --- | --- |
| Did something deliberately embed hidden data here? | **yes** |
| Where is it, and how many bits does it carry? | **yes** |
| What does it say? | yes, if the encoding is one of four published ones |
| Which tool embedded it? | only if the payload says so |
| Was this text written by an AI? | **no** |

A model vendor, a watermarking service, a CMS, a plagiarism tracker and an
attacker all leave the same evidence. The detector says a carrier is present;
it never says who put it there. If a payload decodes, *that* is attribution —
and it is evidence rather than inference, which is what makes it worth more
than any style score.

## Presence is not the test — structure is

Almost every invisible codepoint in a real source tree is legitimate. Counting
codepoints reports a hit rate roughly two orders of magnitude above the truth.
So the residual after [explanation](../reference/characters.md) is the input,
and structure is what promotes a residual to a finding:

| Signal | Weight | Why it is not an accident |
| --- | --- | --- |
| `run` | 2 | Debris is isolated; payloads are contiguous |
| `binary_alphabet` | 3 | Exactly two codepoints repeating is a bit stream |
| `byte_aligned` | 1 | A length that is a multiple of 8 was packed |
| `latin_context` | 2 | Orthographic joiners occur in Indic, Arabic and Thai — never between two ASCII letters |
| `periodic` | 2 | Evenly spaced marks encode one per token |
| `tag_outside_flag` | 3 | The tag block has exactly one sanctioned use, and it is already exempted |
| `private_use_in_text` | 2 | These codepoints have no assigned meaning at all |

Score ≥ 4 is high confidence, ≥ 2 moderate, and anything below that is reported
as an **anomaly** rather than a finding.

Every weight that fired is printed with the verdict. A finding you cannot argue
with is a finding you cannot check.

## The four verdict levels

| Level | Meaning | Exit-code positive |
| --- | --- | --- |
| `none` | No invisible codepoints at all | no |
| `benign` | Invisible codepoints present, all legitimate | no |
| `anomaly` | Unexplained, but isolated and unstructured | no |
| `carrier` | Unexplained **and** structured | **yes** |
| `payload` | …and it decodes to readable data | **yes** |

The `anomaly` tier is the one that earns its keep. Copy-paste debris from a web
page, an editor artifact, a stray BOM inside a string literal — these are
unexplained but meaningless, and a detector without this tier reports them as
findings and destroys its own precision.

## Worked example

```console
$ wm-hook --detect release.md notes.md readme.md stemmer.py app.py
CARRIER! release.md: covert carrier present, and it decodes
         30 carrier(s), 0 explained, 30 unexplained
         + run (+2): 30 consecutive unexplained tag_chars at offset 33
         + tag_outside_flag (+3): 30 tag character(s) outside a subdivision
           flag sequence; the tag block has no other sanctioned use
         > unicode tag block @33 [confirmed]
           'gen=claude-opus-4;run=8f31c2a0'
           identifies: 8f31c2a0, claude, gen=
         confidence: high; capacity 210 bits

CARRIER! notes.md: covert carrier present -- something embedded hidden data
         32 carrier(s), 0 explained, 32 unexplained
         + run (+2): 32 consecutive unexplained zero_width at offset 15
         + binary_alphabet (+3): run of 32 uses exactly two codepoints
           (U+200B U+200C) -- a bit stream
         + byte_aligned (+1): run length 32 is a multiple of 8
         confidence: high; capacity 32 bits

CLEAN    readme.md: invisible characters present, all legitimate
         12 carrier(s), 12 explained, 0 unexplained
CLEAN    stemmer.py: invisible characters present, all legitimate
         2 carrier(s), 2 explained, 0 unexplained

2 of 5 file(s) carry a covert carrier.
```

`readme.md` holds a BOM, an emoji presentation selector, a family ZWJ sequence,
a subdivision flag tag sequence and two French typographic spaces — twelve
carriers, all explained. `stemmer.py` holds Devanagari virama joiners. Neither
is a finding, and getting that right is harder than catching the two that are.

## "But this repository is AI-written and scans clean"

That is the sharpest objection to the whole result, and it is worth answering
properly rather than waving at. The implied argument is:

1. This repository was written almost entirely by an agent.
2. The detector finds no carrier in it.
3. Therefore the detector is broken.

The flaw is an unstated fourth premise — *AI writing contains a carrier* — and
that premise is the claim under test. Assuming it makes the experiment
unfalsifiable: any clean result becomes proof of a broken instrument, and no
observation could ever count against it.

So the two hypotheses have to be separated by measurement:

| | |
| --- | --- |
| **H1** | There is no carrier here |
| **H2** | There is one and the detector is blind to it |

**Three measurements distinguish them.**

### 1. There is no material to hide in

An inventory of every codepoint in this repository's own agent-written source
and prose, excluding its carrier fixtures:

| | |
| --- | --- |
| Characters | 604,030 |
| Non-ASCII | 1,055 (**0.17%**) |
| Invisible (`Cf`/`Co`) | ~40, every one a documented example in the detector's own code |
| Most common non-ASCII | em dash (314), rightwards arrow (127), box drawing (101) |

You cannot fail to detect a carrier in text that is 99.83% ASCII and whose
non-ASCII is em dashes and box-drawing characters. This is not a detector
returning "clean" — it is a file with nowhere for a codepoint carrier to be.

### 2. The same files light up when a carrier is injected

If the detector were blind, adding a carrier would change nothing. It changes
the verdict every time — a tag block, a zero-width bit stream and a private-use
run each flip agent-written source from `none` to `carrier`. That is enforced by
`tests/test_verdict.py`, so the argument is executable rather than asserted.

### 3. Recall against published techniques is 21/21

Measured in `research/recall/`. H2 survives only in the narrow form *a carrier
using a scheme nobody has published* — which is unfalsifiable and therefore not
a finding.

### What is actually detectable here

AI use of this repository **is** detectable, at 100%, just not through a carrier:

| Evidence | Present | Channel |
| --- | --- | --- |
| `.claude/`, `CLAUDE.md` on disk | yes | overt declaration |
| `Co-Authored-By` commit trailers | yes | overt declaration |
| Em dashes, arrows, register | yes | stylometry — a prior, not evidence |
| Invisible codepoint carrier | **no** | Channel A |
| Statistical token watermark | **unknown, and undetectable** | Channel B |

The conclusion is not "we cannot tell". It is that **the marking is not where
the tooling looks**. Claude Code writes plain UTF-8 through a file-write tool;
there is no embedding step between the sampler and the disk. What Anthropic
[documents](https://support.claude.com/en/articles/16266773-how-claude-marks-ai-generated-content)
is a statistical mark, and its own exclusion of "very short passages with too
little text for a reliable signal" is the signature of a Channel B scheme — one
a codepoint scan cannot see by construction, with or without a working detector.

A clean Channel A result and heavy AI authorship are perfectly consistent. Both
are true of this repository.

## Measured false-positive rate

Across the corpus below, unexcluded, on **2026-08-16**:

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

Zero false positives in 1,155 files. By the rule of three that bounds the
per-file false-positive rate at **0.26%** with 95% confidence.

The same corpus puts sensitivity to AI *authorship* at approximately zero: two
of these repositories were written almost entirely by coding agents and both
scan clean. **Specific, not sensitive.** That is the honest characterisation,
and it is why the tool refuses to print a percentage.

### The two unexplained residuals

Both are in `x_likes_scraper`, both are correctly reported as anomalies rather
than findings, and both are worth naming because they are the shape a real
false positive would take:

- A literal `"﻿"` inside a test asserting that BOM stripping works. The
  fixture for a BOM test is, necessarily, a BOM.
- A half-escaped emoji: the base spelled as the ASCII escape `\U0001f441`, the
  variation selector left as a real codepoint. The base lookup saw the trailing
  hex digit and called the selector orphaned.

The second was a genuine gap and is now
[explained](../reference/characters.md) — bounded to exactly one selector,
because the character preceding a second one is the first, not a hex digit. An
exemption without a length bound is a channel, which is the lesson the
subdivision-flag exemption taught at a cost of 1535 bits/KB.
