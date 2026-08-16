# watermarks-remover

An experiment in measuring how much invisible AI provenance marking is actually
present in real codebases, and removing it losslessly where it is.

**Documentation: <https://norandom.github.io/watermarks-remover/>**

> **Baseline measured 2026-08-16.** Provided without warranty of any kind. This
> is a measurement experiment, not a tool for passing AI-generated work off as
> human. See [Limits and disclaimer](docs/disclaimer.md).

---

## The result so far

Across 11 repositories and 1,268 text files on one workstation:

| | |
| --- | --- |
| Private-use codepoints found | **0** |
| Watermark candidates in a Codex-authored repo | **0** of 703 files |
| Watermark candidates in a Claude-authored repo | **0** of 195 files |
| Invisible characters that turned out to be legitimate | **100%** |

The hypothesis that started this was that coding agents hide payloads in
private-use or unassigned Unicode space. In this corpus they do not. Every
invisible character found was doing a job: emoji presentation, script
orthography, or an encoding signature.

That negative result is the most useful thing here.

---

## Before and after

Invisible characters shown as `〈U+XXXX〉`. They are not visible in the
originals, which is the whole problem.

### Zero-width binary payload

```text
before  The release ships on Tuesday.〈U+200B〉〈U+200C〉〈U+200B〉〈U+200B〉〈U+200C〉〈U+200C〉〈U+200B〉〈U+200C〉
after   The release ships on Tuesday.
```

`54 bytes -> 30, removed=8.` Two codepoints, one bit each: one byte of payload.

### Tag-block smuggling

`U+E0000`–`U+E007F` mirrors ASCII invisibly.

```text
before  Shipped today.〈U+E0067〉〈U+E0065〉〈U+E006E〉〈U+E003D〉〈U+E0032〉〈U+E0030〉〈U+E0032〉〈U+E0036〉
after   Shipped today.
```

The payload decodes to `gen=2026`.

### Tag payload behind a flag emoji

The widest channel found, and the one a technique count would have missed:
prefix a payload with 🏴 and terminate it, and the subdivision-flag exemption
waved through **any length**.

```text
before  Status 🏴<14 invisible tag characters>󠀿 ok
after   Status  ok
```

Bounded to a conforming 2–6 character subdivision code. Worth 1535 bits/KB —
64% of everything that used to survive cleaning.

### And what it gets wrong

Real Sanskrit, in a third-party stemmer checked into a real repository:

```text
before  तथा अयम्〈U+200C〉 एकम्〈U+200C〉 इत्यस्मिन्〈U+200C〉
after   तथा अयम् एकम् इत्यस्मिन्
```

Those zero-width non-joiners follow a Devanagari virama. They force the
explicit halant form instead of a conjunct ligature. They are orthography, and
they are also the tokens a search index was built against. Nothing errors;
search quality silently degrades.

Full account: [What breaks](docs/reference/breakage.md).

---

## What the characters indicate

Presence alone indicates nothing. **Position and context carry the signal.**

| Signal | Weak evidence | Strong evidence |
| --- | --- | --- |
| Zero-width | after a Thai or Devanagari base | run between Latin letters |
| Variation selector | one after an emoji or ideograph | run on a single base |
| Tag characters | inside a short flag sequence | anywhere else |
| Private use | beside CJK, or a terminal config | in ordinary English prose |
| Bidi | marks in right-to-left text | override inside source code |
| Space homoglyph | French or CJK typography | alternating with plain spaces |

Everything in the weak column appeared in the baseline. Nothing in the strong
column did.

Not evidence of anything: em dashes, curly quotes, emoji, byte-order marks.

Catalogue: [Invisible characters](docs/reference/characters.md).

---

## Scope: Channel A only

| Channel | Carrier | Removal | Here |
| --- | --- | --- | --- |
| **A. Format** | codepoints that render as nothing | lossless | **yes, only this** |
| **B. Statistical** | which words the model chose | needs paraphrase | no |
| **C. Declared metadata** | a field that says so | delete the field | no |

Images, C2PA manifests, container metadata, YAML frontmatter keys and
stylometry have all been removed. The test for readmitting anything: *does it
change what invisible material is in the text, and can it be removed without
changing what the text says?*

Narrowing paid for itself. Residual covert-channel capacity fell from 2405 to
**142 bits per kilobyte** and detection recall rose from 85% to **100%** over
the same period.

Channel B is permanently out of scope here. Removing a statistical watermark
means running a paraphrase model over your prose and accepting what comes back.
That has no place in a commit hook.

Channel B *detection* does exist upstream, via a
[MarkLLM](https://github.com/THU-BPM/MarkLLM) harness — but only against the
same scheme config and keys used at generation, so it is a research instrument
rather than a general detector. Nothing here invokes it.

---

## Can you tell whether an AI wrote this?

No. But you can tell whether **something deliberately hid data in it**, and
that question is decidable. `wm-hook --detect` answers it, and the answer is
deliberately one-sided:

```console
$ wm-hook --detect release.md notes.md
CARRIER! release.md: covert carrier present, and it decodes
         + tag_outside_flag (+3): 30 tag character(s) outside a subdivision flag sequence
         > unicode tag block @33 [confirmed]
           'gen=claude-opus-4;run=8f31c2a0'
           identifies: 8f31c2a0, claude, gen=
CARRIER! notes.md: covert carrier present -- something embedded hidden data
         + binary_alphabet (+3): run of 32 uses exactly two codepoints (U+200B U+200C)
```

| | |
| --- | --- |
| **A positive is strong** | Text does not grow byte-aligned runs of zero-width characters between Latin letters by itself. |
| **A negative proves nothing** | A statistical watermark leaves no codepoint trace, so an AI-written file is *expected* to scan clean. |

Measured on the corpus below: **0 false positives in 1,155 files**, bounding
the per-file rate at 0.26% (rule of three, 95%). The same corpus puts
sensitivity to AI *authorship* at approximately zero — two of those
repositories were written almost entirely by coding agents and both scan clean.

**Specific, not sensitive.** No "% AI" number is produced, because collapsing
those two measurements into one would be the central dishonesty this project
exists to avoid.

Presence is not the test; **structure** is. Runs, two-codepoint alphabets,
byte-aligned lengths, placement between ASCII letters and even spacing each
carry a weight, and every weight that fired is printed with the verdict. Below
the threshold a residual is reported as an `anomaly`, not a finding — which is
what keeps stray BOMs and copy-paste debris out of the results.

### "But this repo is AI-written and scans clean"

The sharpest objection to the whole result. It assumes an unstated premise —
*AI writing contains a carrier* — which is the claim under test; granting it
makes the experiment unfalsifiable. Three measurements separate "nothing is
there" from "we cannot see it":

1. **No material to hide in.** 604,030 characters of agent-written text here,
   0.17% non-ASCII, and the entire invisible inventory is ~40 characters that
   are the detector's own documented examples. The most common non-ASCII
   character is the em dash.
2. **The same files light up when a carrier is injected.** A tag block, a
   zero-width bit stream and a private-use run each flip agent-written source
   from `none` to `carrier`. Enforced in `tests/test_verdict.py`, so the
   argument is executable rather than asserted.
3. **Recall is 21/21** against published techniques.

AI use of this repo *is* detectable at 100% — through `.claude/`, `CLAUDE.md`
and commit trailers. The marking simply is not where a codepoint scan looks.

Details, worked examples and the full false-positive table:
[Is a carrier present?](docs/usage/detect.md)

---

## Usage

### Survey a tree

```bash
python scripts/wm-survey.py /path/to/repo
python scripts/wm-survey.py . --exclude tests/corpus/ --json
```

Reports carriers found, carriers explained as legitimate, and the unexplained
residual, separately. It never presents the first as a detection rate — on the
Codex repo that would claim 0.43% where the honest answer is 0%.

Also attributes authorship from **overt** evidence: config directories and
commit trailers. Both are removable with `rm -rf` and a rebase. There is no
covert channel to fall back on.

### The pre-commit hook

```yaml
repos:
  - repo: https://github.com/norandom/watermarks-remover
    rev: <tag>
    hooks:
      - id: wm-hook              # rewrites files
        exclude: '^(site/|vendor/|locales/)'
      - id: wm-hook-check        # manual stage, reports only
```

`wm-hook --detect` is the third mode: it never writes, and it exits 1 only when
a covert carrier is *established*, not merely when an invisible character is
present. That makes it the one suitable for a CI gate.

Run `pre-commit run --all-files` once and read the diff before trusting it.
Place it after anything that writes text and before anything that formats it.

Details: [The hook](docs/usage/hook.md).

---

## Status

Under active development against specifications in `.kiro/`. The shipped hook
has documented defects that corrupt Devanagari, CJK typography and YAML
structure. Fixes are specified and partly implemented.

On one real repository, the removal pass removed **zero** watermarks, corrupted
one third-party library, and churned six already-clean files. That measurement
is in [What we measured](docs/experiment/baseline.md).

---

## Provenance

A fork, not a vendored dependency. The cleaning logic in `src/wm_hook/core/`
started as a copy of
[`guillaumemeyer/watermarks-remover`](https://github.com/guillaumemeyer/watermarks-remover)
and has since been edited freely — the flag-tag bound, the
`Default_Ignorable_Code_Point` rule and the detection layer are all divergence
from upstream. Origin commits are recorded in [NOTICE](NOTICE).

## License

MIT. See [LICENSE](LICENSE). Provided without warranty of any kind. Code
inherited from upstream carries upstream's licensing.
