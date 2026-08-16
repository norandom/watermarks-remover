# The hook

A pre-commit hook that strips invisible carriers and AI frontmatter keys. Two
modes: validate, and remove.

!!! danger "Read the breakage page first"

    The default mode rewrites source files in place and has documented,
    reproduced defects. On one real repository it removed zero watermarks,
    corrupted a third-party library, and churned six already-clean files.

    See [What breaks](../reference/breakage.md).

## Two modes

### Validate

```console
$ wm-hook --check docs/*.md
wm-hook: docs/notes.md: changed — would clean (unicode removed=7 replaced=2)
$ echo $?
1
```

Nothing is written. Exit `1` means the file *would* change.

### Remove

```console
$ wm-hook docs/notes.md
wm-hook: docs/notes.md: changed — cleaned (unicode removed=7 replaced=2)
```

Rewritten atomically. **No `.bak` — git is the backup.** Exit is still `1`, the
pre-commit autofix convention: the commit fails, you inspect, re-stage, commit
again.

## Installing

```yaml
repos:
  - repo: https://github.com/norandom/watermarks-remover
    rev: v0.1.0a1
    hooks:
      - id: wm-hook              # rewrites files
        exclude: '^(tests/fixtures/|locales/|site/|vendor/)'
      - id: wm-hook-check        # manual stage, reports only
```

```console
pre-commit install
pre-commit run --all-files      # do this once, and read the diff
```

That first run is not optional advice. It shows the full blast radius in one
diff instead of one commit at a time.

## Exclusions you almost certainly want

| Path | Why |
| --- | --- |
| `site/`, `_build/`, `public/` | Built docs. MkDocs ships 32 lunr language packs containing legitimate invisible characters |
| `vendor/`, `third_party/` | Not your code, and the hook cannot tell |
| `locales/`, `i18n/`, `*.po` | Non-breaking spaces are correct typography |
| Byte-exact test fixtures | Their whole purpose is exact bytes |

## Where it goes in your hook order

After anything that writes text, before anything that formats it.

```yaml
# 1. generators (codegen, agentic hooks) - wm-hook cannot clean what runs after it
# 2. normalisers  <- wm-hook lives here
# 3. formatters   - they get the last word on layout
# 4. linters      - read-only, judge the final state
```

Two mechanics decide this. pre-commit runs hooks in declared order and, by
default, runs all of them even after one fails, so each sees the previous
output. A hook that mutates bytes after a formatter has run invalidates that
formatter's work, so your next commit reformats — perpetual churn between two
hooks that each converge alone. And anything authoring text *after* the hook is
unchecked.

Putting it last buys nothing: formatters emit ASCII and do not introduce
invisible characters.

Two hazards:

- **Do not set `fail_fast: true`** with autofix hooks. You fix one hook per
  commit attempt and `wm-hook` may never run.
- **`fix-byte-order-marker` conflicts with it.** One preserves a required BOM,
  the other removes it unconditionally. Whichever runs later wins. Pick one.

## Agentic CI

If your agent writes code in CI *after* the commit, no pre-commit hook sees its
output. Add a gate to the pipeline:

```yaml
- run: <agentic step>
- run: pre-commit run --hook-stage manual wm-hook-check --all-files
- run: <tests>
```

Use the check hook, not the autofix hook. A gate that silently rewrites the tree
it is judging tells you nothing.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Every file already clean, or skipped as binary |
| `1` | At least one file modified, or would be under `--check` |
| `2` | At least one file could not be read or written |

`0` covers "skipped as binary" as well as "clean", so a file that could not be
checked is currently indistinguishable from one that was.

## Standalone

```console
uvx --from 'git+https://github.com/norandom/watermarks-remover@v0.1.0a1' wm-hook --help
```

Takes explicit paths. It does not walk directories.
