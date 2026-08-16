# Requirements Document

## Project Description (Input)

**Who has the problem.** Anyone trying to answer "how much AI provenance signal
is actually in this codebase, and who put it there" — a maintainer auditing a
tree, a researcher tracking whether agents begin marking their output, a
reviewer deciding whether a contribution was machine-written.

**Current situation.** The hook answers a narrower question: *does this file
contain a carrier I should remove?* That is the wrong instrument for a survey.
It reports per-file counts with no notion of legitimacy, no aggregate rate, and
no attribution. Running it across a tree tells you how many files it would
rewrite, not how much watermarking is present.

A prototype at `scripts/wm-survey.py` established the shape and, more usefully,
established what makes it hard. Measured on 2026-08-16 across 11 sibling
repositories:

- **Zero private-use codepoints anywhere.** The "agents hide payloads in free
  Unicode space" hypothesis found no support in this corpus.
- A Codex-authored repository: 703 files, 3 with carriers (0.43%), **0
  unexplained** — all six hits were emoji presentation selectors.
- Reporting "carriers found" as a detection rate would have claimed 0.43%
  where the honest answer is 0%.
- The prototype's own explanation layer produced **15 false positives across 4
  files**, every one caused by inheriting the cleaner's blind spots: it did not
  recognise five emoji bases, and it did not skip backward over a variation
  selector to find the real base.

That last finding is the whole difficulty. A survey is only as good as its
ability to say *this carrier is legitimate*. Over-explain and real watermarks
vanish; under-explain and every emoji becomes a false alarm.

**What should change.** Promote the survey to a supported command with three
capabilities the prototype proved necessary: rates that separate carriers found
from carriers explained from the unexplained residual; classification by
carrier style; and attribution to a vendor where evidence supports it. The
explanation layer's error rates must themselves be measured, because they are
the number that determines whether any other number can be trusted.

## Introduction

This specification defines **`wm-survey`**, a reporting command that measures
AI provenance signal across a tree and attributes it where it can.

It is a research instrument. Its output is evidence for a human judgement, not
a verdict. The single most important design constraint follows from that: it
must never present a number that overstates what it knows.

The subject of all acceptance criteria is **the Survey**.

## Boundary Context

- **In scope**: walking a tree; classifying carriers by style; deciding whether
  a carrier is explained by a legitimate cause; computing and reporting rates;
  attributing authorship from available evidence; machine-readable output;
  measuring the survey's own false-positive and false-negative rates.

- **Out of scope**:
  - **Modifying anything.** The Survey is read-only under every code path.
  - **Removal**, and the pre-commit hook surface entirely.
  - **Statistical text watermarks.** Out of reach, and the Survey must say so
    rather than let a clean result imply their absence.
  - **Claiming a file was AI-generated.** The Survey reports evidence and its
    strength. The inference is the reader's.

- **Adjacent expectations**:
  - `watermark-removal` owns the classifier. Where the Survey and the cleaner
    disagree about whether a codepoint is a carrier, that is a defect in one of
    them, and the conformance test that catches it belongs here.
  - `watermark-detection` owns per-file findings for gating. The Survey
    aggregates; it should reuse that vocabulary rather than invent a parallel
    one.

## Requirements

### Requirement 1: Honest rate reporting

**Objective:** As a researcher tracking this over time, I want rates that cannot
flatter themselves, so that a trend line means something.

#### Acceptance Criteria

1. The Survey shall report carriers found, carriers explained, and the
   unexplained residual as three separate quantities.
2. The Survey shall not present carriers found as a detection rate.
3. When every carrier in a tree is explained, the Survey shall report a
   watermark-candidate rate of zero.
4. The Survey shall report the proportion of files scanned that contain an
   unexplained carrier.
5. The Survey shall state the size of the corpus each rate is computed over.
6. Where a rate is computed from a sample too small to support it, the Survey
   shall report the count rather than the percentage.

### Requirement 2: Classification by carrier style

**Objective:** As a reader, I want to know which technique was used, because a
zero-width run and an emoji selector mean entirely different things.

#### Acceptance Criteria

1. The Survey shall classify each carrier into a named style.
2. The Survey shall report counts per style.
3. The Survey shall distinguish styles that indicate deliberate encoding from
   styles that commonly occur by accident.
4. Where a style has a documented published technique, the Survey shall name it.
5. The Survey shall report the position of each unexplained carrier.

### Requirement 3: Explanation of legitimate carriers

**Objective:** As a reader, I want carriers that are doing real work excluded
from the candidate count, so that the residual is worth investigating.

#### Acceptance Criteria

1. When a carrier serves a documented linguistic, typographic or presentational
   function in its context, the Survey shall classify it as explained and
   record which function.
2. The Survey shall resolve a carrier's context against the nearest preceding
   base character, disregarding intervening carriers.
3. The Survey shall recognise the same set of emoji and script bases the
   cleaner recognises.
4. If the Survey cannot determine whether a carrier is legitimate, then it shall
   classify it as unexplained rather than guess.
5. The Survey shall make each explanation visible, so a reader can disagree
   with it.

### Requirement 4: Measured accuracy of the explanation layer

**Objective:** As a user of these numbers, I want to know how wrong they are,
because an unmeasured explanation layer makes every other figure unfalsifiable.

#### Acceptance Criteria

1. The Survey shall be evaluated against a corpus of known-legitimate content
   and a corpus of known-carrier content.
2. The Survey shall report its false-positive rate against the known-legitimate
   corpus.
3. The Survey shall report its false-negative rate against the known-carrier
   corpus.
4. When the Survey and the cleaner disagree about whether a codepoint is a
   carrier, the evaluation shall fail.
5. The Survey shall publish these rates alongside its findings, so a reader can
   weigh the residual against the known error.

### Requirement 5: Authorship attribution

**Objective:** As a maintainer, I want to know which agent produced a tree, and
on what basis, so that I can judge how much the claim is worth.

#### Acceptance Criteria

1. The Survey shall attribute authorship from declared configuration artifacts
   present in the tree.
2. The Survey shall attribute authorship from version-control authorship
   metadata where a repository is present.
3. The Survey shall report the evidence each attribution rests on, not only the
   conclusion.
4. The Survey shall state that its attribution evidence is overt and removable.
5. Where evidence supports more than one agent, the Survey shall report all of
   them rather than choosing.
6. The Survey shall not infer an agent from writing style or formatting habits.
7. Where a carrier can be associated with a specific vendor's documented
   scheme, the Survey shall report that association and the evidence for it.

### Requirement 6: Output and invocation

**Objective:** As someone scripting this, I want output I can parse and diff.

#### Acceptance Criteria

1. The Survey shall accept one or more directories.
2. The Survey shall emit a human-readable report by default.
3. Where machine-readable output is requested, the Survey shall emit structured
   data containing every field of the human report.
4. The Survey shall allow paths to be excluded from the scan, so that a
   project's own test fixtures do not dominate its findings.
5. The Survey shall produce deterministic output for unchanged input, so that
   two runs can be diffed.
6. The Survey shall record the date of the run.

### Requirement 7: Scope honesty

**Objective:** As a reader of a zero result, I want to know exactly what was
ruled out.

#### Acceptance Criteria

1. The Survey shall state that it measures deterministic carriers only.
2. The Survey shall state that statistical token-sampling watermarks are
   outside its reach.
3. The Survey shall not describe a tree as free of AI authorship on the basis of
   a zero residual.
4. The Survey shall record the known techniques it does not detect.
