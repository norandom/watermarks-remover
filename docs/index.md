# watermarks-remover

`wm-hook` finds and removes invisible Unicode characters that hide data in text.

![The Sandman scattering invisible Unicode tag characters over three sleeping
developers. Labels trace each speck to the ASCII it mirrors — U+E0067 to g,
U+E0065 to e, U+E006E to n, U+E003D to =, U+E0063 to c, U+E006C to l — and a
panel decodes the whole run as gen=claude-opus-4;run=8f31c2a0. On the monitor
behind them the file reads only "The release ships on Tuesday." A sign on the
wall says: invisible characters, visible problems.](assets/sandman.webp)

The file on that screen holds one visible sentence and thirty characters that
render as nothing. The tag block `U+E0000`–`U+E007F` mirrors ASCII exactly, so
each speck is one letter of a payload that names its own producer. See
[Invisible characters](reference/characters.md) for every carrier family, and
[Detect carriers](usage/detect.md) for how a run like that is judged.

## Why this exists

Coding agents now write a large share of the files in a normal repository. You
read the visible text, and you approve it.

Some Unicode characters render as nothing at all. A zero-width space or a
private-use codepoint can sit between two letters and carry bits. Several tools
claim to strip "AI watermarks" from text, so people assume the marks are there.

Are any actually hidden in your files?

One command answers that. The rest of this site explains what the answer is
worth. A positive result and a negative result mean very different things.

## Try it in 60 seconds

`--detect` only reads. It never changes a file.

```bash
uvx --from git+https://github.com/norandom/watermarks-remover wm-hook --detect .
```

Real output, from running that in `src/wm_hook/core` of this repository:

```text
3 file(s) scanned

      2  none     no invisible characters at all
      1  benign   invisible characters, all legitimate

No hidden data in 3 file(s).

A clean result does not mean a human wrote the text. It only means
nothing is hidden in the characters. Anthropic marks Claude output by
changing which words are chosen, which leaves no trace this can see.
```

Add `-v` to see one block per file, with the reason for each verdict.

Exit codes: `0` clean, `1` a carrier is established, `2` the input could not be
read or no text files were found.

Install, a full worked example and the hook setup are in the
[Quickstart](usage/quickstart.md).

## Or run it with nothing installed

Two throwaway scripts. They list every invisible character and stop there. They
have no explanation layer, so they cannot tell an emoji selector from hidden
data. Use them to look; use `wm-hook` for a verdict.

=== "Windows"

    Needs Windows PowerShell 5.1, which ships with Windows 10 and 11.

    ```powershell
    irm https://raw.githubusercontent.com/norandom/watermarks-remover/main/scripts/detect.ps1 | iex
    ```

    To scan somewhere else, set a variable first. A script piped into `iex`
    cannot take parameters.

    ```powershell
    $WmPath = 'C:\src\myrepo'; irm <same url> | iex
    ```

=== "Linux and macOS"

    Uses ripgrep, or falls back to `grep -P`.

    ```bash
    curl -fsSL https://raw.githubusercontent.com/norandom/watermarks-remover/main/scripts/detect.sh | bash
    ```

    Or with a path:

    ```bash
    curl -fsSL <same url> -o detect.sh && bash detect.sh /path/to/repo
    ```

!!! warning "Read anything you pipe into a shell"

    That goes for these and for every other `irm | iex` or `curl | bash` you
    are offered. Both scripts only read files. Neither writes, deletes, or
    connects anywhere. You can check that in a minute, and you should.

## What a result means

The test is one-sided.

- A positive is strong. Text does not grow byte-aligned runs of zero-width
  characters by itself, so something embedded hidden data on purpose.
- A negative says only that no hidden data is in the codepoints. It says
  nothing about who or what wrote the file.
- Read [What it means](experiment/what-it-means.md) before you quote a result
  to anyone.

## Where to go next

| Page | What it gives you |
| --- | --- |
| [Quickstart](usage/quickstart.md) | Install, a worked example, hook configuration |
| [Detect carriers](usage/detect.md) | How a verdict is decided, and the five verdict levels |
| [The pre-commit hook](usage/hook.md) | Strip carriers on every commit |
| [Sign your own text](usage/signing.md) | Put your own name in a file, invisibly |
| [Survey a tree](usage/survey.md) | Measure a whole repository at once |
| [Results](experiment/baseline.md) | The corpus and what was found in it |
| [What it means](experiment/what-it-means.md) | What a positive and a negative allow you to say |
| [Method](experiment/method.md) | How the measurement was run |
| [Invisible characters](reference/characters.md) | Each character, and what it indicates |
| [What breaks](reference/breakage.md) | Files the cleaner damages |
| [Before and after](reference/examples.md) | Worked examples of a rewrite |
| [Limits and disclaimer](disclaimer.md) | Scope, warranty, and the honest limits |

!!! warning "The cleaner damages some scripts"

    `wm-hook <dir>` without `--detect` rewrites files in place. It strips
    word-final joiners that Devanagari needs and flattens the ideographic space
    used in Japanese and Chinese. See [What breaks](reference/breakage.md).
