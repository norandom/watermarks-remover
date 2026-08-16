# Implementation Plan — watermark-detection

> Order implies dependency. Tasks marked `(P)` have no dependency on their
> immediately preceding peers and may run concurrently with them.
>
> **Each implementation task ships its own unit-test module.** A task's
> `_Boundary:_` covers both the production module and its matching test module.
>
> **Cross-spec prerequisite.** This plan consumes the pipeline and result
> contract produced by `watermark-removal` tasks 3.1 and 3.2. Nothing in group 2
> onward can start until those land; this is stated once here rather than
> repeated on every task.

- [ ] 1. Foundation: outcome taxonomy

- [ ] 1.1 Define the outcome taxonomy and exit-code aggregation
  - Provide four distinct per-file outcomes — clean, marked, skipped, error —
    each carrying its findings or its skip/error reason, so a file that could not
    be checked is never indistinguishable from one checked and found clean.
  - Aggregate a run to a single exit code by severity, with error dominating
    marked, which dominates skipped, which dominates clean.
  - Provide a strict mode that promotes a skipped file to a run failure, and
    nothing else.
  - Keep the outcome-to-exit-code mapping identical to today's so adopting this
    does not break existing pipelines. Note one deliberate net change originating
    in `watermark-removal` task 3.3: an oversize file becomes a skip rather than
    an error, moving its exit code from `2` to `0`. That is a change of outcome,
    not of mapping, and it is the one case where a previously failing run now
    passes by default — `--strict` restores the failure.
  - Observable: every outcome combination maps to the documented exit code, and
    a skipped-only run exits successfully by default and unsuccessfully under
    strict mode.
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  - _Boundary: outcome_

- [ ] 2. Core: findings and presentation

- [ ] 2.1 Derive reader-facing findings from cleaning decisions
  - Group the pipeline's decisions by codepoint, retain a capped list of
    positions, and count every occurrence.
  - Assign each finding a carrier class and a confidence level, so a reader can
    distinguish a space homoglyph from a zero-width carrier and a contextual
    signal from a parsed provenance claim.
  - Name the field for a provenance finding, which has no codepoint.
  - Derive everything from the pipeline's result and never re-examine the text,
    so a finding cannot contradict what cleaning would do.
  - Order findings deterministically so reports are diffable.
  - Observable: a file with a known payload yields the expected codepoint, name,
    count, at least one position, carrier class and confidence; a dropped
    provenance key yields a finding naming the field and carrying no codepoint.
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  - _Boundary: findings_

- [ ] 2.2 (P) Render the human-readable report
  - Present per-file findings with codepoint, name, count, class and confidence,
    and summarise a multi-file run so it stays readable.
  - State on every clean result that the scan covers deterministic carriers only,
    and never phrase a clean result as evidence that text is not model-generated.
  - Observable: a clean multi-file run prints a summary carrying the scope
    qualification, and no output phrases a result as an absence-of-AI verdict.
  - _Requirements: 3.6, 9.1, 9.2, 9.3_
  - _Boundary: render_text_
  - _Depends: 2.1_

- [ ] 2.3 (P) Render the machine-readable report
  - Emit a versioned structured document containing every field present in the
    human report, plus the active policy, a run summary, and one entry per file
    including skipped and errored files.
  - Always include a scope object naming the excluded watermark class and the
    known detection limitations, so a consumer cannot read a clean result as a
    provenance verdict.
  - Produce a valid document when there are no findings at all.
  - Observable: output parses as valid structured data for a zero-finding run, a
    skipped-only run and a mixed run, and every human-report field is present.
  - _Requirements: 4.1, 4.3, 4.4, 9.4_
  - _Boundary: render_json_
  - _Depends: 2.1_

- [ ] 3. Integration: the read-only entry point

- [ ] 3.1 Wire validation through the shared pipeline
  - Run the shared cleaning pipeline, discard the cleaned text, and keep only the
    decisions, so the read-only guarantee is structural rather than a matter of
    returning early.
  - Gate binary and oversize inputs to a skip with an explicit reason, and report
    an unreadable path as an error while continuing with the remaining paths.
  - Observable: a validation run over a mixed set leaves every input byte- and
    timestamp-identical, and reports each of the four outcomes distinctly.
  - _Requirements: 1.1, 1.2, 1.3, 2.1, 2.2, 5.6, 7.3_
  - _Boundary: cli_
  - _Depends: 1.1, 2.1_

- [ ] 3.2 Route output streams and harden invocation
  - Send structured output to the primary output stream and all diagnostics to
    the error stream, so a pipeline can parse one without filtering the other.
  - Add the options selecting structured output and strict mode.
  - Exit successfully and silently when no paths are supplied; treat a path
    beginning with an option prefix as a path; force an output encoding capable
    of representing every codepoint the report can name.
  - Observable: structured output can be piped to a parser while the human report
    is captured separately, and a file named like an option is scanned rather
    than rejected.
  - _Requirements: 4.2, 8.1, 8.2, 8.3, 8.4_
  - _Boundary: cli_
  - _Depends: 2.2, 2.3, 3.1_

- [ ] 3.3 Widen and correct hook file selection
  - Replace the hand-maintained case-sensitive extension list with type-based
    selection unioned with an explicit pattern for the two formats the type
    database does not recognise — Quarto and R Markdown.
  - This fixes coverage and case-sensitivity together: the eight formats that
    currently escape scanning, and uppercase extensions, both become matched.
  - Keep explicit stages on both hook ids so a validation run cannot fire the
    rewriting hook, and record in each id's description whether it modifies
    files.
  - Ship the widened pattern on the validation hook first, so adopters receive a
    report before an autofix touches anything.
  - Observable: the manifest validates, and each id declares its stage and its
    mutation behaviour.
  - _Requirements: 6.1, 6.2, 6.3, 6.5, 7.1, 7.2, 7.5_
  - _Boundary: .pre-commit-hooks.yaml_

- [ ] 4. Validation: guarantees enforced by tests

- [ ] 4.1 Prove the read-only guarantee
  - Assert over both corpora, plus induced error and skip cases, that every input
    file's bytes and modification time are unchanged after a validation run.
  - Assert statically that no detection module imports the write path.
  - Observable: no validation code path mutates a file, and an accidental future
    import of the writer fails the suite.
  - _Requirements: 1.1, 1.2, 1.3, 1.4_
  - _Boundary: tests/test_readonly.py_
  - _Depends: 3.1_

- [ ] 4.2 (P) Prove detection and removal agree
  - Assert for every corpus file in both directions: a clean detection result
    implies the cleaner makes no change, and a marked result implies it does.
  - Cover the cases where detection previously under-reported: a mark concealed
    behind a byte-order mark, and a run of carriers counted as one.
  - Observable: no corpus file produces disagreement between the two paths, and
    a run of forty carriers reports forty.
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 10.2_
  - _Boundary: tests/test_conformance.py_
  - _Depends: 3.1_

- [ ] 4.3 (P) Prove carrier detection and scope honesty
  - Assert that each published technique the tool claims to detect produces a
    finding, using the carrier corpus and its per-entry policy annotations.
  - Assert that techniques known to be undetected are named as limitations in the
    output rather than passing silently as clean.
  - Observable: every claimed technique reports a finding, and every known
    limitation appears in the structured output's scope object.
  - _Requirements: 2.6, 10.3_
  - _Boundary: tests/test_carrier_detection.py_
  - _Depends: 2.3, 3.1_

- [ ] 4.4 Prove outcome and stage behaviour end to end
  - Assert the exit code for each documented outcome including the skipped case,
    through the real entry point.
  - Run each hook id in the other's stage against a scratch consumer repository
    and assert it does not fire, and that a manual-stage run leaves the working
    tree unchanged.
  - Observable: the stage isolation test fails if either id loses its explicit
    stage declaration — the silent, destructive failure this guards against.
  - _Requirements: 6.4, 10.4, 10.5_
  - _Boundary: tests/test_outcome_e2e.py, tests/test_hook_stages.py_
  - _Depends: 3.2, 3.3_

- [ ] 4.5 Prove file-selection coverage
  - Build a scratch repository with one carrier planted in each of the formats
    that currently escape scanning, plus an uppercase-extension file and an
    extensionless text file.
  - Assert the validation hook reports every one of them — the direct regression
    guard for the coverage failure where eight of ten planted carriers survived.
  - Assert that an extensionless file is scannable by explicit path.
  - Observable: all planted carriers are reported, where the current
    configuration reports two.
  - _Requirements: 7.1, 7.2, 7.4, 10.3_
  - _Boundary: tests/test_selection_coverage.py_
  - _Depends: 3.3, 3.2_

- [ ] 4.6 Prove structured-output stability
  - Assert the structured document's shape for zero-finding, skipped-only and
    mixed runs, and that the scope object is present in all of them.
  - Assert that the human report and the structured report never disagree on
    findings for the same input.
  - Observable: a schema check passes for every run shape, and a field present in
    one renderer is present in the other.
  - _Requirements: 4.1, 4.3, 4.4, 10.1_
  - _Boundary: tests/test_render_json.py_
  - _Depends: 2.2, 2.3_
