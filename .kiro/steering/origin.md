# Origin of the code, and what that does not imply

This project began from
[`guillaumemeyer/watermarks-remover`](https://github.com/guillaumemeyer/watermarks-remover).
The cleaning modules under `src/wm_hook/core/` were copied from its
`service/scripts/` directory.

**This is a fork, not a vendored dependency.** The distinction matters because
an earlier version of this repository got it wrong, and the mistake was
expensive.

## What is true

- The code came from upstream and upstream deserves credit. Both projects are
  MIT licensed, recorded in `NOTICE`.
- The files were byte-identical to upstream commit `fcebf53` at the point of
  copying, verified by hash.
- We change them freely, wherever the measurements say they are wrong.

## What is not true

There is **no synchronisation contract**. We do not track upstream, do not
re-pull, and do not preserve byte-exactness. Upstream may fix something we
have already fixed differently, or change something we depend on. Neither is
our problem.

## The mistake this replaces, and what it cost

The repository was originally structured as if the copied files were vendored:
a `_vendor/` directory, a `VENDORED.json` hash manifest, a `refresh.sh` that
re-pulled from upstream, and a rule that the files must never be edited.

That rule was load-bearing in the wrong direction. Nearly every confirmed
defect lives inside those files, so an entire architecture was designed to
route around a constraint that did not exist:

- a `_tables.py` gateway, so owned code could reach the codepoint tables
  without importing the decision functions;
- a plan to **reimplement the classifier from scratch** in an owned module,
  consuming upstream only as data;
- a divergence conformance test to record every intentional disagreement with
  an upstream we were never going to re-pull from.

Roughly 350 lines of machinery, plus the largest task in the specification,
existed to avoid editing four files we are allowed to edit.

## What follows from getting it right

- **Fix defects where they are.** A bug in the classifier is fixed in the
  classifier.
- **No gateway indirection.** Import what you need.
- **No divergence test.** There is nothing to diverge from.
- **Attribution stays.** `NOTICE` credits upstream; the licence requires it and
  it is right regardless.

## The one thing worth keeping from the old approach

Recording the **provenance hash** of the original copy. Not as a sync contract,
but so anyone can reconstruct which upstream state this started from and diff
against it if they want to see what changed. That lives in `NOTICE`, as a fact
about history rather than a constraint on the future.

---
_A constraint you invented is still a constraint. Check that it is real before
building around it._
