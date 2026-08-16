# Before and after

This page is the full catalogue. It shows one worked example for every class of
hidden data the tool knows about, plus the cases it gets wrong.

If you only want to run the tool, read [Quickstart](../usage/quickstart.md)
first. It is shorter and it has the install commands.

**Generated 2026-08-16.** Every example below is real output from the shipped
tool. Nothing here is drawn by hand.

## How to read the examples

Invisible characters are printed as `<U+XXXX>`. In the real files you see
nothing at all. That is the whole problem.

Three commands appear on this page.

| Command | What it does | Writes files? |
| --- | --- | --- |
| `wm-hook --detect` | reports a verdict and says why | no |
| `wm-hook --check` | reports what would change | no |
| `wm-hook` | rewrites the file in place | **yes** |

The detector and the cleaner are separate. The detector decides if hidden data
is present. The cleaner deletes invisible characters whether or not they hide
anything.

They disagree in both directions. The last two sections show where.

## The test tree

Fourteen files, one for each case on this page. This is what the detector
prints for the whole tree.

```console
$ wm-hook --detect .
14 file(s) scanned

      1  none     no invisible characters at all
      7  benign   invisible characters, all legitimate
      1  anomaly  unexplained, but too little to call it hidden data
      2  carrier  hidden data found
      3  payload  hidden data found, and it can be read

Files with hidden data:
  nerdfont.zsh    private_use_in_text
  private-use.md  private_use_in_text
  selectors.md    reads: 'run42'
  tag-block.md    reads: 'gen=2026-08-16'
  zero-width.md   reads: 'A'

5 of 14 file(s) carry hidden data. Run -v for the reasons.

A clean result does not mean a human wrote the text. It only means
nothing is hidden in the characters. Anthropic marks Claude output by
changing which words are chosen, which leaves no trace this can see.
```

The five verdict levels and the structural weights are explained in
[Detect carriers](../usage/detect.md).

??? note "Build the tree yourself: save this as `make_fixtures.py`"

    Run it with `python make_fixtures.py fx`, then `cd fx`. The script is pure
    ASCII, so copy and paste cannot damage it.

    ```python
    import pathlib, shutil, sys

    root = pathlib.Path(sys.argv[1])
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    def T(s):   # tag block, one tag character per ASCII character
        return "".join(chr(0xE0000 + ord(c)) for c in s)

    def B(data):   # zero-width bit stream, ZWSP = 0 and ZWNJ = 1
        bits = "".join(f"{b:08b}" for b in data)
        return "".join("\u200b\u200c"[int(x)] for x in bits)

    def VS(data):   # variation selectors, one byte each
        return "".join(chr(0xFE00 + b) if b < 16 else chr(0xE0100 + b - 16) for b in data)

    def W(name, text):
        (root / name).write_bytes(text.encode("utf-8"))

    # hidden data
    W("zero-width.md", "The release ships on Tuesday." + B(b"A") + "\n")
    W("tag-block.md", "# Release notes\n\nShipped today." + T("gen=2026-08-16") + "\n")
    W("selectors.md", "Deploy now." + VS(b"run42") + "\n")
    W("private-use.md", "Deploy now.\ue000\ue001\uf8ff\n")
    W("homoglyphs.md", "Ship\u00a0it now\u00a0and tell\u00a0the team\u00a0today ok\n")
    W("bidi.js", "if (isAdmin) {\n  // \u202egnitidua pots\u202c\n  grant();\n}\n")

    # correctly left alone
    W("emoji.md",
      "Ship it \u26a0\ufe0f now.\n\n"
      "Team: \U0001f468\u200d\U0001f469\u200d\U0001f467\n\n"
      "Flag: \U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f\n")
    W("cjk-vs.md", "\u8fbb\U000e0100\u5b50 and \u845b\ufe00\u57ce build notes\n")
    W("devanagari-zwj.md", "\u0915\u094d\u200d\u0937 and \u0930\u094d\u200d\u092f in the stemmer\n")
    W("plain.py", 'def main() -> int:\n    print("hello")\n    return 0\n')

    # incorrectly changed
    W("sanskrit.js",
      "generateStopWordFilter('\u0924\u0925\u093e \u0905\u092f\u092e\u094d\u200c "
      "\u090f\u0915\u092e\u094d\u200c \u0907\u0924\u094d\u092f\u0938\u094d\u092e"
      "\u093f\u0928\u094d\u200c')\n")
    W("cjk-space.md", "\u3053\u3093\u306b\u3061\u306f\u3000\u4e16\u754c\n")
    W("ci.yml", "jobs:\n  build:\n    steps: []\n\u00a0notify: true\n")
    W("nerdfont.zsh", 'PROMPT="\ue0b0 %~ \uf07c "\n')
    ```

## One example per carrier class

| Class | Codepoints | Verdict | Payload | Cleaner |
| --- | --- | --- | --- | --- |
| [Zero-width bit stream](#zero-width-bit-stream) | `U+200B` `U+200C` | payload | `A` | removes 8 |
| [Unicode tag block](#unicode-tag-block) | `U+E0000` to `U+E007F` | payload | `gen=2026-08-16` | removes 14 |
| [Variation selectors](#variation-selectors) | `U+FE00` to `U+FE0F`, `U+E0100` to `U+E01EF` | payload | `run42` | removes 5 |
| [Private use](#private-use-characters) | `U+E000` to `U+F8FF` | carrier | none | removes 3 |
| [Bidirectional override](#bidirectional-override) | `U+202E` `U+202C` | anomaly | none | removes 2 |
| [Space homoglyphs](#space-homoglyphs) | `U+00A0` | benign | none | replaces 4 |

### Zero-width bit stream

Two codepoints that both render as nothing. One is a `0`, the other is a `1`.

```text
before  The release ships on Tuesday.<U+200B><U+200C><U+200B><U+200B><U+200B><U+200B><U+200B><U+200C>
after   The release ships on Tuesday.
```

54 bytes before, 30 after. Eight characters carry one byte, and it reads `A`.

Three weights fire: `run`, `binary_alphabet` and `byte_aligned`. The tool
reports moderate confidence.

### Unicode tag block

This block copies ASCII one to one and renders as nothing. A whole readable
string can ride along inside ordinary text.

```text
before  # Release notes

        Shipped today.<U+E0067><U+E0065><U+E006E><U+E003D><U+E0032><U+E0030><U+E0032><U+E0036><U+E002D><U+E0030><U+E0038><U+E002D><U+E0031><U+E0036>
after   # Release notes

        Shipped today.
```

88 bytes before, 32 after. Each tag character costs 4 bytes. The payload reads
`gen=2026-08-16`, and the tool reports high confidence.

### Variation selectors

There are 256 of them. Chain them after any base character and each one carries
a byte.

```text
before  Deploy now.<U+E0162><U+E0165><U+E015E><U+E0124><U+E0122>
after   Deploy now.
```

32 bytes before, 12 after. Five selectors, five bytes, and the payload reads
`run42`. Only one weight fires here, `run`, but the payload decodes cleanly, so
the tool reports high confidence.

### Private-use characters

These codepoints have no assigned meaning, so they are an obvious hiding place.

```text
before  Deploy now.<U+E000><U+E001><U+F8FF>
after   Deploy now.
```

21 bytes before, 12 after. Nothing decodes, so the verdict stops at `carrier`.
This range is also where icon fonts live, which is why the tool gets the
[Nerd Font case](#a-terminal-prompt-with-icon-glyphs) wrong.

An earlier baseline of 1,268 files found no private-use codepoints at all: see
[Results](../experiment/baseline.md).

### Bidirectional override

`U+202E` reverses the reading direction. Source code can render one way and
compile another. This is the Trojan Source attack.

```text
before  if (isAdmin) {
          // <U+202E>gnitidua pots<U+202C>
          grant();
        }
after   if (isAdmin) {
          // gnitidua pots
          grant();
        }
```

53 bytes before, 47 after. The comment reads `stop auditing` on screen.

No structural weight fires here, because two characters are not a pattern. The
verdict stops at `anomaly`. The tool looks for hidden data, not for attacks, so
use a dedicated bidi linter if this is your threat.

### Space homoglyphs

Sixteen codepoints look like a space. Choosing between them encodes bits, and
nothing on screen looks wrong.

```text
before  Ship<U+00A0>it now<U+00A0>and tell<U+00A0>the team<U+00A0>today ok
after   Ship it now and tell the team today ok
```

43 bytes before, 39 after. Four no-break spaces became plain spaces.

!!! warning "The detector calls this file clean"

    A no-break space is correct typography in French and in several other
    languages, so the detector explains all four and returns `benign`. The
    cleaner replaces them anyway. This channel is a known blind spot in the
    detector.

## What is correctly left alone

Leaving legitimate characters alone is the harder half of the job. Every file
below is byte-identical after the cleaner runs, and the detector explains every
invisible character in it.

| File | What it holds | Bytes | Verdict |
| --- | --- | --- | --- |
| `emoji.md` | VS16, two joiners, a subdivision flag | 82, unchanged | benign |
| `cjk-vs.md` | two variation selectors on ideographs | 37, unchanged | benign |
| `devanagari-zwj.md` | half-form joiner and eyelash reph | 45, unchanged | benign |
| `plain.py` | nothing invisible | 51, unchanged | none |

### Emoji sequences

```text
before  Ship it ⚠<U+FE0F> now.

        Team: 👨<U+200D>👩<U+200D>👧

        Flag: 🏴<U+E0067><U+E0062><U+E0073><U+E0063><U+E0074><U+E007F>
after   Ship it ⚠<U+FE0F> now.

        Team: 👨<U+200D>👩<U+200D>👧

        Flag: 🏴<U+E0067><U+E0062><U+E0073><U+E0063><U+E0074><U+E007F>
```

Nine invisible characters, and the detector explains all nine. The Scottish
flag survives with its five tag letters and its `U+E007F` terminator, even
though tag characters anywhere else count as hidden data.

### Variation selectors on ideographs

```text
before  辻<U+E0100>子 and 葛<U+FE00>城 build notes
after   辻<U+E0100>子 and 葛<U+FE00>城 build notes
```

One selector after a legal base is spelling, not payload. Japanese personal
names depend on this. A run of selectors on one base is a payload, because no
base takes two.

### Devanagari joiners

```text
before  क्<U+200D>ष and र्<U+200D>य in the stemmer
after   क्<U+200D>ष and र्<U+200D>य in the stemmer
```

Both joiners have a letter of the same script on each side, so the tool keeps
them. The next section shows where that rule fails.

## What is incorrectly changed

Four cases. Three are the cleaner damaging correct text. One is the detector
raising a false alarm.

| File | What goes wrong | Bytes |
| --- | --- | --- |
| `sanskrit.js` | word-final joiners deleted, spelling changed | 102 to 93 |
| `cjk-space.md` | ideographic space flattened to ASCII | 25 to 23 |
| `ci.yml` | valid YAML becomes invalid | 44 to 43 |
| `nerdfont.zsh` | icon glyphs reported as hidden data, then deleted | 21 to 15 |

Read [What breaks](breakage.md) before you point the cleaner at a tree.

### Sanskrit stop words

```text
before  generateStopWordFilter('तथा अयम्<U+200C> एकम्<U+200C> इत्यस्मिन्<U+200C>')
after   generateStopWordFilter('तथा अयम् एकम् इत्यस्मिन्')
```

Three joiners deleted, and the spelling changes. Each one sits at the end of a
word, so no same-script letter follows it and the rule above does not protect
it.

The detector is right to call this file clean. The cleaner damages it anyway.

### Japanese ideographic space

```text
before  こんにちは<U+3000>世界
after   こんにちは 世界
```

`U+3000` is the normal wide space in Japanese and Chinese typesetting.
Replacing it with an ASCII space makes the gap too narrow.

### A YAML file that stops parsing

```text
before  jobs:
          build:
            steps: []
        <U+00A0>notify: true
after   jobs:
          build:
            steps: []
         notify: true
```

One character. Before the change, `notify` is a top-level key whose name starts
with a no-break space, and the file parses. After the change it is an indented
line, and the file does not parse.

A second run reports the file as clean.

### A terminal prompt with icon glyphs

```text
before  PROMPT="<U+E0B0> %~ <U+F07C> "
after   PROMPT=" %~  "
```

This is the one false alarm on the page. Nerd Fonts and Powerline put icon
glyphs in the private-use range, so the detector reports `private_use_in_text`
and calls the file a carrier. The cleaner then deletes both glyphs and the
prompt loses its icons.

A fix is specified: the default will change to keep private-use characters.
Until it lands, exclude your shell and editor configuration from the hook.

## Reproducing these

```console
$ wm-hook --check tag-block.md
wm-hook: tag-block.md: changed — would clean (unicode removed=14 replaced=0)
$ echo $?
1
$ wm-hook tag-block.md
wm-hook: tag-block.md: changed — cleaned (unicode removed=14 replaced=0)
```

`--check` never writes and exits `1` when a file would change. Bare `wm-hook`
rewrites the file and exits `1` because it changed something. There is no
backup file, so run it under git on a clean tree and read the diff.

A positive result is strong evidence that something embedded hidden data. A
clean result is not evidence that a human wrote the text: see
[What it means](../experiment/what-it-means.md).
