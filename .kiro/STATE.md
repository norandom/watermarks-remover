# Project state

**Paused 2026-08-16.** Written to be picked up cold. Repository is private.

## Where things stand

Four specs in `.kiro/specs/`, implementation partway through the first.

| Spec | Phase | Notes |
| --- | --- | --- |
| `watermark-removal` | tasks, **6 of 18 done** | the rewrite path |
| `watermark-detection` | tasks generated | read-only gating, not started |
| `container-cleaning` | requirements | `wm-clean` for DOCX/PDF/SVG/images |
| `provenance-survey` | requirements | the survey tool, prototype already working |
| `ci-pipeline` | requirements | dagger, GitHub releases |

Suite: **775 passed, 8 skipped** on Windows; **783 passed, 0 skipped** on Linux
via `scripts/test-linux.sh`. The 8 are POSIX gates that Windows cannot observe.

## Do not release yet

The shipped hook damages files. Measured on a copy of
`DataWorkStation_Powershell`: 576 files processed, 7 modified, **zero
watermarks removed**, one third-party Sanskrit stemmer corrupted, six clean
files churned by the CRLF-frontmatter defect.

Release blocker is correctness, not detection. See
`docs/reference/breakage.md`.

## Immediate next step

**Task 2.2 was REJECTED and needs re-dispatch.** `src/wm_hook/regions.py` and
`tests/test_regions.py` are committed but the task checkbox is unticked, on
purpose.

The finding: `_structural_positions` marks only column 0, but a no-break space
at column 2 inside YAML indentation also changes the parse. Reproduced:

```
before: 'nested:\n  \xa0key: v\n'  ->  {'nested': {'\xa0key': 'v'}}
after : 'nested:\n   key: v\n'     ->  {'nested': {'key': 'v'}}
```

That is Requirements 1.3 and 4.1, both listed on task 2.2, unmet.

Part of it is a **spec gap I own**: `design.md` narrows the requirement to
"column 0 of a line", which is narrower than the requirement it traces to. Fix
the design wording first, then re-dispatch the implementer with the reviewer's
remediation (widen to the whole leading-whitespace run; add the four test cases
it names).

Everything else in the code is reviewed and approved.

## The detection finding, which changed the project's framing

The starting hypothesis was that agents hide payloads in private-use Unicode
space. **They do not** — zero private-use codepoints across 1,268 files in 11
repositories.

Claude *does* watermark text, including Claude Code output
([support article](https://support.claude.com/en/articles/16266773-how-claude-marks-ai-generated-content)).
But the exclusion "very short passages with too little text for a reliable
signal" is the signature of a **statistical** watermark, not a Unicode one. A
zero-width payload works on five words; a statistical test needs many tokens.

Three channels were tested against Claude Code output:

| Channel | Method | Result | Why |
| --- | --- | --- | --- |
| A, invisible Unicode | codepoint scan | 0 found | wrong channel |
| Stylometry | upstream's scorer | 0 flagged, mean 0.05 | calibrated for marketing register |
| B, statistical | needs scheme + keys | untestable | Anthropic has not published a detector |

The stylometry scorer was **validated with controls**: 0.685 on AI marketing
prose, 0.030 on hand-written informal, 0.029 on technical documentation written
by Claude minutes earlier. It works; it simply has near-zero recall on the
register these repositories use.

Upstream's own position, from a project with 10k stars: *"Until vendors ship
public detectors and keys, no tool can honestly certify."*

So a 0% Layer A result on Claude Code output is **evidence about the
mechanism**, not evidence of absence.

## Detection work

1. **Applicability reporting — DONE.** The survey now declares, per channel,
   what it could and could not have detected, and qualifies every zero. Two of
   four channels report OFF. A zero residual is no longer presentable as
   "clean".
2. **Layer A recall benchmark — next.** Synthetic corpus of every published
   edit-based technique, measured recall. Turns "we found nothing" into "we
   detect N of M known techniques".
3. **Vendor `score_stylometry.py`** as a fifth `_vendor` file with its own
   survey channel, never conflated with carrier findings. Note its measured
   register limitation before wiring it in.
4. **Watch item:** Anthropic's "forthcoming technical documentation" on
   detection. That is the trigger for any Layer B work.

## The discrimination study: built, then dropped

A labelled corpus was assembled and the study was **deliberately not run**,
because the result would have been confounded. Recorded so it is not
rediscovered.

**Corpus that exists** (scripts in the session scratchpad, not committed):

- 300 wholly-Claude-authored files — every commit touching them carries a
  Claude trailer. 195 prose (221k words), 105 code (103k words).
- 2,400 pre-LLM human commit messages from `git/git` 2018-2019, 166k words.
- 261 Claude-trailered commit messages, 28k words.

**Why it was dropped.** 87k of the 221k Claude prose words are this
repository's kiro specs, and 59k more are from `Skills`. A classifier fitted to
that learns the spec template and one developer's toolchain, not Claude. It
would score well on held-out data from these repos and collapse elsewhere.

**The deeper reason.** Every style-based method measures *register*, which is a
property of the workflow. That is exactly why upstream's scorer returns 0.685
on marketing prose and 0.029 on Claude-authored technical docs.

**Commit-message length is process, not authorship.** Measured medians:

| Corpus | Median words | Driver |
| --- | --- | --- |
| `git/git` 2019 | 50 | no ticket system; the message is the documentation |
| CPython, curl | 16 | messages reference issue numbers |
| this owner, pre-AI | 3 | ticket-driven, context lived in the ticket |
| Claude here | 91 | no ticket, and asked to explain reasoning |

A 2019 git contributor and Claude both write long messages for the same
structural reason. "Verbose implies AI" is false.

**If revived**, `git/git` is the right control precisely because it is
process-matched — message-as-documentation on both sides — and the file-level
confound must be handled by holding out whole repositories, not files.

## Environment notes

- `python` is **not** on PATH. Use `uv run --python 3.12`.
- **Keep WSL to an absolute minimum.** Reserved for `scripts/test-linux.sh`
  only. Never use the `Debian-MW` distro; it is reserved. Querying git through
  WSL against `/mnt/c` produced a wrong answer during this work and it reached
  the documentation before being caught.
- Linux verification: `wsl.exe -d Debian -- bash scripts/test-linux.sh`, which
  uses **dagger**, not raw docker.
- `.gitattributes` pins `_vendor/**` to `eol=lf`. Without it, `refresh.sh
  --check` reports drift on pristine files under `core.autocrlf=true`.
- `site/` is gitignored. MkDocs ships 32 lunr language packs containing
  legitimate invisible characters, and this repo's own hook would strip them.

## GitHub Pages caveat

`.github/workflows/docs.yml` is written and builds clean locally, but **Pages
on a private repository needs GitHub Pro, Team or Enterprise**. On a free
private repo the deploy step will fail. Either make the repo public when
publishing docs, or drop the workflow until then.

## Review discipline

`.kiro/steering/review-effort.md` tiers it. Tier 1 gets a fresh adversarial
reviewer, Tier 2 is reviewed inline. Six checks are non-negotiable either way.
Mutation probes capped at three, chosen to hit different failure modes.

That calibration came from data: uniform maximum review cost ~81 minutes for
four foundation tasks, and every defect it found was in a task touching
behaviour or repo-wide config.
