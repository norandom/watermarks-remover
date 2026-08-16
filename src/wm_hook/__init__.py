"""Pre-commit hook that strips AI provenance marks from text.

Scope is text and Unicode carriers. Image, C2PA and pixel-domain work is out
of scope and was removed; upstream remains the better choice for that.

Layout:

    core/       the cleaning modules, forked from
                guillaumemeyer/watermarks-remover (see NOTICE)
    cli.py      batch iteration, exit codes, in-place writes
    policy.py   which transformations are enabled
    regions.py  document segmentation
    flags.py    bounded emoji tag sequence validation
    atomic.py   mode-preserving atomic write

`core/` is a fork, not a vendored dependency. It is edited wherever the
measurements say it is wrong.
"""
