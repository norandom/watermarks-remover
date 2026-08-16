# watermarks-remover

`wm-hook` finds and removes invisible Unicode characters that hide data in text.

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
uvx --from git+https://github.com/norandom/watermarks-remover@v0.1.0a1 wm-hook --detect .
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

## What it found

- Scanned on 2026-08-16: 8 external repositories, 1,155 text files.
- 0 carriers established. 1 anomaly.
- That bounds the false-positive rate at 0.26% per file, with 95% confidence.
- Nothing deliberately hid data in that corpus. The negative result is the
  finding.
- Corpus, numbers and dates: [Results](experiment/baseline.md).

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
