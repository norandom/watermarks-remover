# Quickstart

`wm-hook` finds carriers in text. A carrier is a character you cannot see that
hides data. This page is one worked example, and every block of output is real.

## Install

You do not need to activate a virtualenv. Pick one option.

=== "No install (recommended)"

    ```console
    $ uvx --from 'git+https://github.com/norandom/watermarks-remover' wm-hook --version
    wm-hook 0.1.0a2
    ```

    `uvx` builds a throwaway environment and deletes it again.

=== "On your PATH"

    ```bash
    uv tool install 'git+https://github.com/norandom/watermarks-remover'
    ```

    Then `wm-hook` is a normal command. Update it with `uv tool upgrade`.

=== "pre-commit only"

    ```yaml
    # .pre-commit-config.yaml
    repos:
      - repo: https://github.com/norandom/watermarks-remover
        rev: v0.1.0a2
        hooks:
          - id: wm-hook
    ```

    pre-commit builds the environment itself. Nothing else is needed.

## Look before you touch

Here is a demo tree of four files. Two hide data, one holds legitimate invisible
characters, one holds none.

??? note "Build it yourself: save this as `make_demo.py` and run it"

    ```python
    import pathlib
    T = lambda s: "".join(chr(0xE0000 + ord(c)) for c in s)
    B = lambda d: "".join("\u200b\u200c"[int(x)] for x in "".join(f"{b:08b}" for b in d))
    root = pathlib.Path("demo"); root.mkdir()
    W = lambda name, text: (root / name).write_text(text, encoding="utf-8")
    W("release-notes.md", "# Release 2.4.0" + T("gen=claude-opus-4;run=8f31c2a0") + "\n\nFixes the retry loop in the uploader.\n")
    W("changelog.md", "## Unreleased\n\n- Faster startup" + B(b"v41") + "\n")
    W("README.md", "\ufeff# Notes\n\n\u26a0\ufe0f Build on Linux only.\n\nFamille\u202f: \U0001f468\u200d\U0001f469\u200d\U0001f467\n\nRelisez le diff\u202f!\n")
    W("app.py", 'def main() -> int:\n    print("hello")\n    return 0\n')
    ```

`--detect` reads files and never writes. Give it a directory and it walks the tree,
skipping `.git`, `node_modules`, `.venv`, `dist`, `build`, `target` and `site`.

`-v` prints one block per file. Without it you get only the summary at the end.

```console
$ wm-hook --detect -v .
CARRIER! changelog.md: covert carrier present, and it decodes
         24 carrier(s), 0 explained, 24 unexplained
         + run (+2): 24 consecutive unexplained zero_width at offset 33
         + binary_alphabet (+3): run of 24 uses exactly two codepoints (U+200B U+200C) -- a bit stream
         + byte_aligned (+1): run length 24 is a multiple of 8
         > zero-width binary (ZWSP/ZWNJ) @33 [probable]
           'v41'
         confidence: moderate; capacity 24 bits
CLEAN    README.md: invisible characters present, all legitimate
         6 carrier(s), 6 explained, 0 unexplained
CARRIER! release-notes.md: covert carrier present, and it decodes
         30 carrier(s), 0 explained, 30 unexplained
         + run (+2): 30 consecutive unexplained tag_chars at offset 15
         + tag_outside_flag (+3): 30 tag character(s) outside a subdivision flag sequence; the tag block has no other sanctioned use
         > unicode tag block @15 [confirmed]
           'gen=claude-opus-4;run=8f31c2a0'
           identifies: 8f31c2a0, claude, gen=
         confidence: high; capacity 210 bits

4 file(s) scanned

      1  none     no invisible characters at all
      1  benign   invisible characters, all legitimate
      2  payload  hidden data found, and it can be read

Files with hidden data:
  changelog.md      reads: 'v41'
  release-notes.md  reads: 'gen=claude-opus-4;run=8f31c2a0'

2 of 4 file(s) carry hidden data. Run -v for the reasons.
```

Four paragraphs are cut above. Two follow the `CARRIER!` blocks and say that a
carrier does not tell you who put it there. Two say that a clean file is not
proof that a human wrote it.

| Line | Meaning |
| --- | --- |
| `CARRIER! changelog.md` | 24 zero-width characters in a row. They use only two codepoints and the length divides by 8, so it is a bit stream. It decodes to `v41`. |
| `CLEAN README.md` | Six invisible characters, and the tool explains all six: a BOM, an emoji selector, two joiners inside a family emoji, two French spaces. |
| `CARRIER! release-notes.md` | 30 invisible tag characters that spell `gen=claude-opus-4;run=8f31c2a0`. |
| `app.py` is absent | A file with no invisible characters is not printed. Add `-v` to list it too. |

The weights in brackets, the confidence and the five verdict levels are explained in [Detect carriers](detect.md).

## Before and after

`--check` writes nothing and exits `1` if the file would change. Bare `wm-hook` rewrites it.

```console
$ wm-hook --check release-notes.md
wm-hook: release-notes.md: changed — would clean (unicode removed=30 replaced=0)
$ echo $?
1
$ wm-hook release-notes.md
wm-hook: release-notes.md: changed — cleaned (unicode removed=30 replaced=0)
```

The first line of the file, with invisible characters printed as `<U+XXXX>`:

```text
before  # Release 2.4.0<U+E0067><U+E0065><U+E006E><U+E003D><U+E0063><U+E006C><U+E0061><U+E0075><U+E0064><U+E0065><U+E002D><U+E006F><U+E0070><U+E0075><U+E0073><U+E002D><U+E0034><U+E003B><U+E0072><U+E0075><U+E006E><U+E003D><U+E0038><U+E0066><U+E0033><U+E0031><U+E0063><U+E0032><U+E0061><U+E0030>
after   # Release 2.4.0
```

178 bytes before, 58 after: each tag character costs 4 bytes. The visible text is byte-identical. There is no `.bak` file, because git is the backup.

## Wire it into pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/norandom/watermarks-remover
    rev: v0.1.0a2
    hooks:
      - id: wm-hook              # rewrites files, fails the commit
        exclude: '^(tests/fixtures/|locales/|site/|vendor/)'
      - id: wm-hook-check        # manual stage, reports only
```

```bash
pre-commit install
pre-commit run --all-files      # do this once and read the diff
```

A commit that adds a file with a carrier fails. The hook has already fixed the file, so stage it again and retry:

```console
$ git commit -m "add spec"
strip AI provenance marks (Layer A + md/qmd frontmatter).......................Failed
- hook id: wm-hook
- exit code: 1
- files were modified by this hook

wm-hook: spec.md: changed — cleaned (unicode removed=30 replaced=0)

$ git add spec.md
$ git commit -m "add spec"
strip AI provenance marks (Layer A + md/qmd frontmatter).......................Passed
[master 8ee1611] add spec
 1 file changed, 1 insertion(+)
 create mode 100644 spec.md
```

More on hook order, exclusions and CI gates: [The pre-commit hook](hook.md).

## Exit codes

| Command | `0` | `1` | `2` |
| --- | --- | --- | --- |
| `wm-hook --detect` | no carrier found | at least one carrier | a file was unreadable, or no text files were found |
| `wm-hook --check` | nothing would change | a file would change | a file was unreadable |
| `wm-hook` | nothing changed | a file was rewritten | a file could not be read or written |

!!! warning "`--detect` never writes. Bare `wm-hook` does."

    `wm-hook <dir>` rewrites the whole tree in place. Run it under git, on a clean working tree, and read the diff before you commit.

    The cleaner is not the detector. `--detect` called `README.md` above clean,
    but `wm-hook --check README.md` reports `removed=1 replaced=2`. It deletes
    the BOM and turns two correct French spaces into ordinary spaces.

    It also damages Devanagari spelling and CJK typography. Read
    [What breaks](../reference/breakage.md) first.

## What a clean result means

The test is one-sided. A positive result is strong evidence that something embedded
hidden data. A clean result is not evidence that a human wrote the text: see
[What it means](../experiment/what-it-means.md).

We scanned 1,155 files across 8 external repositories and established zero carriers:
see [Results](../experiment/baseline.md). To measure several repositories at once, see [Survey a tree](survey.md).
