# Requirements Document

## Project Description (Input)

**Who has the problem.** Developers and technical writers who paste
model-generated text into a git repository, and the maintainers who review
their commits. Neither can see invisible Unicode carriers in a diff.

**Current situation.** `wm-hook` already removes Layer A invisible/format
Unicode and AI generator keys from Markdown/Quarto YAML frontmatter, and
rewrites files in place at commit time. An adversarial review of the shipped
implementation confirmed by execution that the removal path is unsafe: it
destroys legitimate content that merely resembles a marker (frontmatter values
naming a vendor, private-use glyphs, Thai/Lao word separators, Persian ZWNJ),
it rewrites files that carry no marks at all (CRLF frontmatter, leading `---`
thematic breaks), it can convert a valid YAML file into an unparseable one, it
does not converge in a single pass, and it drops file metadata that git tracks.
There is no test suite.

**What should change.** The removal path must become predictable enough to run
unattended on every commit: converge in one pass, never change bytes it was not
asked to change, never destroy legitimate content, and preserve file metadata.
Risky transformations must be scopeable rather than unconditional. All of it
must be covered by tests, including a preservation corpus.

## Introduction

This specification defines the **rewrite path** of `wm-hook`: the behavior of
the tool when it is permitted to modify files. Its governing promise is that
cleaning is **lossless** — the rendered appearance and the semantic content of
the text are unchanged, and only invisible or provenance-bearing material is
removed.

Every requirement below is traceable to a defect reproduced against the shipped
implementation, or to an existing behavior that must be preserved as a
regression guard.

The subject of all acceptance criteria is **the Cleaner**.

## Boundary Context

- **In scope**: what the Cleaner deletes, replaces and preserves in a text
  file; byte-level fidelity of everything it does not target; convergence;
  write safety and file-metadata preservation; the scoping controls that let an
  adopter disable a risky transformation; the test corpus that proves all of
  the above.

- **Out of scope**:
  - **Layer B statistical watermarks** (token-sampling schemes such as
    SynthID-Text or green-list biasing). Permanently excluded: removing them
    requires paraphrasing, which would break the lossless promise.
  - **Stylistic tells** (em dashes, curly quotes, word choice). Not watermarks;
    the Cleaner does not alter punctuation or wording.
  - **Read-only validation, reporting format, hook ids, CI gating and exit
    codes** — owned by the `watermark-detection` spec.
  - **Binary and container formats** (images, PDF, DOCX, ODT). The Cleaner
    refuses them; cleaning them is upstream tooling's job.

- **Adjacent expectations**:
  - The `watermark-detection` spec expects the Cleaner's classification of a
    given character to be identical to detection's. A change to what the
    Cleaner removes is a change to what detection reports.
  - The vendored upstream modules own the character-classification logic and
    are byte-exact copies. Where a defect originates upstream, this spec
    requires the observable behavior to be correct; it does not mandate where
    the correction lives.
  - The set of file extensions the Cleaner is invoked on is owned by the hook
    manifest, not by this spec.

## Requirements

### Requirement 1: Lossless transformation guarantee

**Objective:** As a developer committing prose, I want cleaning to never change
what my text says or how it renders, so that I can enable an automatic rewrite
without reviewing every diff.

#### Acceptance Criteria

1. The Cleaner shall preserve the rendered appearance of the text for every
   transformation it performs, such that a removed character contributed no
   visible glyph and a replaced character is visually equivalent.
2. The Cleaner shall not alter the wording, punctuation, capitalization or
   ordering of any visible text.
3. If a transformation would change the meaning or parse of the surrounding
   content, then the Cleaner shall not perform it.
4. When a file contains no invisible carriers and no provenance metadata, the
   Cleaner shall leave the file byte-for-byte identical.

### Requirement 2: Removal of invisible and format carriers

**Objective:** As a maintainer, I want invisible codepoints that can carry a
payload removed, so that no undetectable data enters repository history.

#### Acceptance Criteria

1. When a file contains a zero-width character (`U+200B`, `U+200C`, `U+200D`,
   `U+2060`, `U+FEFF`) that is not serving a documented linguistic function,
   the Cleaner shall remove it.
2. When a file contains a Unicode Tag-block character (`U+E0000`–`U+E007F`)
   outside a complete subdivision-flag sequence, the Cleaner shall remove it.
3. When a file contains a variation selector (`U+FE00`–`U+FE0F`,
   `U+E0100`–`U+E01EF`) that does not follow a base character it can legally
   modify, the Cleaner shall remove it.
4. When a file contains a bidirectional override (`U+202D`, `U+202E`), the
   Cleaner shall remove it unconditionally.
5. The Cleaner shall remove any character in Unicode general category `Cf` that
   is not on the documented preservation allowlist, so that newly assigned
   format characters are covered without a change to the tool.
6. When multiple carriers of the same class appear consecutively, the Cleaner
   shall remove every character in the run in a single pass.

### Requirement 3: Preservation of load-bearing invisible characters

**Objective:** As an author writing in a non-Latin script or using emoji, I
want invisible characters that are part of my language or my glyphs left
intact, so that cleaning does not corrupt my content.

#### Acceptance Criteria

1. When a zero-width joiner sits between two emoji bases, the Cleaner shall
   preserve it, so that multi-person and combined emoji sequences render
   unchanged.
2. When a text or emoji variation selector follows any character that Unicode
   defines as emoji-presentable, the Cleaner shall preserve it, including
   bases outside the Miscellaneous Symbols blocks.
3. When a zero-width joiner or non-joiner sits between characters of a script
   in which it is orthographic, the Cleaner shall preserve it, including at
   the end of a text value and adjacent to punctuation, digits, or a line
   break.
4. While processing text in a script that uses `U+200B` as its word or line
   break separator, the Cleaner shall preserve `U+200B`.
5. The Cleaner shall preserve private-use-area codepoints by default, so that
   icon-font glyphs in tracked text files survive cleaning.
6. Where a preservation rule depends on an adjacent base character, the Cleaner
   shall evaluate that rule against the neighbouring *base*, not against
   another carrier, so that a run of carriers cannot mask itself.
7. The Cleaner shall preserve directional marks and correctly paired
   directional embeddings by default.

### Requirement 4: Structural safety of space normalization

**Objective:** As an operator, I want space normalization to never change how a
file parses, so that cleaning cannot break a build.

#### Acceptance Criteria

1. When a space homoglyph occupies a position where an ASCII space would be
   structurally significant, the Cleaner shall not replace it with an ASCII
   space.
2. If replacing a space homoglyph would make a previously parseable file
   unparseable, then the Cleaner shall leave the character unchanged and report
   it instead.
3. If a space homoglyph would, after replacement, hide provenance metadata from
   the Cleaner's own subsequent processing, then the Cleaner shall remove the
   homoglyph rather than replace it.
4. Where space normalization is disabled by configuration, the Cleaner shall
   leave all space homoglyphs unchanged.
5. The Cleaner shall preserve space homoglyphs that carry documented
   typographic meaning in the surrounding language when normalization is
   disabled for that path.

### Requirement 5: Provenance metadata removal without collateral loss

**Objective:** As a technical writer, I want AI generator keys removed from my
frontmatter without losing my own fields, so that cleaning does not silently
delete my content.

#### Acceptance Criteria

1. When a frontmatter key names an AI generator or provenance concept, the
   Cleaner shall remove that key together with its nested block or list items.
2. If a frontmatter key's **value** merely mentions an AI vendor while the key
   itself is not a provenance field, then the Cleaner shall preserve the key
   and its value.
3. The Cleaner shall not remove a frontmatter key whose name is a common
   domain term unless its value also indicates AI provenance.
4. If the leading `---` in a document is a thematic break rather than a
   frontmatter delimiter, then the Cleaner shall leave the document body
   unmodified.
5. When every key in a frontmatter block is removed, the Cleaner shall remove
   the now-empty delimiter block.
6. When provenance metadata is hidden behind a byte-order mark or an invisible
   character, the Cleaner shall still detect and remove it in the same pass.

### Requirement 6: Byte-level fidelity outside the targeted change

**Objective:** As a reviewer, I want a cleaning diff to contain only the
removal, so that I can see what actually changed.

#### Acceptance Criteria

1. The Cleaner shall preserve the file's existing line-ending convention,
   including in a frontmatter block.
2. If a file's line endings are uniform before cleaning, then they shall remain
   uniform after cleaning.
3. The Cleaner shall preserve the presence or absence of a trailing newline.
4. The Cleaner shall preserve blank lines and indentation that it was not
   required to remove.
5. When a byte-order mark is a required encoding signal for the file's format,
   the Cleaner shall preserve it.
6. When a file cannot be decoded as UTF-8, the Cleaner shall round-trip the
   undecodable bytes unchanged.

### Requirement 7: Single-pass convergence

**Objective:** As a developer, I want one cleaning run to finish the job, so
that a commit does not fail repeatedly.

#### Acceptance Criteria

1. When the Cleaner modifies a file, a second run on the result shall report
   the file as clean and leave it byte-identical.
2. The Cleaner shall remove all detectable marks in a single invocation,
   regardless of the order in which different mark classes appear.
3. If one class of mark conceals another, then the Cleaner shall remove both in
   the same invocation.
4. The Cleaner shall not reach a stable state in which a detectable mark
   remains present.

### Requirement 8: File metadata and write safety

**Objective:** As a repository owner, I want cleaning to change only file
contents, so that no unrelated change enters the commit.

#### Acceptance Criteria

1. When the Cleaner rewrites a file, it shall preserve the file's executable
   permission bit.
2. The Cleaner shall write modified content atomically, so that an interrupted
   run never leaves a partially written file.
3. If the write target is a symbolic link, then the Cleaner shall not write
   through it.
4. If a file's contents indicate a binary format, then the Cleaner shall leave
   the file unmodified.
5. If a file exceeds the configured maximum input size, then the Cleaner shall
   leave it unmodified and report it as skipped rather than as a failure.
6. When a path is supplied that cannot be read, the Cleaner shall report the
   failure and continue processing the remaining paths.

### Requirement 9: Scoping and opt-out controls

**Objective:** As an adopter with unusual content, I want to disable a specific
transformation, so that I can adopt the tool without excluding whole
directories.

#### Acceptance Criteria

1. Where a transformation carries a documented false-positive risk, the Cleaner
   shall provide a way to disable that transformation independently of the
   others.
2. When a transformation is disabled, the Cleaner shall leave the corresponding
   characters unchanged and shall not report the file as modified on their
   account.
3. The Cleaner shall apply a safe default configuration when no configuration
   is supplied.
4. The Cleaner shall document which transformations are enabled by default.

### Requirement 10: Actionable reporting of what was removed

**Objective:** As a developer whose commit just failed, I want to know exactly
what was taken out, so that I can decide whether the change was correct.

#### Acceptance Criteria

1. When the Cleaner modifies a file, it shall report each distinct codepoint it
   removed or replaced, identified by codepoint and Unicode name.
2. When the Cleaner removes provenance metadata, it shall report each field it
   removed by name.
3. When the Cleaner declines a transformation because a preservation or safety
   rule applied, it shall be possible to learn that this happened.
4. The Cleaner shall not report a file as modified when it made no change.

### Requirement 11: Regression and preservation test coverage

**Objective:** As a maintainer, I want the guarantees above enforced by tests,
so that a future change cannot silently reintroduce a data-loss defect.

#### Acceptance Criteria

1. The Cleaner's test suite shall include a preservation corpus covering emoji
   sequences, right-to-left scripts, Indic and Arabic joiners, CJK variation
   selectors, Thai and Lao word separators, and icon-font glyphs, asserting
   byte-identical output.
2. The Cleaner's test suite shall assert single-pass convergence for every case
   in which one mark class can conceal another.
3. The Cleaner's test suite shall assert byte-identical output for
   watermark-free inputs across each supported line-ending convention, with and
   without frontmatter.
4. The Cleaner's test suite shall assert that each documented carrier class is
   actually removed.
5. When a defect is fixed, the test suite shall gain a case that reproduces the
   original defect.
