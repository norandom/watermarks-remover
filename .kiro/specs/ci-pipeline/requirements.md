# Requirements Document

## Project Description (Input)

**Who has the problem.** Maintainers of this repository, and adopters who pin a
`rev:` in their `.pre-commit-config.yaml` and need that tag to mean something.

**Current situation.** There is no CI and no release process at all. No
`.github/`, no `dagger.json`, no tags, version `0.1.0` hand-written in
`pyproject.toml`. Three consequences, each already biting:

1. **Assertions that execute nowhere.** The development host is Windows, which
   has no `os.fchmod` and reports every writable file as `0o666`. Eight
   write-path assertions — including the executable bit that Requirement 8.1 of
   `watermark-removal` rests on — skip locally. `scripts/test-linux.sh` now runs
   the suite through Dagger on Linux (783 passed, zero skips), but nothing
   *enforces* that anyone runs it.
2. **Integrity checks with no home.** `refresh.sh --check` verifies the vendored
   files against their recorded hashes and is the only control enforcing the
   byte-exact vendoring rule. It cannot even run on the development host (it
   shells out to `python3`). Hook-manifest validation is likewise manual.
3. **No releasable artifact.** Adopters are told to pin `rev: <tag>`, and no tag
   exists. There is no changelog, no build provenance, and nothing stops a
   release being cut from a tree whose vendored files have drifted.

**What should change.** A single pipeline, defined once and executed
identically on a workstation and on CI, that verifies the repository and can
cut a GitHub release from a verified commit. Dagger is the chosen mechanism
precisely so the local and CI paths cannot diverge: a maintainer runs the same
functions the runner does, against the same container images.

## Introduction

This specification defines the **build, verification and release pipeline**. It
is deliberately separate from the two cleaning specs: it is about the
repository as a product — how it is proven correct and how it reaches adopters
— not about what the cleaner does to text.

The subject of all acceptance criteria is **the Pipeline**.

## Boundary Context

- **In scope**: the Dagger module and its functions; running the test suite on
  Linux; the repository-integrity checks (vendored hashes, hook-manifest
  validation, corpus protection); building the distribution; the GitHub
  Actions workflow that invokes the pipeline; tag-driven release publication;
  changelog and version handling.

- **Out of scope**:
  - **What the tests assert.** Test content belongs to `watermark-removal` and
    `watermark-detection`. The Pipeline runs them; it does not author them.
  - **Publishing to a package index.** Adopters install from a git ref via
    pre-commit, `uvx` or `pipx`. A PyPI release is a separate decision with its
    own naming and ownership questions.
  - **Signing and attestation.** Desirable, but a distinct concern; noted as a
    likely follow-on rather than smuggled in here.
  - **Cleaning behaviour of any kind.**

- **Adjacent expectations**:
  - `watermark-removal` task 4.5 owns making the POSIX gates self-policing; the
    Pipeline owns *where* they run.
  - `refresh.sh` owns re-vendoring; the Pipeline only verifies the result.
  - The `Debian` WSL distro is the local Linux host on the development machine.
    **`Debian-MW` is reserved and must never be used.**

## Requirements

### Requirement 1: One pipeline definition, two execution contexts

**Objective:** As a maintainer, I want the checks CI runs to be the checks I can
run locally, so that a CI failure is reproducible without pushing commits.

#### Acceptance Criteria

1. The Pipeline shall define each verification step once and expose it as a
   named function invocable from a developer workstation and from CI.
2. When a step runs locally and in CI against the same commit, the Pipeline
   shall execute the same container image and the same command for both.
3. The Pipeline shall run without any project-specific tooling preinstalled on
   the host beyond a container runtime.
4. Where the host is Windows, the Pipeline shall be invocable through a Linux
   environment without the developer reconstructing the command by hand.

### Requirement 2: Verification on a POSIX host

**Objective:** As a maintainer, I want the platform-gated assertions to actually
execute, so that a green run means what it appears to mean.

#### Acceptance Criteria

1. The Pipeline shall run the full test suite on a Linux container.
2. If any platform-gated test is skipped during a Linux run, then the Pipeline
   shall fail the run rather than report success.
3. The Pipeline shall report the count of passed, failed and skipped tests.
4. Where a test suite run fails, the Pipeline shall surface the failing test
   names in its output.

### Requirement 3: Repository-integrity gates

**Objective:** As a maintainer, I want the rules the project depends on enforced
mechanically, so that they cannot decay silently.

#### Acceptance Criteria

1. The Pipeline shall verify that every vendored file matches its recorded hash
   and fail the run on any mismatch.
2. The Pipeline shall validate the pre-commit hook manifest.
3. The Pipeline shall verify that the byte-exact test fixtures remain excluded
   from this repository's own hook.
4. If a verification gate fails, then the Pipeline shall not proceed to build or
   release steps.
5. The Pipeline shall verify that the built distribution declares no runtime
   dependencies, since the stdlib-only guarantee is an adopter-visible promise.
6. The Pipeline shall verify that the built distribution contains the vendored
   modules, without which the tool cannot run.

### Requirement 4: Automated verification on change

**Objective:** As a maintainer, I want every push and pull request checked, so
that a regression is caught before it is merged.

#### Acceptance Criteria

1. When a commit is pushed to any branch, the Pipeline shall run verification.
2. When a pull request is opened or updated, the Pipeline shall run
   verification and report the result against that pull request.
3. The Pipeline shall complete a verification run within a duration that does
   not discourage frequent pushes.
4. Where a run repeats work whose inputs have not changed, the Pipeline should
   reuse the earlier result.

### Requirement 5: Release publication

**Objective:** As an adopter, I want to pin a real tag, so that my hook
configuration is reproducible.

#### Acceptance Criteria

1. When a release is requested for a version, the Pipeline shall refuse to
   publish unless every verification gate has passed for that commit.
2. The Pipeline shall build the distribution artifacts and attach them to the
   published release.
3. The Pipeline shall refuse to publish a version that is already published.
4. The Pipeline shall require the declared project version and the release tag
   to agree.
5. When a release is published, the Pipeline shall record what changed since
   the previous release.
6. The Pipeline shall make the released tag usable directly as a pre-commit
   `rev:` without further steps by the adopter.

### Requirement 6: Operability and failure diagnosis

**Objective:** As a maintainer debugging a red run, I want to know what broke
without reading the whole log.

#### Acceptance Criteria

1. When a step fails, the Pipeline shall identify which named step failed.
2. The Pipeline shall keep credentials out of its output.
3. The Pipeline shall accept the credentials it needs from the environment
   rather than from files in the repository.
4. Where a run is triggered without the credentials a release needs, the
   Pipeline shall fail before doing any work rather than partway through.
