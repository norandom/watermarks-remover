# The pre-commit hook

The hook runs `wm-hook` on the files you are about to commit. There are two
hook ids.

| Hook id | What it does | Stage |
| --- | --- | --- |
| `wm-hook` | Rewrites the files in place, then fails the commit | `pre-commit` |
| `wm-hook-check` | Reports what would change, writes nothing | `manual` |

!!! danger "The default hook rewrites your files"

    `wm-hook` edits source files in place and has known defects: it damages
    Devanagari spelling, Japanese spacing and some YAML files. Read
    [What breaks](../reference/breakage.md) before you enable it.

## Configure it

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/norandom/watermarks-remover
    rev: v0.1.0a1
    hooks:
      - id: wm-hook              # rewrites files, fails the commit
        exclude: '^(tests/fixtures/|locales/|site/|vendor/)'
      - id: wm-hook-check        # manual stage, reports only
```

```bash
pre-commit install
pre-commit run --all-files
```

Run `--all-files` once before you trust the hook. It shows every change in one
diff, instead of one commit at a time.

pre-commit builds its own environment, so you install nothing else. For the
other install options and a worked example of a failing commit, see
[Quickstart](quickstart.md).

## Which files the hook reads

The hook carries its own list of file extensions: Markdown, plain text, Python,
JavaScript, TypeScript, CSS, JSON, YAML, TOML, CSV and about twenty more. It
ignores every other extension, and it excludes `tests/corpus/`.

`wm-hook-check` sits in the `manual` stage, so a normal commit does not run it.
Run it yourself:

```bash
pre-commit run --hook-stage manual wm-hook-check --all-files
```

## Exclusions you almost certainly want

| Path | Why |
| --- | --- |
| `site/`, `_build/`, `public/` | Built docs. MkDocs ships 32 search language packs that contain legitimate invisible characters |
| `vendor/`, `third_party/` | Not your code, and the hook cannot tell the difference |
| `locales/`, `i18n/`, `*.po` | Non-breaking spaces are correct typography there |
| Byte-exact test fixtures | Their whole purpose is exact bytes |

## Where it goes in your hook order

Put `wm-hook` after anything that writes text, and before anything that formats
it.

```yaml
# 1. generators (codegen, agent hooks)
# 2. normalisers  <- wm-hook goes here
# 3. formatters
# 4. linters
```

Two mechanics decide this:

- pre-commit runs hooks in the order you declare them.
- By default it runs every hook, even after one fails. Each hook sees the
  output of the hook before it.

A hook that changes bytes after a formatter has run undoes the formatter's
work. Your next commit reformats the file, and the two hooks keep fighting.
Anything that writes text after `wm-hook` is never checked.

Putting `wm-hook` last gains nothing. Formatters emit ASCII and do not add
invisible characters.

Two hazards:

- Do not set `fail_fast: true`. With autofix hooks you fix one hook per commit
  attempt, so `wm-hook` may never get to run.
- `wm-hook` removes a leading byte order mark (BOM). Exclude any file that
  needs its BOM. `fix-byte-order-marker` from `pre-commit-hooks` does the same
  job, so you do not need both hooks.

## Agentic CI

A pre-commit hook cannot see what your agent writes in CI after the commit. Add
a gate to the pipeline:

```yaml
- run: <agentic step>
- run: pre-commit run --hook-stage manual wm-hook-check --all-files
- run: <tests>
```

Use the check hook, not the autofix hook. A gate that rewrites the tree it is
judging tells you nothing.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Every file is already clean, or was skipped as binary |
| `1` | At least one file changed, or would change under `--check` |
| `2` | At least one file could not be read or written |

Exit `1` is the pre-commit autofix convention: the commit fails, you read the
diff, stage the file again and commit again. Code `0` also covers files skipped
as binary. The output names those files, but the exit code does not separate
them from clean ones.

Exit codes for every command: [Quickstart](quickstart.md#exit-codes).
