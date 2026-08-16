# Survey a tree

`scripts/wm-survey.py` scans a whole directory tree and reports rates. It only
reads files. It never writes.

The survey answers a different question from the hook. The hook asks "is this
file clean?". The survey asks "how much invisible material is in this tree, and
how much of it is legitimate?".

!!! note "The survey lives in the repository, not in the installed command"

    `wm-hook` is the command you install. The survey is a script in the source
    tree, and it is not part of the wheel. Clone the repository to run it.

## Running it

```bash
git clone https://github.com/norandom/watermarks-remover
cd watermarks-remover
python scripts/wm-survey.py /path/to/repo
```

| Argument | What it does |
| --- | --- |
| `<path>` | A directory to scan. Repeat it to scan several trees. |
| `--json` | Write the full report to stdout as JSON. |
| `--exclude PREFIX` | Skip paths that start with PREFIX. Repeat as needed. |

Always exclude your own carrier test fixtures. This project keeps deliberate
payloads in `tests/corpus/`, and they dominate every number unless you skip
them.

```bash
python scripts/wm-survey.py . --exclude tests/corpus/
python scripts/wm-survey.py repo-a repo-b --json > findings.json
```

The survey walks directories and skips `.git`, `node_modules`, `.venv`, `dist`,
`build`, `target` and `site`. It shares that list with the hook.

It differs in one way. The survey also reads dot directories such as `.github/`
and `.claude/`, which the hook leaves alone. Your file counts will therefore be
higher than the hook's.

!!! warning "Windows consoles"

    A decoded payload can hold a character your console cannot print. The
    report then stops with a `UnicodeEncodeError`. Set `PYTHONIOENCODING=utf-8`
    before you run it.

## The three numbers

A real run over this repository, on 2026-08-16:

```console
$ python scripts/wm-survey.py . --exclude tests/corpus/
  files scanned                 141
  files with any carrier        13  (9.22%)
  files with UNEXPLAINED        5  (3.55%)

  carriers found                144
    explained as legitimate     71  (49.31%)
    unexplained (candidates)    73
```

The first block counts files. The second block counts characters, and it is the
part that matters:

| Number | Meaning |
| --- | --- |
| **carriers found** | Every invisible or format codepoint in the tree. |
| **explained** | Those with a documented legitimate cause. |
| **unexplained** | The rest. These are the only watermark candidates. |

The tool never merges the three into one figure.

!!! danger "Carriers found is not a detection rate"

    Almost every invisible codepoint in real source code is legitimate.
    Reporting "carriers found" as a detection rate overstates the result by
    about two orders of magnitude. See
    [Results](../experiment/baseline.md) for the measured gap.

The counts above are high because this repository studies carriers. Its
unexplained ones sit in worked documentation examples and in the detector's own
test data. A normal project looks nothing like this.

## Reading the unexplained list

The survey prints where the unexplained carriers are, worst file first. It
shows the 20 worst files and up to five offsets in each:

```console
  unexplained detail:
    src/wm_hook/payload.py  x24
        @3389    U+FE00 VARIATION SELECTOR-1 [variation_selector]
        @3391    U+FE0F VARIATION SELECTOR-16 [variation_selector]
        @4224    U+200B ZERO WIDTH SPACE [zero_width]
```

Each line gives the character offset in the file, the codepoint, its Unicode
name and its class. Open the file at that offset and judge it yourself. If the
file is test data or a documented example, add it to `--exclude` and run again.

## What counts as explained

| Carrier | Explained when |
| --- | --- |
| Variation selector | it follows an emoji, symbol or ideograph base |
| `U+200C` / `U+200D` | it sits between letters of a script that needs it, or at a word boundary after one |
| `U+200B` | it follows a base in a script that uses it as a word separator |
| `U+FEFF` | it is at offset zero |
| Space homoglyph | it is typographic, or an ideographic space in CJK |
| Tag characters | they are inside a subdivision flag sequence |
| Directional marks | they are in mixed-direction text |

The survey resolves context against the nearest **base** character before the
carrier, skipping any other carriers on the way. Without that step the joiner
in `❤️‍🔥` looks like it follows a variation selector rather than the heart, and
the survey reports it as a payload.

## The verdict block

The survey runs the same classifier as `wm-hook --detect` and counts files per
verdict level:

```console
  COVERT CARRIER PRESENT?
    none                   128 file(s)
    benign                 8 file(s)
    anomaly                2 file(s)
    carrier                3 file(s)
    -> established in           3 file(s)
       src/wm_hook/payload.py  [carrier/high] run, run, private_use_in_text  76 bits
```

It reports counts per level and never a percentage. See
[Detect carriers](detect.md) for what each level means and how the score is
built.

## The explanation layer is the weak point

The survey is only as good as its ability to say "this carrier is legitimate".
Explain too much and real marks disappear. Explain too little and every emoji
raises an alarm.

The first version got this wrong 15 times across 4 files. It inherited two
blind spots from the cleaner:

- Five emoji base characters sit outside the Symbol categories, so their
  presentation selectors looked like payloads.
- Context resolution looked back exactly one character, so a joiner that
  followed a variation selector lost its base.

Both are fixed. One limitation remains: **source that escapes a character but
leaves its combining mark literal**.

A file can contain `\U0001f441` written as an escape sequence, followed by a
real `U+FE0F`. No base character exists in the file, so the survey cannot
explain the selector. It reports a false positive, and any tool built this way
will do the same.

Treat the unexplained count as an upper bound that still needs review. It is
not a verdict.

## Attribution

```console
  attribution (overt evidence only):
    config on disk              claude
    commit trailers             claude=30 (93.8%)  of 32 commits
```

Both sources are overt, which means the agent declared them itself:

| Agent | Config on disk | Commit trailer |
| --- | --- | --- |
| Claude | `.claude/`, `CLAUDE.md`, `.mcp.json` | `Co-Authored-By: Claude`, `Generated with [Claude Code]` |
| Codex | `AGENTS.md`, `.agents/`, `.specify/`, `.codex/` | `Co-Authored-By: Codex` or `ChatGPT` |
| Copilot | `.github/copilot-instructions.md` | `Co-Authored-By: Copilot` |
| Cursor | `.cursor/`, `.cursorrules` | `Co-Authored-By: Cursor` |
| Gemini | `.gemini/`, `GEMINI.md` | none |
| Aider | `.aider.conf.yml`, `.aiderignore` | none |
| Devin | none | `Co-Authored-By: Devin` |

Neither source survives `rm -rf .claude` and a rebase. Attribution here shows
only that nobody cleaned up. It is not proof.

!!! note "A trailer count is not an authorship share"

    Several agents often work on the same repository, and some leave no trailer
    at all. See [Results](../experiment/baseline.md) for the measured counts.

The survey does not guess an agent from writing style or formatting habits. You
cannot prove such a guess wrong, so it is not evidence.

## What the survey cannot see

The survey reads codepoints. It cannot see a statistical watermark, which lives
in the model's choice of words and leaves no codepoint trace. A result of zero
does not mean a human wrote the text.

Every run ends with a "what this run could detect" block. It lists each
detection channel and its status, including the ones that are switched off. See
[What it means](../experiment/what-it-means.md) for the channels, and
[Limits and disclaimer](../disclaimer.md) for the full caveats.
