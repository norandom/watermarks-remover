# watermarks-remover

Finds data that someone hid inside text with characters you cannot see, and
removes it.

Documentation: <https://norandom.github.io/watermarks-remover/>

[![release v0.1.0a1 pre-release](https://img.shields.io/badge/release-v0.1.0a1%20pre--release-orange)](https://github.com/norandom/watermarks-remover/releases/tag/v0.1.0a1)
[![licence MIT](https://img.shields.io/badge/licence-MIT-blue)](LICENSE)

> Measured 2026-08-16. Provided without warranty of any kind. This is a
> measurement experiment, not a tool for passing AI-written work off as human.
> See [Limits and disclaimer](https://norandom.github.io/watermarks-remover/disclaimer/).

## Try it

You do not need to install anything. `uvx` builds a throwaway environment, runs
the tool, and deletes the environment again.

```console
$ uvx --from 'git+https://github.com/norandom/watermarks-remover' \
      wm-hook --detect -v .
CARRIER! release-notes.md: covert carrier present, and it decodes
         30 carrier(s), 0 explained, 30 unexplained
         + run (+2): 30 consecutive unexplained tag_chars at offset 15
         + tag_outside_flag (+3): 30 tag character(s) outside a subdivision flag sequence; the tag block has no other sanctioned use
         > unicode tag block @15 [confirmed]
           'gen=claude-opus-4;run=8f31c2a0'
           identifies: 8f31c2a0, claude, gen=
         confidence: high; capacity 210 bits

2 file(s) scanned

      1  none     no invisible characters at all
      1  payload  hidden data found, and it can be read

Files with hidden data:
  release-notes.md  reads: 'gen=claude-opus-4;run=8f31c2a0'

1 of 2 file(s) carry hidden data. Run -v for the reasons.
```

That tree holds two files. `release-notes.md` hides a payload in invisible tag
characters, and `app.py` is plain. The script that builds the tree is in the
[Quickstart](https://norandom.github.io/watermarks-remover/usage/quickstart/).

Two paragraphs are cut from the output above. One says a carrier never tells you
who put it there. The other says a clean file is not proof that a human wrote it.

Without `-v` the tool prints only the summary block.

`--detect` only reads files. Bare `wm-hook <dir>` rewrites the whole tree in
place, so run that under git and read the diff. Exit codes for `--detect`: `0`
clean, `1` a carrier was established, `2` unreadable input or no text files found.

To keep the command on your PATH instead, run
`uv tool install 'git+https://github.com/norandom/watermarks-remover'`.

## Wire it into pre-commit

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/norandom/watermarks-remover
    rev: v0.1.0a1
    hooks:
      - id: wm-hook              # rewrites files, fails the commit
        exclude: '^(site/|vendor/|locales/)'
      - id: wm-hook-check        # manual stage, reports only
```

The install commands above deliberately track the default branch, so you always
get the newest code. Pin them yourself if you want a fixed version: add
`@v0.1.0a1` to the `git+` URL, or a tag to the raw script URL.

`rev:` is the exception and stays pinned. pre-commit caches by rev and its whole
point is that everyone on the team runs the same version, so it warns on a
mutable reference. Move it with `pre-commit autoupdate`.

Run `pre-commit run --all-files` once and read the diff before you trust it.
Hook order, exclusions and CI gates:
[The pre-commit hook](https://norandom.github.io/watermarks-remover/usage/hook/).

## Or run it with nothing installed at all

Two throwaway scripts. They list every invisible character and stop there, with
no explanation layer, so they cannot tell an emoji selector from hidden data.
Use them to look. Use `wm-hook` for a verdict.

**Windows.** Needs Windows PowerShell 5.1, which ships with Windows 10 and 11.

```powershell
irm https://raw.githubusercontent.com/norandom/watermarks-remover/main/scripts/detect.ps1 | iex
```

A script piped into `iex` cannot take parameters, so set a variable first:

```powershell
$WmPath = 'C:\src\myrepo'; irm <same url> | iex
```

**Linux and macOS.** Uses ripgrep, or falls back to `grep -P`.

```bash
curl -fsSL https://raw.githubusercontent.com/norandom/watermarks-remover/main/scripts/detect.sh | bash
```

Read anything you pipe into a shell, these included. Both only read files.
Neither writes, deletes, or connects anywhere.

## What a result means

- **A positive is strong.** Text does not grow byte-aligned runs of invisible
  characters between Latin letters by itself.
- **A negative proves nothing.** A statistical watermark leaves no trace in the
  characters, so an AI-written file is expected to scan clean.

Why the tool prints no "% AI" number, and what to say about a repository that is
AI-written and scans clean:
[What a result means](https://norandom.github.io/watermarks-remover/experiment/what-it-means/).

## More in the docs

| Question | Page |
| --- | --- |
| Which invisible characters exist, and when is each one legitimate? | [Invisible characters](https://norandom.github.io/watermarks-remover/reference/characters/) |
| What does the tool damage when it rewrites files? | [What breaks](https://norandom.github.io/watermarks-remover/reference/breakage/) |
| What does a cleaned file look like next to the original? | [Before and after](https://norandom.github.io/watermarks-remover/reference/examples/) |
| Why only characters, and not word choice or metadata? | [The three channels](https://norandom.github.io/watermarks-remover/experiment/what-it-means/) |

## Status

- Pre-release. v0.1.0a1 is a GitHub pre-release, with a wheel and an sdist
  attached. Development follows the specifications in `.kiro/`.
- The rewriting hook has defects that damage correct text: Devanagari spelling,
  CJK typography and some YAML files. Every defect we reproduced is listed with
  its fix status in
  [What breaks](https://norandom.github.io/watermarks-remover/reference/breakage/).
- `--detect` and `--check` never write, so those defects cannot reach your files.
- On one real repository the rewrite removed zero watermarks, corrupted one
  third-party library, and churned six files that were already clean.

## Provenance

A fork, not a vendored dependency. The cleaning code in `src/wm_hook/core/`
started as a copy of
[`guillaumemeyer/watermarks-remover`](https://github.com/guillaumemeyer/watermarks-remover)
and has been edited freely since. Origin commits are recorded in
[NOTICE](NOTICE).

## Licence

MIT. See [LICENSE](LICENSE). Provided without warranty of any kind.

Code inherited from upstream carries upstream's licensing.
