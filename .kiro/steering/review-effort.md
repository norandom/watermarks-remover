# Review Effort Calibration

How much adversarial review a task earns. Written after the foundation phase of
`watermark-removal`, where uniform maximum review cost ~81 minutes of agent time
for four tasks and found three real defects — all three in the tasks that
touched behaviour or repository-wide configuration, none in the two that were
pure scaffolding.

## Principle

**Spend review where a mistake is expensive and hard to detect later.** Uniform
maximum effort is not rigour; it is unpriced risk aversion that slows the loop
and buys nothing on a frozen dataclass.

## Tiers

### Tier 1 — full independent adversarial review (fresh subagent)

Any task that:
- changes what the cleaner **does to a user's bytes** (classification,
  segmentation, key policy, the pipeline);
- changes **repository-wide configuration** an adopter inherits
  (`.pre-commit-hooks.yaml`, `.gitattributes`, packaging metadata);
- creates or alters **byte-exact fixtures** that later tests trust;
- touches the **vendoring boundary**.

In this spec: 2.2, 2.4, 2.5, 3.1, 3.2, 3.3, and every group-4 task.

### Tier 2 — inline review by the controller

Small, self-contained, mechanically verifiable tasks with no behavioural reach:
a frozen value object, a single-purpose I/O helper, a documentation re-sync.
The controller reads the diff, runs the suite, runs the boundary and integrity
checks, and records the result. No second subagent.

In this spec: 2.1, 2.3, 4.5.

Escalate to Tier 1 the moment a Tier 2 task turns out to touch behaviour.

## Non-negotiable in both tiers

These are cheap and catch the failures that actually happened here. Never skip:

1. Full suite passes; the prior baseline count is intact.
2. `_vendor/*.py` SHA-256 still match `VENDORED.json`.
3. Changed files stay inside the task's `_Boundary:_`.
4. RED evidence exists — tests failed before the implementation.
5. No literal invisible carrier in any **test module** (corpus data files
   excepted); the repo's own hook would rewrite it and corrupt the fixture.
6. No TBD/TODO/FIXME left in changed files.

## Mutation probes: cap at three

Probes prove an assertion is load-bearing. Three well-chosen ones prove it;
fifteen prove it fifteen times. The reviewer of task 1.4 ran fifteen — each is
mutate → run suite → restore → verify byte-identical — for the same conclusion
three would have reached.

Choose probes that target **different failure modes**, not three variants of
one:
- one that breaks the *data* (corrupt a fixture byte),
- one that breaks the *claim* (falsify an annotation or expectation),
- one that removes the *guard* (delete the check under test).

Known trap: `frozenset(x)` returns the same object when `x` is already a
frozenset, so it is useless as a "copy instead of alias" probe. Use `dict(...)`
or `frozenset(set(...))`.

## Dispatch efficiency

- **Point subagents at the prompt templates on disk**
  (`.claude/skills/kiro-impl/templates/`) rather than inlining them. The
  template is the stable half; only task-specific context needs restating.
- **Do not split a cohesive artifact across tasks** merely to hit a size
  guideline. Four tasks sharing one file and one boundary re-read the same
  specs, re-run the same suite, and produce observables that reference work
  their own task has not done yet. Merge them and let the groups be bullets.
- **Genuinely disjoint tasks may run concurrently.** The default is sequential
  to avoid git conflicts; that reasoning does not apply when boundaries touch
  different files and neither writes shared state.

---
_Calibrate effort to consequence. The checks in "Non-negotiable" are the floor,
not the target._
