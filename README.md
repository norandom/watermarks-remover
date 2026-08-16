# watermarks-remover

Finds data that someone hid inside text using characters you cannot see, and
removes it.

**Full documentation: <https://norandom.github.io/watermarks-remover/>** — how a
verdict is decided, what the tool damages, what was measured, and what a result
does and does not prove.

[![release v0.1.0a2 pre-release](https://img.shields.io/badge/release-v0.1.0a2%20pre--release-orange)](https://github.com/norandom/watermarks-remover/releases/tag/v0.1.0a2)
[![licence MIT](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)

> Pre-release, no warranty. This is a measurement experiment, not a tool for
> passing AI-written work off as human.

## Install

Nothing to install permanently. `uvx` builds a throwaway environment, runs the
tool, then deletes it again.

```bash
uvx --from 'git+https://github.com/norandom/watermarks-remover' wm-hook --detect .
```

To keep it on your PATH:

```bash
uv tool install 'git+https://github.com/norandom/watermarks-remover'
```

Both track the default branch, so you get the newest code. Add `@v0.1.0a2` to
the URL if you would rather pin a version.

No shell tooling at all? Two scripts list invisible characters and stop there:

```powershell
irm https://raw.githubusercontent.com/norandom/watermarks-remover/main/scripts/detect.ps1 | iex
```

```bash
curl -fsSL https://raw.githubusercontent.com/norandom/watermarks-remover/main/scripts/detect.sh | bash
```

The PowerShell one needs Windows PowerShell 5.1, which ships with Windows 10 and
11. Read anything you pipe into a shell. Both only read files.

## Detect from the command line

`--detect` only reads. It never changes a file.

```console
$ wm-hook --detect .
2 file(s) scanned

      1  none     no invisible characters at all
      1  payload  hidden data found, and it can be read

Files with hidden data:
  release-notes.md  reads: 'gen=claude-opus-4;run=8f31c2a0'

1 of 2 file(s) carry hidden data. Run -v for the reasons.
```

Add `-v` for the reasoning behind each verdict:

```console
$ wm-hook --detect -v release-notes.md
CARRIER! release-notes.md: covert carrier present, and it decodes
         30 carrier(s), 0 explained, 30 unexplained
         + run (+2): 30 consecutive unexplained tag_chars at offset 29
         + tag_outside_flag (+3): 30 tag character(s) outside a subdivision
           flag sequence; the tag block has no other sanctioned use
         > unicode tag block @29 [confirmed]
           'gen=claude-opus-4;run=8f31c2a0'
           identifies: 8f31c2a0, claude, gen=
         confidence: high; capacity 210 bits
```

Point it at a directory and it walks the tree, skipping `.git`,
`node_modules`, `.venv`, `dist`, `build` and `site`. Dot directories such as
`.claude` and `.kiro` are skipped too; `--include-hidden-files` puts them back.

Exit codes: `0` nothing found, `1` hidden data found, `2` a file could not be
read or no text files were found.

## What the invisible characters actually encode

The file above looks like one line of text:

```text
The release ships on Tuesday.
```

It is 29 visible characters followed by 30 invisible ones. The invisible run is
in the Unicode **tag block**, `U+E0000`–`U+E007F`, which mirrors ASCII exactly:
add `U+E0000` to an ASCII code point and you get a character that renders as
nothing at all.

| Invisible character | ASCII it mirrors |
| --- | --- |
| `U+E0067` | `g` |
| `U+E0065` | `e` |
| `U+E006E` | `n` |
| `U+E003D` | `=` |
| `U+E0063` | `c` |
| `U+E006C` | `l` |

Read the whole run that way and it spells:

```text
gen=claude-opus-4;run=8f31c2a0
```

That is why the tool decodes payloads instead of only counting characters. A
count tells you 30 tag characters are present. The decode tells you what they
say, and here they name their own producer.

Other carriers encode differently. Variation selectors carry one arbitrary byte
each. Zero-width characters carry one bit each, so eight of them make a byte.
Private-use codepoints have no assigned meaning at all. Each one, and when it is
legitimate, is catalogued in
[Invisible characters](https://norandom.github.io/watermarks-remover/reference/characters/).

## Remove them

```console
$ wm-hook --check release-notes.md
wm-hook: release-notes.md: changed — would clean (unicode removed=30 replaced=0)

$ wm-hook release-notes.md
wm-hook: release-notes.md: changed — cleaned (unicode removed=30 replaced=0)
```

`--check` reports and writes nothing. Bare `wm-hook` rewrites files in place, so
run it under git and read the diff.

> [!WARNING]
> The cleaner damages correct text: Devanagari spelling, CJK typography and
> some YAML. Every defect we reproduced is listed with its status in
> [What breaks](https://norandom.github.io/watermarks-remover/reference/breakage/).

## Install the pre-commit hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/norandom/watermarks-remover
    rev: v0.1.0a2
    hooks:
      - id: wm-hook              # rewrites files, fails the commit
        exclude: '^(site/|vendor/|locales/)'
      - id: wm-hook-check        # manual stage, reports only
```

```bash
pre-commit install
pre-commit run --all-files      # do this once, and read the diff
```

`wm-hook` rewrites a changed file and exits 1, so the commit fails and you
re-stage. `wm-hook-check` only reports.

`rev:` stays pinned on purpose. pre-commit caches by rev and warns on a mutable
reference, so a team should run one known version. Move it with
`pre-commit autoupdate`. Hook ordering and exclusions:
[The pre-commit hook](https://norandom.github.io/watermarks-remover/usage/hook/).

## Everything else

| Question | Page |
| --- | --- |
| What does a positive or a clean result prove? | [What a result means](https://norandom.github.io/watermarks-remover/experiment/what-it-means/) |
| What was actually found in real repositories? | [Results](https://norandom.github.io/watermarks-remover/experiment/baseline/) |
| How is a verdict decided? | [Detect carriers](https://norandom.github.io/watermarks-remover/usage/detect/) |
| Can I sign my own text? | [Sign your own text](https://norandom.github.io/watermarks-remover/usage/signing/) |
| What does the cleaner break? | [What breaks](https://norandom.github.io/watermarks-remover/reference/breakage/) |

## Provenance and licence

A fork, not a vendored dependency. The cleaning code in `src/wm_hook/core/`
began as a copy of
[`guillaumemeyer/watermarks-remover`](https://github.com/guillaumemeyer/watermarks-remover)
and has been edited freely since. Origin commits are in [NOTICE](NOTICE).

MIT, see [LICENSE](LICENSE). Provided without warranty of any kind. Code
inherited from upstream carries upstream's licensing.
