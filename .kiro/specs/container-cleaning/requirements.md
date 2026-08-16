# Requirements Document

## Project Description (Input)

**Who has the problem.** Anyone shipping documents and images rather than
source text — a report exported to PDF, a diagram saved as SVG, a screenshot
pasted into a repository, a DOCX handed to a client. `wm-hook` refuses all of
them by design: it detects binary content and skips it untouched. Today there
is no supported way to clean them at all.

**Current situation.** The machinery already exists and already ships. The
vendored modules in `src/wm_hook/_vendor/` implement:

- `container_meta.py` — inspect and clean **SVG, PDF, DOCX, ODT, HTML**,
  including XMP packet removal, `docProps` scrubbing, `customXml` removal,
  dangling-relationship pruning, and a qpdf structural rewrite so that
  exiftool's incremental PDF edits do not leave the original metadata bytes
  recoverable in the file.
- `image_meta.py` — inspect and strip **PNG, JPEG, WebP, AVIF/HEIC**, covering
  C2PA and JUMBF markers, EXIF, XMP and text chunks, plus optional integrations
  for SynthID scoring and pixel-domain regeneration.

Both are vendored, hashed, and present in the built wheel. Neither is reachable:
`cli.py` wires only the plain-text and Markdown-frontmatter paths. The capability
is paid for and unused.

**What should change.** Expose a separate command-line tool that routes a file
by detected format to the appropriate container or image cleaner, with an
inspect-only mode matching the text tool's, and with honest reporting of the two
ways this differs from text cleaning: it is **best-effort** for some formats, and
it **degrades** when optional external tools are absent.

**Why this is not part of the hook.** Four reasons, each of which would break a
guarantee the hook currently makes:

1. **Losslessness.** The hook promises the rendered content is unchanged. PDF
   cleaning is best-effort; without `qpdf` the metadata bytes remain recoverable,
   and the stdlib fallback can leave byte offsets inconsistent.
2. **Execution context.** These paths spawn subprocesses (`exiftool`, `qpdf`,
   `c2patool`) with runtimes measured in seconds. That is wrong for a hook that
   runs on every commit.
3. **Dependency posture.** Steering mandates stdlib-only. The metadata paths hold
   to that; the pixel-domain path does not.
4. **Different stakes.** Removing a hidden zero-width character and removing a
   cryptographically signed C2PA provenance assertion are not the same act. The
   second deserves a deliberate, separately reasoned surface.

## Introduction

This specification defines **`wm-clean`**, a standalone command-line tool for
non-text formats. It is the sibling of the text tool, not an extension of it:
same inspect/clean duality, same refusal-over-corruption posture, different
guarantees.

The subject of all acceptance criteria is **the Container Cleaner**.

## Boundary Context

- **In scope**: format detection by content; routing to the correct container or
  image cleaner; metadata and provenance removal for SVG, PDF, DOCX, ODT, HTML,
  PNG, JPEG, WebP and AVIF; an inspect-only mode; honest reporting of degraded
  and best-effort outcomes; output-path handling that never destroys an original
  by surprise.

- **Out of scope**:
  - **Everything the text specs own.** Layer A Unicode cleaning of plain text
    files, and the pre-commit hook surface. Note that DOCX, ODT and HTML bodies
    *do* receive Layer A cleaning as part of container cleaning — that reuses the
    removal spec's classifier and does not redefine it.
  - **Becoming a pre-commit hook.** This tool is invoked deliberately.
  - **Layer B statistical text watermarks.**
  - **Pixel-domain watermark removal** — see the open decision below.

- **Adjacent expectations**:
  - The `watermark-removal` spec owns character classification. Where this tool
    cleans text inside a container body, it must use that classifier, so a
    paragraph in a DOCX is treated exactly as the same paragraph in a `.md`.
  - The `watermark-detection` spec owns finding shape and confidence levels.
    This tool's inspect mode should reuse them rather than invent a parallel
    vocabulary.
  - External binaries (`exiftool`, `qpdf`, `c2patool`) are optional. Their
    absence changes results and must be reported, never silently absorbed.

- **Pixel-domain removal — deferred to a future spec, not rejected.** The
  vendored code contains hooks for SynthID scoring and CtrlRegen-style
  regeneration. These are the image analogue of Layer B: they do not strip a
  field, they **re-generate the image**, and they require torch. This spec
  covers the lossless metadata path only, so `wm-clean` keeps one coherent
  promise — *it removes what was added; it does not regenerate your content* —
  and keeps the stdlib-only dependency posture from steering. A future
  `pixel-watermark-removal` spec may take it up; until then the tool must report
  it as out of scope rather than implying a clean image is unwatermarked.

- **Packaging decision.** `wm-clean` ships as a **second console script in the
  existing `watermarks-hook` package**, not as a separate distribution and not
  as subcommands of `wm-hook`. The vendored modules are already present in the
  built wheel, so this adds an entry point and no packaging machinery.
  Subcommands were rejected because pre-commit invokes `wm-hook` with bare
  filenames, so any subcommand grammar would have to stay backward-compatible
  with that forever.

## Requirements

### Requirement 1: Format routing by content

**Objective:** As a user with a mixed directory, I want the right cleaner chosen
automatically, so that I do not have to know a file's internal format.

#### Acceptance Criteria

1. The Container Cleaner shall determine a file's format from its content rather
   than its extension.
2. When a file's extension contradicts its content, the Container Cleaner shall
   route by content and report the discrepancy.
3. Where a caller pins the format explicitly, the Container Cleaner shall use the
   pinned format and skip detection.
4. If a file's format is unsupported, then the Container Cleaner shall leave it
   unmodified and report it as unsupported rather than attempting a generic
   strip.

### Requirement 2: Document metadata removal

**Objective:** As someone publishing a document, I want authoring and generator
metadata removed, so that the file does not disclose how it was produced.

#### Acceptance Criteria

1. When cleaning a document container, the Container Cleaner shall remove
   embedded provenance metadata while leaving the visible content intact.
2. The Container Cleaner shall remove metadata parts that carry arbitrary
   user-defined properties, since they are an open provenance channel.
3. When removing a part from a packaged container, the Container Cleaner shall
   also remove references to that part, so the result opens without repair
   prompts.
4. When cleaning a container that holds body text, the Container Cleaner shall
   apply the same character-level cleaning the text tool applies, using the same
   classifier.
5. The Container Cleaner shall preserve a document's own title and visible
   headings, which are content rather than provenance.
6. When a cleaned container is written, the Container Cleaner shall produce a
   file that opens in its native application without warnings.

### Requirement 3: Image metadata removal

**Objective:** As someone sharing an image, I want provenance metadata removed
without altering a single pixel.

#### Acceptance Criteria

1. When cleaning an image, the Container Cleaner shall leave the decoded pixel
   data bit-for-bit identical.
2. The Container Cleaner shall remove content-credential and provenance
   manifests, embedded profiles carrying provenance, and free-form text records.
3. Where an embedded record is required for correct rendering, the Container
   Cleaner shall preserve it and report that it was preserved.
4. When an image contains no removable metadata, the Container Cleaner shall
   leave the file byte-identical.

### Requirement 4: Honest reporting of degraded results

**Objective:** As a user relying on this before publishing, I want to know when
the clean was incomplete, so that I do not over-trust it.

#### Acceptance Criteria

1. If an optional external tool required for a complete clean is unavailable,
   then the Container Cleaner shall complete what it can and report the result as
   degraded.
2. When a clean is degraded, the Container Cleaner shall name the missing tool
   and what remains uncleaned.
3. When a format's cleaning is inherently best-effort, the Container Cleaner
   shall say so rather than reporting unqualified success.
4. When a clean completes, the Container Cleaner shall re-inspect the output and
   report any provenance that survived.
5. The Container Cleaner shall exit with a distinct status when a clean completed
   but was degraded.
6. The Container Cleaner shall state that pixel-domain and statistical
   watermarks are outside its scope, so a clean result is not read as proof of
   absence.

### Requirement 5: Inspect-only mode

**Objective:** As a reviewer, I want to see what a file discloses before deciding
to alter it.

#### Acceptance Criteria

1. While operating in inspect mode, the Container Cleaner shall not create,
   modify or delete any file.
2. When inspecting, the Container Cleaner shall report each finding with its
   location within the container and a confidence level.
3. The Container Cleaner shall use the same finding vocabulary as the text
   detection tool.
4. Where machine-readable output is requested, the Container Cleaner shall emit
   findings in a structured format.

### Requirement 6: Safe output handling

**Objective:** As a user, I want control over whether my original survives.

#### Acceptance Criteria

1. The Container Cleaner shall write to a separate output path by default rather
   than modifying the input.
2. Where in-place modification is requested, the Container Cleaner shall write
   atomically and preserve the file's permissions.
3. If an output path already exists, then the Container Cleaner shall refuse to
   overwrite it unless overwriting is explicitly requested.
4. If cleaning fails partway, then the Container Cleaner shall leave the input
   unmodified and remove any partial output.
5. The Container Cleaner shall refuse to write through a symbolic link.
6. If an archive-based container declares a decompressed size beyond the
   configured limit, then the Container Cleaner shall refuse it rather than
   expanding it.

### Requirement 7: Test coverage

**Objective:** As a maintainer, I want format handling proven against real files.

#### Acceptance Criteria

1. The Container Cleaner's test suite shall include a fixture per supported
   format, each carrying known provenance metadata, asserting its removal.
2. The Container Cleaner's test suite shall assert that cleaned packaged
   containers remain structurally valid and reopenable.
3. The Container Cleaner's test suite shall assert pixel-identity for cleaned
   images.
4. The Container Cleaner's test suite shall assert that inspect mode leaves every
   input byte-identical.
5. The Container Cleaner's test suite shall assert degraded-mode reporting by
   running with the optional external tools made unavailable.
