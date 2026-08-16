# Technology Stack

## Architecture

A thin CLI wrapper around **vendored, byte-exact upstream cleaning modules**.

```
pre-commit  ──▶  wm-hook (cli.py)  ──▶  _vendor/text_unicode.clean_text
                  │                 └─▶  _vendor/container_meta.clean_markdown
                  └────────────────────▶  _vendor/common.safe_write_text
```

The split is deliberate and load-bearing: `cli.py` owns batch iteration, exit
codes and in-place writes; `_vendor/` owns all detection and transformation
logic and is **never edited in this repository**.

## Core Technologies

- **Language**: Python, `requires-python = ">=3.10"`
- **Runtime dependencies**: none — stdlib only
- **Build backend**: setuptools >= 68, `src/` layout
- **Distribution**: `language: python` pre-commit hook + console script `wm-hook`

## Key Libraries

Stdlib only, by design. A pre-commit hook that pulls a dependency tree slows
every commit in every adopting repository and widens the supply-chain surface
of a tool that rewrites source files. `unicodedata`, `re`, `zipfile`,
`argparse` and `pathlib` cover the whole problem.

Optional external binaries (`exiftool`, `qpdf`, `c2patool`) are discovered via
`which()` and used only by container/PDF paths that `wm-hook` does not invoke.

## Development Standards

### The vendoring rule (most important rule in this repo)

`src/wm_hook/_vendor/*.py` are byte-exact copies of `service/scripts/` from
`guillaumemeyer/watermarks-remover`, pinned by commit SHA with a SHA-256 per
file in `_vendor/VENDORED.json`.

- **Never edit `_vendor/` in place.** A fix to cleaning behaviour goes upstream
  or is compensated for in `cli.py`.
- To take upstream changes: bump `PINNED_REF` in `refresh.sh`, run it, review
  the per-file change summary, test, commit.
- `./refresh.sh --check` verifies no drift, offline.

Local routing decisions (e.g. adding `.qmd` to the markdown extension set)
belong in `cli.py`, not in the vendored files.

**The manifest hashes LF bytes.** `VENDORED.json` records SHA-256 over the
LF-normalized content git stores. On a checkout with `core.autocrlf=true` the
working tree would otherwise get CRLF and `refresh.sh --check` would report
drift on pristine files — disabling the only integrity control the vendoring
rule has. `.gitattributes` pins the vendored tree to `eol=lf` to prevent this.
Do not remove that rule.

**Import costs are asymmetric.** `text_unicode` is standalone and side-effect
free. `container_meta` and `common` mutate process stdio to UTF-8 on import and
pull `image_meta` with them. Production code should import the former freely and
avoid the latter; tests may import anything.

### Type safety
`from __future__ import annotations` throughout; PEP 604 unions
(`str | None`). No type checker is currently wired in.

### Safety invariants
Code touching user files must uphold these. They are the product's contract:

- **Atomic writes** — temp file in the destination directory, then
  `os.replace`. Never a partial file.
- **No symlink traversal on write** — `safe_write_bytes` refuses to write
  through a symlink.
- **Binary refusal** — magic-number, NUL-byte and control-density sniffing;
  a file that looks binary is skipped, never rewritten.
- **Byte-exact round-trip for non-UTF-8** — decode and encode both use
  `surrogateescape`.
- **Bounded input** — `MAX_INPUT_BYTES` (default 256 MiB) caps whole-file
  in-memory processing; `MAX_ZIP_DECOMPRESSED_BYTES` caps zip bombs.
- **Argv injection guard** — `safe_arg()` prefixes `./` to paths starting with
  `-` before they reach option-parsing external tools.

### Testing
**No test suite exists.** This is the single largest gap in a tool whose
default mode rewrites source files in place. New work should establish
`tests/` with, at minimum: golden-file round-trips, idempotence assertions,
exit-code coverage, and a preservation corpus (emoji, RTL, CJK, Indic).

## Development Environment

### Required Tools
Python >= 3.10. `uv` is used locally for ephemeral interpreters and builds.
`pre-commit` for hook integration. `bash` + `curl` for `refresh.sh`.

### Common Commands
```bash
# Run the CLI from source
PYTHONPATH=src python -m wm_hook.cli --check path/to/file.md

# Ephemeral run without installing
uv run --python 3.12 --no-project python -m wm_hook.cli file.md

# Build and inspect the wheel (verify _vendor ships)
uv build

# Verify the vendored files match VENDORED.json (offline)
./refresh.sh --check

# Validate the hook manifest
uvx pre-commit validate-manifest .pre-commit-hooks.yaml
```

## Key Technical Decisions

**`sys.path.insert` for vendored imports.** `cli.py` prepends `_vendor/` to
`sys.path` so the vendored modules import each other by bare name
(`from common import ...`) exactly as upstream does. This is what keeps them
byte-exact. Two known costs: the very generic name `common` shadows any other
`common` for the whole process, and importing it reconfigures process stdio to
UTF-8 as a side effect.

**Exit code 1 on modification.** Follows the pre-commit autofix convention:
the commit fails, the developer inspects and re-stages. `2` is reserved for
I/O errors so CI can distinguish "dirty" from "broken".

**Explicit `files:` regex instead of `types: [text]`.** `identify` does not
know `.qmd`/`.qml`, so type filtering would silently skip Quarto and Qt files.
The cost is that the extension list is case-sensitive and must be maintained
by hand.

**Aggressive transforms stay off.** `aggressive_homoglyphs`, `nfkc`,
`strip_emoji_glue` and `strip_bidi` are supported upstream but not enabled and
not exposed as flags. Each has a false-positive profile unacceptable for an
unattended commit-time rewrite.

---
_Document standards and patterns, not every dependency_
