# Implementation Plan — watermark-removal

> Order implies dependency. Tasks marked `(P)` have no dependency on their
> immediately preceding peers and may run concurrently with them.
>
> **Each implementation task ships its own unit-test module.** A task's
> `_Boundary:_` covers both the production module and its matching test module.
> Group 4 owns only the cross-cutting suites, so no two tasks ever contend for
> the same test file. (Group 4 cannot overlap group 2 in time — it depends on
> group 3 — but the file-ownership rule is what keeps the `(P)` markers within
> each group safe.)

- [ ] 1. Foundation: import access, test harness, and the corpora

- [x] 1.1 Establish the test harness
  - Add a dev dependency group and a test runner configuration to the project
    metadata; the repository currently has no test suite at all.
  - Provide shared fixtures for building a throwaway working tree, writing a
    file with exact bytes, constructing policy variants, and enumerating an
    annotated corpus directory.
  - Observable: the runner collects and passes a sentinel test that exercises
    the throwaway-tree fixture, a policy-variant factory, and the corpus
    enumeration helper.
  - _Boundary: tests/conftest.py_

- [ ] 1.2 Provide constants-only access to the vendored tables
  - The vendored modules import each other by bare name and are currently
    reachable only through a path insertion performed inside the command-line
    entry point; owned modules and tests must not depend on that entry point.
  - Establish a single import shim exposing the vendored **codepoint** tables to
    owned modules. Measurement confirms the Unicode module is standalone and
    side-effect free, so this costs nothing.
  - Do **not** route the frontmatter key vocabulary through it. Importing that
    module pulls two others and mutates process stdio, all for two constants;
    the vocabulary is re-declared in the key-policy task instead.
  - Observable: importing the classifier module in a bare test process, with the
    command-line entry point never imported, succeeds and leaves the process
    output encoding unchanged.
  - _Boundary: _tables_

- [ ] 1.3 (P) Build the preservation corpus
  - Assemble files that must survive cleaning byte-identically: emoji joiner
    sequences and a subdivision flag; Persian, Urdu and Arabic with joiners at
    end-of-value, before punctuation, beside digits and before a newline; Thai,
    Lao, Khmer and Myanmar using the zero-width word separator; ideographic text
    with a single legal variation selector per base; Devanagari conjuncts;
    icon-font glyphs; French typography using no-break and narrow no-break
    spaces; CRLF Markdown with frontmatter; a byte-order-marked comma-separated
    file; a latin-1 file.
  - Annotate each entry with the rule that protects it, so a future change
    cannot silently reclassify it.
  - Observable: every entry is enumerable and carries a protecting-rule
    annotation.
  - _Requirements: 11.1_
  - _Boundary: tests/corpus/preservation_
  - _Depends: 1.1_

- [ ] 1.4 (P) Build the carrier corpus
  - Assemble files that must be cleaned: zero-width binary payloads; tag-block
    smuggling both bare and hidden behind a flag emoji; variation-selector byte
    smuggling on ideographic bases; joiners between ASCII digits; directional
    overrides; free-floating private-use characters; provenance frontmatter keys
    both plain and concealed behind an invisible character.
  - Annotate each entry with **the policy it is expected to be cleaned under**
    and **the residue it may legitimately retain**. Several entries are not
    cleaned under the default policy — private-use characters are preserved by
    default, and a smuggled run on legal bases legitimately retains its first
    selector under the selector-run rule recorded in the design's classifier
    notes and implemented in 2.5.
  - Observable: every entry carries an expected-policy and expected-residue
    annotation, and no entry asserts removal under a policy that preserves it.
  - _Requirements: 11.4_
  - _Boundary: tests/corpus/carriers_
  - _Depends: 1.1_

- [ ] 2. Core: the owned policy layer

- [ ] 2.1 Define the transform policy value object
  - Provide one immutable flag per risky transform, with a documented default
    for each, and a constructor for the safe default set.
  - Three defaults change from today's behaviour: private-use characters are
    preserved, a required byte-order mark is preserved, and space normalisation
    becomes position-aware.
  - Observable: constructing the default policy yields the documented values,
    and each field carries its rationale.
  - _Requirements: 9.1, 9.2, 9.3, 9.4_
  - _Boundary: policy_

- [ ] 2.2 (P) Implement document segmentation
  - Classify every offset as preamble, frontmatter delimiter, frontmatter body,
    or document body, tolerating a leading byte-order mark and invisible
    characters when locating the opening delimiter.
  - Distinguish a genuine frontmatter block from a leading thematic break by
    requiring a key-like line to follow the opening delimiter, and treat an
    unterminated block as ordinary body text.
  - Mark positions where a space would be structurally significant: the start of
    a line inside a frontmatter region, and the start of a line in a standalone
    configuration document.
  - Detect the line-ending convention and the trailing-newline state, and mark
    offset zero so the classifier can distinguish a leading byte-order mark from
    an interior one without needing to know the file's format.
  - Observable: regions tile the document exactly with no gaps or overlaps, and
    a thematic-break document reports no frontmatter.
  - _Requirements: 1.3, 4.1, 4.2, 5.4, 5.6, 6.5, 7.3_
  - _Boundary: regions_

- [ ] 2.3 (P) Implement the mode-preserving atomic write
  - Capture the original file's permissions, write through a temporary file in
    the same directory, restore the captured mode, flush to disk, and move it
    into place.
  - Refuse to write through a symbolic link, and on any failure leave the
    original untouched with no temporary file left behind.
  - Skip permission restoration on platforms without POSIX modes.
  - Observable: rewriting an executable script leaves it executable, and an
    induced mid-write failure leaves the original bytes intact.
  - _Requirements: 8.1, 8.2, 8.3_
  - _Boundary: atomic_

- [ ] 2.4 Implement the character classifier
  - Build the single decision function that both cleaning and detection will
    use, returning the action, the surviving character, the carrier class, and
    the reason a rule fired or declined.
  - Consume the vendored codepoint tables as data through the shim; do not
    import or call the vendored decision function in production code.
  - Evaluate every context-dependent rule against the previous surviving **base**
    rather than the raw previous character, so a run of carriers cannot mask
    itself and every member of the run is removed.
  - Resolve the byte-order-mark ambiguity by **position, not format**: a mark at
    offset zero is preserved unless the policy opts into stripping it; every
    interior occurrence is a carrier and is stripped. The classifier is never
    told the file's format, so a format-conditional rule would be unimplementable.
  - Observable: a run of forty consecutive selectors is fully removed in one
    call, where today one is removed per invocation.
  - _Requirements: 1.1, 1.2, 2.1, 2.4, 2.5, 2.6, 6.5, 10.3_
  - _Boundary: classify_
  - _Depends: 1.2, 2.1_

- [ ] 2.5 Correct the emoji, flag and selector-run rules
  - Widen the emoji base set so presentation selectors survive after the five
    bases currently missing, and narrow it so ASCII digits and the hash and
    asterisk characters count as bases only inside a genuine keycap sequence.
  - State the selector-run rule explicitly: a **single** selector after a legal
    base is preserved, and every subsequent selector in the run is contraband.
    This is what separates legitimate ideographic variation from byte smuggling
    on the same bases.
  - Bound subdivision-flag tag payloads to a conforming length and alphabet, so
    an arbitrary-length hidden payload behind a flag is treated as contraband.
  - Add a regression case for each defect this task closes.
  - Observable: an information-source emoji keeps its presentation selector, a
    joiner between two ASCII digits is removed, a long tag payload behind a flag
    is stripped, and a smuggled selector run retains only its first member.
  - _Requirements: 2.2, 2.3, 3.1, 3.2, 11.5_
  - _Boundary: classify_
  - _Depends: 2.4_

- [ ] 2.6 Correct the script-preservation rules
  - Preserve the zero-width separator where the surrounding script uses it as a
    word or line break.
  - Extend joiner preservation to the edge positions where it is currently lost:
    end of a value, before punctuation, beside a digit, and before a line break.
  - Preserve private-use characters under the default policy, and preserve
    directional marks and correctly paired embeddings.
  - Add a regression case for each defect this task closes.
  - Observable: every corpus entry protected by *this task's* rules classifies as
    unchanged — Arabic, Persian and Urdu joiners at edge positions; Thai, Lao,
    Khmer and Myanmar separators; icon-font glyphs; Devanagari conjuncts;
    directional marks. Space homoglyphs are 2.7's, and whole-file byte-identity
    is 3.1's.
  - _Requirements: 3.3, 3.4, 3.5, 3.6, 3.7, 11.5_
  - _Boundary: classify_
  - _Depends: 1.3, 2.4_

- [ ] 2.7 Make space handling position-aware
  - Suppress space replacement at any position segmentation marked structurally
    significant, regardless of policy. Correctness outranks configuration: no
    policy flag may re-enable a replacement at such a position.
  - Where a space homoglyph would, once replaced, conceal provenance metadata
    from later processing, remove it instead of replacing it. This is one half
    of the concealed-key behaviour; the key-pattern half lands in 2.8 and the
    joint outcome is asserted in 4.1.
  - Honour the normalisation flag everywhere else, leaving all space homoglyphs
    untouched when it is disabled.
  - Observable: a configuration document with a no-break space at the start of a
    line still parses after cleaning and the provenance key it precedes is
    removed; with normalisation disabled, every space homoglyph in the
    French-typography corpus file is left unchanged.
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 11.5_
  - _Boundary: classify_
  - _Depends: 1.3, 2.2, 2.4_

- [ ] 2.8 (P) Implement the provenance key policy
  - Re-declare the key vocabulary locally, split into names that always indicate
    provenance and ambiguous names that are also ordinary domain terms. It is
    re-authored rather than imported because the split is required anyway and
    importing the vendored source carries a stdio side effect.
  - Add a drift test that imports the vendored vocabulary — in tests only, where
    the side effect is harmless — and asserts the local sets account for every
    upstream key, so an upstream addition cannot go unnoticed.
  - Report a drop verdict when a key name is unconditionally provenance-bearing,
    or when an ambiguous name is corroborated by its value; never report a drop
    on a value match alone.
  - Report each dropped key as a line span covering its nested block and list
    continuation lines, and signal when every key in the block has been dropped.
    This task reports spans only — the text rewrite belongs to the pipeline.
  - Tolerate a leading run of invisible or space-homoglyph characters in the key
    pattern so a concealed key is caught on the first pass. This is the other
    half of the concealed-key behaviour begun in 2.7.
  - Observable: a title mentioning an AI vendor reports keep; a generator key
    reports a drop span covering its nested continuation lines; a plain model key
    reports keep while a model key naming a chat model reports drop; a block
    whose every key dropped reports the emptied signal.
  - _Requirements: 5.1, 5.2, 5.3, 5.5_
  - _Boundary: frontmatter_
  - _Depends: 1.2, 2.2_

- [ ] 3. Integration: pipeline, reporting, and entry point

- [ ] 3.1 Assemble the single-pass cleaner
  - Run segmentation once, classify every character with its region and column,
    apply the key policy's drop spans within the frontmatter region, and
    reassemble by splicing untouched lines verbatim so line endings, blank lines
    and indentation survive.
  - Report a change only when the output bytes actually differ from the input,
    so the caller has an unambiguous signal and never writes needlessly. This
    task is pure — it returns a result and performs no I/O.
  - Preserve undecodable bytes across the decode and encode boundary.
  - Observable: a mark-free file yields a result reporting no change, and every
    preservation-corpus file emerges byte-identical.
  - _Requirements: 1.4, 6.1, 6.2, 6.3, 6.4, 6.6_
  - _Boundary: clean_
  - _Depends: 1.3, 2.2, 2.4, 2.5, 2.6, 2.7, 2.8_

- [ ] 3.2 Surface what was removed
  - Aggregate the pipeline's decisions into a reportable result: each distinct
    codepoint removed or replaced with its Unicode name and count, each dropped
    provenance field by name, and the rules that fired to protect content.
  - Ensure a file is never reported as modified when no bytes changed.
  - Observable: cleaning a file containing a zero-width payload and a generator
    key reports the codepoint by name with its count, names the dropped field,
    and lists any declined transformation.
  - _Requirements: 10.1, 10.2, 10.3, 10.4_
  - _Boundary: clean_
  - _Depends: 3.1_

- [ ] 3.3 Rewire the command-line entry point
  - Reduce the entry point to path handling, gating, document-kind routing and
    status aggregation, with all cleaning delegated to the pipeline.
  - Derive the document kind from the path suffix — the markdown set including
    Quarto, and the configuration-document set — and pass it to the pipeline;
    nothing downstream can infer it.
  - Expose one option per policy field, defaulting to the safe default set, so
    an adopter can disable a risky transform through hook arguments.
  - Treat oversize input as a skip rather than an error so one large file cannot
    fail an entire run, and keep binary files skipped and unmodified. Report an
    unreadable path and continue with the remaining paths.
  - Land the adopter-visible consequences in the same change: the manifest and
    the README must record the changed defaults and the oversize-input
    reclassification.
  - Observable: a run mixing a clean file, a marked file, a binary file, an
    oversize file and a missing path reports each distinctly and processes all of
    them; a file the pipeline reports as unchanged is never opened for writing;
    disabling space normalisation through a hook argument leaves homoglyphs
    intact.
  - _Requirements: 8.4, 8.5, 8.6, 9.1, 9.2, 9.3, 9.4_
  - _Boundary: cli_
  - _Depends: 2.3, 3.2_

- [ ] 4. Validation: guarantees enforced by tests

- [ ] 4.1 Prove single-pass convergence
  - Assert for every corpus file that a second cleaning run reports no change
    and produces identical bytes.
  - Cover each concealment case explicitly: a byte-order mark before the
    frontmatter, and an invisible character inside a key name.
  - Include the case that never converged before: a no-break space at the start
    of a frontmatter line must, in one pass, leave the document parseable and
    remove the provenance key. This is the joint outcome of 2.7 and 2.8.
  - Observable: no corpus file requires a second pass, and the previously
    non-converging case is covered by a named regression test.
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 11.2, 11.5_
  - _Boundary: tests/test_convergence.py_
  - _Depends: 1.3, 1.4, 3.1_

- [ ] 4.2 (P) Prove byte-level fidelity
  - Assert byte-identical output for mark-free inputs across each line-ending
    convention, with and without frontmatter, with and without a trailing
    newline, and with a byte-order mark where the format requires one.
  - Include the two spurious-rewrite cases: CRLF Markdown with frontmatter, and
    a frontmatter block with leading or trailing blank lines.
  - Observable: no mark-free input produces a diff.
  - _Requirements: 11.3_
  - _Boundary: tests/test_fidelity.py_
  - _Depends: 1.3, 3.1_

- [ ] 4.3 (P) Prove carrier removal
  - Assert that every carrier-corpus entry is cleaned **under the policy its
    annotation names**, not under a single blanket policy.
  - Assert per entry that the payload is destroyed and the file changes, allowing
    the residue its annotation permits rather than requiring a blanket
    no-carrier re-scan.
  - Observable: each entry changes under its annotated policy, and entries
    annotated as preserved under the default policy are asserted unchanged there.
  - _Requirements: 11.4_
  - _Boundary: tests/test_carriers.py_
  - _Depends: 1.4, 3.1_

- [ ] 4.4 Record and enforce divergence from the vendored classifier
  - Enumerate every character-in-context where the owned classifier disagrees
    with the vendored decision function, and assert the set equals a recorded
    list carrying a justification per entry.
  - Assert that production modules reach the vendored package only through the
    constants shim, and never import its decision or write functions.
  - Assert that the vendored files still match their recorded hashes.
  - Observable: an unjustified behavioural divergence, or an upstream refresh
    that changes semantics, fails the suite with a named diff.
  - _Requirements: 11.5_
  - _Boundary: tests/test_divergence.py_
  - _Depends: 2.5, 2.6, 2.7, 2.8, 3.3_

- [ ] 4.5 (P) Re-sync the structure steering document
  - The repository no longer has a single original source file; update the
    organisation patterns to describe the owned policy layer, the constants-only
    dependency rule on the vendored package, and where a new rule belongs.
  - Observable: the steering document names each owned module with its
    responsibility, and states the constants-only rule as a rule.
  - _Boundary: .kiro/steering/structure.md_
  - _Depends: 3.3_

## Deferred with rationale

- **Exit-code semantics are not scheduled here.** Requirement 1's boundary and
  the design's Out of Boundary both assign them to `watermark-detection`, whose
  tasks **1.1** (outcome taxonomy and exit-code aggregation) and **4.4**
  (end-to-end exit code per documented outcome) own them. Task 3.3 asserts only
  that each outcome is produced and distinguishable, not which numeric code it
  maps to.

- **Tasks without a requirement anchor.** 1.1, 1.2 and 4.5 carry no
  `_Requirements:_` line by design: the first two are foundation work that
  enables every later assertion without itself being an acceptance criterion,
  and 4.5 is a steering re-sync mandated by the design's Modified Files. Every
  one of the 57 requirement IDs is anchored on a task that actually implements
  it.

## Implementation Notes

- **1.1** — `python` is not on PATH on this machine; use `uv run --python 3.12`.
  `refresh.sh --check` cannot run here at all (it shells out to `python3`), so
  verify vendored hashes inline instead. Hash the **LF-normalized** bytes:
  `.gitattributes` pins `_vendor/**` to `eol=lf` precisely so the working tree
  matches `VENDORED.json`.
- **1.1** — Use PEP 735 `[dependency-groups]`, never
  `[project.optional-dependencies]`, for dev tooling. An extra leaks
  `Provides-Extra`/`Requires-Dist` into wheel metadata and breaks the
  stdlib-only runtime contract.
- **1.1** — Test data must never contain a *literal* invisible carrier. This
  repo's own hook would rewrite the test file and silently corrupt the
  constant. Always write carriers as `\uXXXX` escapes.
- **1.1** — `POLICY_FIELD_DEFAULTS` in `tests/conftest.py` restates
  `CleanPolicy`'s fields and defaults. **Task 2.1 must add the drift assertion**
  against the real value object; it belongs in 2.1's boundary, not the harness.

## Cross-spec revalidation raised

- Task 3.3 reclassifies oversize input from an error to a skip. The
  outcome-to-exit-code *mapping* is unchanged, but the outcome an oversize file
  produces changes, moving its net exit code from `2` to `0`. This must be
  reflected in `watermark-detection` task 1.1, whose bullets promise a default
  mapping identical to today's.
