# Research & Design Decisions

## Summary

- **Feature**: `watermark-detection`
- **Discovery Scope**: Extension (the `--check` path already ships and works)
- **Key Findings**:
  - Detection is **not** "removal with the write disabled", even though that is
    how it is currently implemented. It is the surface a human reads when
    judging a true positive and the surface CI reads when failing a build, so it
    carries reporting obligations removal does not have.
  - The dominant weakness is not the reporting format — it is **coverage**. In a
    ten-file test repository with one `U+200B` planted in each, the shipped hook
    scanned two. A gate that never looks at a file cannot report on it.
  - The read-only guarantee is currently **incidental**, not structural. It
    holds because `clean_one` returns before the write, not because the
    detection path is incapable of writing.

## Research Log

### How does detection currently under-report?

- **Context**: Requirement 2 demands that a clean result actually mean clean.
- **Findings**: Three distinct mechanisms, all confirmed by execution.
  1. **Concealment.** The frontmatter scan runs before the Unicode scan and
     anchors on a literal `---` at byte zero, so a BOM or a zero-width character
     hides provenance metadata from a single `--check` run entirely.
  2. **Run collapse.** A run of Mongolian free variation selectors reports one
     hit for forty, because the preservation guard tests the raw previous
     character — which is another selector.
  3. **Silent survivors.** Tag-char payloads behind a flag emoji, ZWJ between
     ASCII digits, and orthographic `Cf` marks are classified as legitimate and
     never surface at all.
- **Implications**: Every one of these is a *classification* defect, already
  owned by `watermark-removal`. Detection inherits the fix rather than
  duplicating it. What detection must add is a **conformance test** proving the
  two agree.

### Is `--check` genuinely incapable of writing?

- **Context**: Requirement 1 asks for a guarantee, not an observation.
- **Findings**: Verified that `--check` leaves files byte-identical, including
  the frontmatter-rewrite case. But the same function performs both roles and
  differs only by an early return, so the property is one edit away from being
  lost, and nothing tests it.
- **Implications**: Make it structural. Detection should call a function that
  computes a result and returns it, with the write living in a separate caller
  the detection path never reaches.

### What does the file-selection gap actually cost?

- **Context**: Requirement 7.
- **Findings**: `.mjs`, `.cjs`, `.html`, `.ipynb`, `.po`, `.tf`, `.Rmd` and
  extensionless files such as `Dockerfile` are unmatched. Separately, the regex
  is case-sensitive, so `README.MD` is skipped. Checking `identify` directly
  disproved the in-code rationale: it **does** know `.qml` (→ `qml`, `text`) and
  tags `.MD` as `markdown`; what it does not know is `.qmd` and `.Rmd`, which
  both return no tags.
- **Implications**: `types: [text]` unioned with a small `files:` pattern for
  Quarto and R Markdown covers strictly more than the hand-maintained list, and
  removes the case-sensitivity bug for free.

### Can a hook be prevented from running in the wrong stage?

- **Context**: Requirement 6.2–6.3. A validation run must not trigger a rewrite.
- **Findings**: Reproduced against pre-commit 4.6.2 — a hook that declares no
  `stages:` runs in **every** stage, so `--hook-stage manual` fired the autofix
  hook and rewrote the working tree. Fixed during review by pinning `wm-hook` to
  `pre-commit` and `wm-hook-check` to `manual`; the manifest validates.
- **Implications**: Explicit stages are a correctness requirement, not
  cosmetics. Worth a test, because the failure is silent and destructive.

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Verdict |
|--------|-------------|-----------|---------------------|---------|
| Keep `--check` as an early return | Status quo | Zero work; agreement is automatic | Read-only is incidental; no per-codepoint reporting; untestable guarantee | Rejected |
| Separate detection implementation | A dedicated scanner independent of the cleaner | Reporting freedom | Guarantees divergence between detect and clean — the exact bug class this tool exists to avoid | Rejected |
| **Shared classifier, separate presentation** | Both paths consume `classify()`; detection owns rendering and exit codes | Agreement is structural; read-only by construction; reporting is free to evolve | Cross-spec coupling must be managed | **Selected** |

## Design Decisions

### Decision: Detection and removal share one classifier, differ only in what they do with the result

- **Context**: Requirement 2.1–2.2 demands that detection and removal never
  disagree. `structure.md` records this as a load-bearing invariant.
- **Selected Approach**: `watermark-removal` owns `classify()` and
  `clean_document()`. Detection calls `clean_document()` for its decisions and
  simply **discards the text**, rendering `FileResult` instead. The write lives
  only in the removal caller.
- **Rationale**: Agreement becomes structural rather than a property to
  maintain. Read-only becomes a consequence of never calling the writer.
- **Trade-offs**: Detection computes the cleaned text it throws away — wasted
  work, but bounded by the existing size cap and far cheaper than divergence.
- **Follow-up**: A conformance test asserting `detect(f).clean == (clean(f)
  makes no change)` over both corpora.

### Decision: Findings are structured values; formatting is a separate layer

- **Context**: Requirements 3 and 4 want per-codepoint detail and machine-readable
  output without forcing one to be derived from the other's text.
- **Selected Approach**: A `Finding` value object carrying codepoint, name,
  count, offsets, carrier class and confidence. Two renderers — human and JSON —
  consume the same list.
- **Rationale**: Guarantees the two formats cannot drift, and satisfies
  Requirement 4.1's "every field available in the human report".

### Decision: "Skipped" is a first-class outcome, not a flavour of clean

- **Context**: Requirement 5.4. Today a binary or oversize file exits `0`,
  indistinguishable from a checked-and-clean file.
- **Selected Approach**: Four outcomes — `CLEAN`, `MARKED`, `SKIPPED`, `ERROR` —
  each represented in both renderers, with a `--strict` flag promoting `SKIPPED`
  to failure (Requirement 5.5).
- **Trade-offs**: A third exit-code dimension; mitigated by keeping the default
  exit mapping exactly as it is today.

## Risks & Mitigations

- **Cross-spec drift** — the removal spec changes `Decision` or `FileResult` and
  detection's rendering silently degrades. *Mitigation*: both listed as
  revalidation triggers in the removal design; the conformance test fails fast.
- **Widening `files:` causes mass churn** — scanning `.html` and `.ipynb` for the
  first time surfaces many findings at once. *Mitigation*: ship the widened
  pattern with the validation hook first so adopters see a report before an
  autofix touches anything.
- **JSON output mistaken for a provenance verdict** — a `clean` result read as
  "not AI-generated". *Mitigation*: Requirement 9; the scope caveat is a field
  in the structured output, not just prose in a README.

## References

- `.kiro/specs/watermark-removal/design.md` — the classifier and `FileResult`
  contracts this spec consumes.
- `.kiro/steering/structure.md` — the "one decision function" invariant.
- pre-commit 4.6.2 stage-selection behaviour, verified locally.
- `identify` 2.6.19 tag coverage, verified locally.
