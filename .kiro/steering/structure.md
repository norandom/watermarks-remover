# Project Structure

## Organization Philosophy

**Vendor-isolated, single-entry-point.** The repository has exactly one
original source file and a quarantined copy of upstream logic. Every
structural decision follows from keeping that boundary legible.

```
src/wm_hook/
  __init__.py       docstring only — points at the vendoring boundary
  cli.py            THE original code: batch, exit codes, in-place writes
  _vendor/          quarantined upstream copies — never edited here
.pre-commit-hooks.yaml   adopter-facing hook contract
refresh.sh               the only way _vendor/ changes
.kiro/                   steering + specs
```

## Directory Patterns

### Original code
**Location**: `src/wm_hook/`
**Purpose**: Commit-time plumbing only — argument parsing, per-file iteration,
status reporting, exit codes, and the decision of *which* vendored cleaner to
call for a given extension.
**Rule**: If a change is about *how text is cleaned*, it does not belong here.
If it is about *which files get cleaned, when, and what the process reports*,
it does.

### Vendored code
**Location**: `src/wm_hook/_vendor/`
**Purpose**: Byte-exact copies of upstream `service/scripts/`. Contains
`text_unicode.py` (Layer A), `container_meta.py` (frontmatter + containers),
`common.py` (safe writes, binary sniffing), `image_meta.py` (unused by the
hook, imported by `container_meta`).
**Rule**: Read-only. Verified by SHA-256 in `VENDORED.json`. Any edit is a bug.

### Adopter contract
**Location**: `.pre-commit-hooks.yaml`, `README.md`
**Purpose**: Everything an external repository sees. Hook ids, the `files:`
regex, exit-code semantics, and the documented blast radius.
**Rule**: A behaviour change that an adopter would notice must land here in the
same change.

### Specs and steering
**Location**: `.kiro/`
**Purpose**: `steering/` is persistent project memory; `specs/` holds
requirements, design and tasks per feature.

## Naming Conventions

- **Modules**: lowercase, underscore-separated (`text_unicode`, `container_meta`).
- **Private helpers**: leading underscore (`_decide`, `_is_strip_cp`,
  `_valid_flag_tag_indices`). The vendored modules use this heavily; a
  non-underscore name signals a cross-module API.
- **Predicates**: `_is_*` returns bool (`_is_emoji_glue`, `_is_private_use`).
- **Constants**: SCREAMING_SNAKE, and `frozenset`/`dict` literals at module
  top with a per-codepoint inline comment naming the character.
- **Status strings**: `clean_one` returns one of the fixed set
  `clean | changed | skipped | error`. Extending this set is an
  adopter-visible change.

## Import Organization

```python
from __future__ import annotations   # always first

import argparse                      # stdlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "_vendor"))

from common import safe_write_text   # noqa: E402  — vendored, bare names
from text_unicode import clean_text  # noqa: E402
```

**Vendored modules are imported by bare name, after the `sys.path` insert, with
`# noqa: E402`.** This is not sloppiness — it is what allows the vendored files
to stay byte-exact with upstream, which imports them the same way. Do not
"fix" these into relative imports.

Inside `_vendor/`, cyclic pairs use function-local imports
(`from text_unicode import clean_text` inside a function body).

## Code Organization Principles

**One decision function.** `text_unicode._decide()` classifies a single
character for *both* inspection and cleaning, and returns
`(action, out_char, kind)`. `inspect_text()` and `clean_text()` are two loops
over the same classifier. This is why a `--check` run and a real run can never
disagree — preserve that property. A new rule goes in `_decide`, not in one
of the two callers.

**Preservation is contextual, not a list.** An invisible codepoint is kept only
when it sits directly after a base from its own script and is therefore doing
real work (emoji glue after an emoji base, Mongolian FVS after a Mongolian
letter, tag chars inside a complete flag sequence). The same codepoint floating
alone is contraband. New preservation rules follow this shape.

**Strip by category, allowlist by exception.** The catch-all is
`unicodedata.category(ch) == "Cf"`, so new Unicode format characters are
covered without a code change. Legitimate ones are named explicitly in
`_ORTHOGRAPHIC_CF`. Prefer extending the allowlist over extending the strip
list.

**Fail closed on ambiguity.** When input cannot be confidently handled — binary
bytes, oversized files, symlinked write targets — refuse and report rather
than transform. A skipped file is a better outcome than a corrupted one.

---
_Document patterns, not file trees. New files following patterns shouldn't require updates_
