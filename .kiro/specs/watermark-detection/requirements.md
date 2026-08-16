# Requirements Document

## Project Description (Input)

**Who has the problem.** Teams who want a repository *gated* on AI provenance
marks rather than silently rewritten — CI owners who need a build to fail with
an actionable report, reviewers who need to know what a file contains before
deciding to clean it, and maintainers of prose repositories where the autofix
path is too destructive to enable.

**Current situation.** A validation mode exists: `wm-hook --check` runs the
same detection path as removal, short-circuits before the write, and exits `1`
if any file would change. Verified by execution: it does not modify the file.
Until this session `.pre-commit-hooks.yaml` exposed only the autofix hook id,
so validation was unreachable through the framework adopters actually use; a
`wm-hook-check` id has now been added.

An adversarial review confirmed the remaining gaps by execution: reporting is
counts rather than codepoints; there is no machine-readable output; detection
under-reports (a run of carriers is counted as one, and a mark hidden behind a
byte-order mark is missed entirely); several published carrier techniques are
reported as clean; the file-selection pattern misses most ordinary text
formats; and a file skipped as binary is indistinguishable from a file that was
checked and found clean.

**What should change.** Validation must become a first-class, trustworthy
reporting surface: per-codepoint findings with offsets and confidence, optional
machine-readable output, a detection result that provably matches what removal
would do, complete counts, and an unambiguous signal when a file was skipped
rather than cleared. Detection must never write to disk under any code path.

## Introduction

This specification defines the **read-only path** of `wm-hook`: detecting and
reporting AI provenance marks without modifying anything, and the hook and CI
surfaces through which that detection is invoked.

Detection is not merely "removal with the write disabled". It is the surface a
human reads when deciding whether a finding is a true positive, and the surface
CI reads when deciding whether to fail a build. It therefore carries reporting
and completeness obligations that removal does not.

The subject of all acceptance criteria is **the Detector**.

## Boundary Context

- **In scope**: read-only inspection of text files; the content, granularity
  and confidence of findings; machine-readable output; exit-code semantics;
  the distinction between "clean", "skipped" and "failed"; hook ids, stage
  assignment and file selection; completeness against published carrier
  techniques.

- **Out of scope**:
  - **Any modification of any file.** Detection is read-only under every code
    path, including error paths.
  - **What gets removed and what gets preserved** — owned by the
    `watermark-removal` spec. Detection reports; it does not decide policy.
  - **Layer B statistical watermarks.** Out of scope permanently, and the
    reporting must say so rather than implying that a clean result means the
    text is not model-generated.
  - **Remediation guidance beyond naming the finding.** The Detector reports
    what is present; it does not propose rewrites.

- **Adjacent expectations**:
  - The `watermark-removal` spec owns the classification of each character.
    The Detector expects to share that classification exactly, so that a clean
    detection result guarantees a no-op removal run and vice versa.
  - The pre-commit framework owns invocation, file enumeration and stage
    selection. The Detector expects to receive an explicit list of paths.
  - CI systems consume the exit code and, where enabled, the machine-readable
    output.

## Requirements

### Requirement 1: Read-only guarantee

**Objective:** As a CI owner, I want validation to be incapable of modifying my
working tree, so that I can run it on untrusted branches and on a clean
checkout.

#### Acceptance Criteria

1. While operating in validation mode, the Detector shall not create, modify,
   delete, or change the metadata of any file.
2. If an error occurs during validation, then the Detector shall still leave
   every input file unmodified.
3. When validation reports that a file would change, the Detector shall leave
   that file byte-for-byte identical.
4. The Detector shall be invocable through the hook framework in a form that
   cannot trigger the rewrite path.

### Requirement 2: Detection completeness and agreement with removal

**Objective:** As a reviewer, I want a clean validation result to actually mean
clean, so that a passing gate is meaningful.

#### Acceptance Criteria

1. When the Detector reports a file as clean, a removal run on that same file
   shall make no change.
2. When the Detector reports that a file would change, a removal run on that
   same file shall change it.
3. The Detector shall detect every mark that a removal run would act on,
   including marks that are concealed by another mark.
4. When a run of carriers of the same class appears consecutively, the Detector
   shall report the count of every character in the run.
5. When a carrier is present at a position where a preservation rule does not
   apply, the Detector shall report it regardless of the surrounding
   characters.
6. If a published carrier technique is known to be undetected, then the
   Detector shall document it as a known limitation rather than report the file
   as clean without qualification.

### Requirement 3: Per-finding reporting granularity

**Objective:** As a developer whose build just failed, I want to see exactly
which characters were found and where, so that I can judge whether the finding
is a true positive.

#### Acceptance Criteria

1. When the Detector reports a finding, it shall identify the codepoint, its
   Unicode name, and the number of occurrences.
2. When the Detector reports a finding, it shall provide at least one position
   within the file at which the finding occurs.
3. The Detector shall classify each finding by carrier class, so that a reader
   can distinguish a zero-width carrier from a space homoglyph.
4. The Detector shall assign each finding a confidence level, so that a reader
   can distinguish a strong provenance signal from a contextual one.
5. When the Detector finds provenance metadata, it shall name the field.
6. The Detector shall summarize per-file results so that a run over many files
   remains readable.

### Requirement 4: Machine-readable output

**Objective:** As a CI owner, I want structured output, so that I can annotate
a diff and track findings over time.

#### Acceptance Criteria

1. Where machine-readable output is requested, the Detector shall emit findings
   in a structured format containing every field available in the human-readable
   report.
2. Where machine-readable output is requested, the Detector shall emit it on a
   stream separate from diagnostic messages, so that it can be parsed without
   filtering.
3. The Detector shall produce valid structured output even when no findings are
   present.
4. When a file is skipped or fails, the Detector shall represent that outcome in
   the structured output rather than omitting the file.

### Requirement 5: Unambiguous outcome signalling

**Objective:** As an operator, I want to distinguish "checked and clean" from
"could not check", so that a gate cannot pass by accident.

#### Acceptance Criteria

1. When every supplied file is checked and carries no marks, the Detector shall
   exit with a success status.
2. When at least one file carries a mark, the Detector shall exit with a
   distinct failure status reserved for that outcome.
3. If at least one file cannot be read, then the Detector shall exit with a
   status distinct from both "clean" and "marks found".
4. When a file is skipped because it is binary or exceeds the size limit, the
   Detector shall report the skip explicitly and shall not represent that file
   as clean.
5. Where a strict mode is requested, the Detector shall treat a skipped file as
   a failure.
6. The Detector shall report every problematic file in a run, rather than
   stopping at the first one.

### Requirement 6: Hook and CI integration

**Objective:** As an adopter, I want to choose between gating and autofixing,
so that I can pick the behavior my repository can tolerate.

#### Acceptance Criteria

1. The hook manifest shall expose a validation-only hook id distinct from the
   autofix hook id.
2. When a run selects the validation hook, the autofix hook shall not execute.
3. The hook manifest shall declare explicit stages for every hook id it
   defines, so that no hook executes in a stage the adopter did not select.
4. When an adopter runs the validation hook over an entire repository, the
   Detector shall report every matching file without modifying the working
   tree.
5. The hook manifest shall document, for each hook id, whether it modifies
   files.

### Requirement 7: File selection coverage

**Objective:** As a maintainer, I want the gate to look at the text files my
repository actually contains, so that a passing result is not an artifact of
files never having been scanned.

#### Acceptance Criteria

1. The file-selection pattern shall match the common text formats in which
   pasted model output appears, including notebook, templating, translation,
   infrastructure and web formats.
2. The file-selection pattern shall match a given format regardless of the
   letter case of its extension.
3. If a matched file's contents indicate a binary format, then the Detector
   shall skip it and report the skip.
4. Where a file has no recognized extension, the Detector shall be invocable on
   it by explicit path.
5. The Detector shall document which formats are covered and which are not, so
   that an adopter can extend the pattern deliberately.

### Requirement 8: Invocation robustness

**Objective:** As an operator, I want the gate to survive unusual inputs, so
that one odd filename cannot disable the check for an entire repository.

#### Acceptance Criteria

1. When the Detector is invoked with no paths, it shall exit successfully
   without error output.
2. If a supplied path begins with a character that resembles an option prefix,
   then the Detector shall treat it as a path.
3. If a supplied path cannot be read, then the Detector shall report that path
   and continue processing the remaining paths.
4. The Detector shall produce its diagnostic output using an encoding capable of
   representing every codepoint it reports.

### Requirement 9: Honest scope communication

**Objective:** As a reader of a passing report, I want to understand what was
not checked, so that I do not overstate the guarantee.

#### Acceptance Criteria

1. When the Detector reports a file as clean, the report shall make clear that
   the result covers deterministic carriers only.
2. The Detector shall state that statistical token-sampling watermarks are
   outside its detection scope.
3. The Detector shall not describe a file as free of AI provenance on the basis
   of a clean deterministic scan alone.
4. Where known detection limitations exist, the Detector shall make them
   discoverable from its own output or documentation.

### Requirement 10: Detection test coverage

**Objective:** As a maintainer, I want detection guarantees enforced by tests,
so that the gate cannot silently weaken.

#### Acceptance Criteria

1. The Detector's test suite shall assert that validation leaves every input
   file byte-identical, including on error paths.
2. The Detector's test suite shall assert agreement between detection and
   removal for every case in the removal preservation corpus.
3. The Detector's test suite shall include a carrier corpus covering each
   published technique the tool claims to detect, asserting a finding is
   reported.
4. The Detector's test suite shall assert the exit status for each documented
   outcome, including the skipped-file case.
5. The Detector's test suite shall assert that the validation hook and the
   autofix hook execute only in their declared stages.
