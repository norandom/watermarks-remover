# Before and after

**Generated 2026-08-16** by running the shipped CLI against each input. Nothing
here is illustrative; every pair is real output.

Invisible characters are shown as `〈U+XXXX〉`. They are not visible in the
originals, which is the entire problem.

## Markdown

### Zero-width binary payload

The classic encoding channel: two codepoints, one bit each.

```text
before  The release ships on Tuesday.〈U+200B〉〈U+200C〉〈U+200B〉〈U+200B〉〈U+200C〉〈U+200C〉〈U+200B〉〈U+200C〉
after   The release ships on Tuesday.
```

`54 bytes -> 30. removed=8.` Eight bits, one byte of payload.

### Tag-block smuggling

`U+E0000`–`U+E007F` mirrors ASCII invisibly. A whole readable string rides along.

```text
before  # Release notes

        Shipped today.〈U+E0067〉〈U+E0065〉〈U+E006E〉〈U+E003D〉〈U+E0032〉〈U+E0030〉〈U+E0032〉〈U+E0036〉〈U+E002D〉〈U+E0030〉〈U+E0038〉〈U+E002D〉〈U+E0031〉〈U+E0036〉
after   # Release notes

        Shipped today.
```

`88 bytes -> 32. removed=14.` The payload decodes to `gen=2026-08-16`.

## Code

### Private-use characters

The "free Unicode space" hypothesis, which the baseline found **zero** instances
of in real repositories.

```text
before  Deploy now.〈U+E000〉〈U+E001〉〈U+F8FF〉
after   Deploy now.
```

`removed=3.` Note this also deletes Nerd Font glyphs and CJK gaiji. The default
is being changed to preserve them.

### A YAML file, structurally broken

```text
before  jobs:\n  build:\n    steps: []\n〈U+00A0〉notify: true\n
after   jobs:\n  build:\n    steps: []\n notify: true\n
```

`replaced=1.` One character. The file parsed before and does not parse after.
See [What breaks](breakage.md).

## What is correctly left alone

Equally important, and the harder half.

### Real code from a Codex-authored repository

An emoji presentation selector in a spec template:

```text
before  ...MUST be complete before ANY user story can be implemented
after   ...MUST be complete before ANY user story can be implemented
```

`status: clean.` Unchanged, correctly.

### Legitimate variation sequences

```text
before  日󠄀本󠄁語󠄂 build notes
after   日󠄀本󠄁語󠄂 build notes
```

`status: clean.` One ideographic variation selector per base is orthography.
A *run* of them on one base would be payload, because no base takes two.

### Emoji sequences

`⚖️`, `👨‍👩‍👧`, `❤️‍🔥` and the subdivision flag `🏴󠁧󠁢󠁳󠁣󠁴󠁿` all survive
unchanged, including the flag's five tag characters and its `U+E007F`
terminator.

## What is incorrectly changed

Documented in full at [What breaks](breakage.md). Summarised:

```text
before  तथा अयम्〈U+200C〉 एकम्〈U+200C〉 इत्यस्मिन्〈U+200C〉
after   तथा अयम् एकम् इत्यस्मिन्
```

Real Sanskrit orthography, real third-party file, silently corrupted.

## Reproducing these

```bash
uv run --python 3.12 wm-hook --check path/to/file    # report, never writes
uv run --python 3.12 wm-hook path/to/file            # rewrite in place
```

`--check` exits 1 if the file would change and leaves it untouched.
