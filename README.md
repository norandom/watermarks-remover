# wm-hook

A pre-commit hook that strips **AI provenance marks from text files** — the
invisible Unicode carriers that survive copy/paste out of a chat window, plus
AI generator keys in Markdown/Quarto YAML frontmatter.

It runs at commit time, is lossless by construction, and never needs a model.

```console
$ wm-hook docs/notes.md
wm-hook: docs/notes.md: changed — cleaned (unicode removed=7 replaced=2; drop frontmatter key: generator)
```

---

## Table of contents

- [Why this exists](#why-this-exists)
- [Two modes: validate vs remove](#two-modes-validate-vs-remove)
- [Adopting it](#adopting-it)
- [Where it goes in your hook order](#where-it-goes-in-your-hook-order)
- [What it removes](#what-it-removes)
- [What it deliberately keeps](#what-it-deliberately-keeps)
- [What it does *not* remove](#what-it-does-not-remove)
- [Which files it touches](#which-files-it-touches)
- [Exit codes](#exit-codes)
- [Sharp edges to check before you adopt](#sharp-edges-to-check-before-you-adopt)
- [Configuration](#configuration)
- [Provenance and vendoring](#provenance-and-vendoring)
- [Spec-driven development](#spec-driven-development)
- [License](#license)

---

## Why this exists

Text watermarking splits into three unrelated channels. Confusing them is the
main reason people over- or under-estimate a tool like this.

| Channel | How the mark is carried | Detect by | Remove by | In scope here |
| --- | --- | --- | --- | --- |
| **A — Format / edit-based** | Codepoints that render as nothing, or as something visually identical to an ASCII character. Zero-width characters, the Unicode Tag block, variation selectors, homoglyph spaces, private-use glyphs. | Scanning codepoints. Deterministic — a hit is a hit. | Deleting the codepoints. **Lossless**: the rendered text is unchanged. | ✅ **yes** |
| **B — Statistical / token-sampling** | The mark is in *which words the model chose*. Green-list logit biasing (Kirchenbauer et al. 2023), Gumbel/exponential sampling (Aaronson), tournament sampling (SynthID-Text, Dathathri et al., *Nature* 2024). | A statistical test over the token sequence. Probabilistic — needs enough text. | Paraphrasing. Requires a model and **rewrites your prose**. | ❌ no — see below |
| **C — Metadata / provenance** | A declared field: C2PA Content Credentials, XMP, `docProps`, YAML frontmatter keys. | Parsing the container. | Deleting the field. | ⚠️ **frontmatter only** |

Layer A is the one that matters at commit time, because it is the one that
**travels invisibly**. You paste a paragraph from a chat UI into a docstring,
a commit message, a `README`, a `.po` translation — and a run of `U+200B`
comes with it. Nobody reviewing the diff can see it. It survives grep, it
survives most linters, and it lands in your repository history forever.

The concrete Layer A schemes this hook is aimed at:

- **Zero-width binary encoding** — `U+200B`/`U+200C`/`U+200D`/`U+FEFF` used as
  bits to spell out an arbitrary payload between visible characters.
- **Unicode Tag block smuggling** — `U+E0000`–`U+E007F` mirrors ASCII one-to-one
  and renders as nothing, so a whole readable string can be hidden inline.
- **Variation-selector smuggling** — `U+FE00`–`U+FE0F` plus `U+E0100`–`U+E01EF`
  give 256 invisible selectors, i.e. one arbitrary byte each, chained after any
  base character.
- **Homoglyph spaces** — `U+00A0`, `U+2009`, `U+202F` and friends substituted
  for plain `U+0020`, so the *choice of space character* carries the bits.
- **Private-use codepoints** — `U+E000`–`U+F8FF` has no assigned meaning, so it
  is a natural payload channel.
- **Bidi controls** — the same family behind Trojan Source
  (CVE-2021-42574), where source code renders differently than it compiles.

Layer B is deliberately out of scope. Removing a statistical watermark means
running a paraphrase model over your prose and accepting whatever it hands
back. That has no place in a `git commit`.

---

## Two modes: validate vs remove

Both exist. They are the same code path; `--check` short-circuits before the
write.

### Validate — report only, never writes

```console
$ wm-hook --check docs/*.md
wm-hook: docs/notes.md: changed — would clean (unicode removed=7 replaced=2; drop frontmatter key: generator)
$ echo $?
1
```

Nothing on disk is touched. Exit code `1` means "this file *would* change".
Use this in CI, or as a manual gate, when you want a build failure rather than
a silent rewrite.

### Remove — rewrite in place

```console
$ wm-hook docs/notes.md
wm-hook: docs/notes.md: changed — cleaned (unicode removed=7 replaced=2; drop frontmatter key: generator)
$ echo $?
1
```

The file is rewritten atomically (temp file in the same directory, then
`os.replace`). **No `.bak` is created — git is the backup.** The exit code is
still `1`, which is the pre-commit autofix convention: the commit fails, you
inspect the change, `git add` it, and commit again.

### As pre-commit hooks

Two hook ids ship in `.pre-commit-hooks.yaml`:

| Hook id | Mode | Runs |
| --- | --- | --- |
| `wm-hook` | remove (autofix) | every commit |
| `wm-hook-check` | validate only | `pre-commit run --hook-stage manual wm-hook-check` |

```yaml
repos:
  - repo: https://github.com/norandom/watermarks-remover
    rev: <tag>
    hooks:
      - id: wm-hook            # rewrites files, fails the commit
      - id: wm-hook-check      # manual stage: reports, never writes
```

Both ids declare their stages explicitly, which matters more than it looks: a
pre-commit hook with no `stages:` runs in *every* stage, so an autofix hook
left unpinned would also fire during a `--hook-stage manual` CI run and rewrite
the tree the gate was only meant to inspect. `wm-hook` is pinned to
`pre-commit` and `wm-hook-check` to `manual`.

Run the gate in CI with:

```console
pre-commit run --hook-stage manual wm-hook-check --all-files
```

If you want validate-only behaviour on commit instead of autofix, drop the
`wm-hook` entry and override the stage:

```yaml
      - id: wm-hook-check
        stages: [pre-commit]
```

---

## Adopting it

### Via pre-commit (recommended)

`language: python` means pre-commit builds the isolated environment itself.
Nothing needs to be preinstalled on the committer's machine beyond
`pre-commit`.

```yaml
repos:
  - repo: https://github.com/norandom/watermarks-remover
    rev: <tag>                 # pin a tag, not a branch
    hooks:
      - id: wm-hook
```

```console
pre-commit install
pre-commit run --all-files     # do this once before you adopt — see Sharp edges
```

That first `--all-files` run is not optional advice. It shows you the full
blast radius on your existing tree in one diff, before the hook starts
rewriting files under you one commit at a time.

### Standalone CLI

```console
uvx --from 'git+https://github.com/norandom/watermarks-remover@<tag>' wm-hook --help
pipx install 'git+https://github.com/norandom/watermarks-remover@<tag>'
```

```console
wm-hook --check path/to/file.md          # validate
wm-hook path/to/file.md other.py         # remove
wm-hook --version
```

The CLI takes one or more explicit file paths. It does not walk directories
and does not glob — pre-commit (or your shell) supplies the file list.

---

## Where it goes in your hook order

Short answer: **after anything that writes text, before anything that formats
it, and nowhere near last.**

That is deliberately not the intuitive answer, so here is the reasoning.

### The two mechanics that decide this

pre-commit runs hooks **sequentially in declared order**, and by default runs
*all* of them even after one fails. Each hook therefore sees the previous
hook's output. Two consequences follow:

1. **A hook that mutates bytes invalidates the work of every formatter before
   it.** If `wm-hook` removes a no-break space from a comment, that line gets
   shorter. A formatter that already ran can no longer vouch for the layout, so
   your *next* commit reformats it. You get perpetual churn between two hooks
   that each individually converge.
2. **A hook that writes new text after `wm-hook` defeats it entirely.** The
   guarantee is about the bytes that reach the commit. Anything authoring text
   downstream of the clean is unchecked.

Put together: `wm-hook` belongs in the **byte-normalisation** phase — late
enough to catch everything generated, early enough that formatters get the last
word on layout.

### The order

```yaml
repos:
  # 1. GENERATORS — anything that authors or rewrites text.
  #    Codegen, schema stubs, and agentic hooks belong here. wm-hook cannot
  #    clean output that is produced after it runs.
  - repo: local
    hooks:
      - id: codegen
      - id: agent-review          # if it *writes*; see the CI note below

  # 2. NORMALISERS — byte- and character-level cleanup. wm-hook lives here.
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: <tag>
    hooks:
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: mixed-line-ending
  - repo: https://github.com/norandom/watermarks-remover
    rev: <tag>
    hooks:
      - id: wm-hook
        exclude: '^(tests/fixtures/|locales/|assets/nerdfonts/)'

  # 3. FORMATTERS — they get the final say on layout, and they will not
  #    reintroduce invisible characters.
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: <tag>
    hooks:
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-prettier
    rev: <tag>
    hooks:
      - id: prettier

  # 4. LINTERS AND VALIDATORS — read-only, so they judge the final state.
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: <tag>
    hooks:
      - id: ruff
  - repo: https://github.com/Yelp/detect-secrets
    rev: <tag>
    hooks:
      - id: detect-secrets
```

### Why not last

Putting `wm-hook` after your formatters is the tempting choice — "clean the
final bytes" — and it is the one that causes churn. It also buys nothing:
formatters emit ASCII. `black`, `ruff format`, `gofmt`, `rustfmt` and
`prettier` do not insert zero-width characters, private-use glyphs or bidi
controls, so there is no threat downstream of them to catch.

### Why not first either

Running it before your generators means it cleans the previous commit's text
and misses everything produced in this one.

There is one genuine argument for going earlier: an invisible character inside
an identifier produces a baffling syntax error, and cleaning first gives your
linter a chance to say something sensible. That argument favours *before the
linters*, which the order above already satisfies.

### The agentic CI case specifically

If your agent writes code **in CI, after the commit**, then no pre-commit hook
ever sees its output. The gate has to exist wherever generated text enters, so
you need a second check in the pipeline:

```yaml
- run: <your agentic step>                                    # writes code
- run: pre-commit run --hook-stage manual wm-hook-check --all-files
- run: <tests>
```

Use `wm-hook-check` rather than the autofix hook in CI: a gate that silently
rewrites the tree it is judging tells you nothing, and if the agent is
reintroducing marks on every run you want that to be loud.

### Two ordering hazards

- **Do not set `fail_fast: true`** alongside autofix hooks. It stops at the
  first failure, so you fix one hook per commit attempt and `wm-hook` may never
  run at all.
- **`fix-byte-order-marker` and `wm-hook` disagree about the BOM.** `wm-hook`
  preserves a leading BOM where the format requires it; that hook removes it
  unconditionally. Whichever runs later wins. Pick one.

### The first run will fail a few times

Autofix hooks exit non-zero when they change something, and pre-commit leaves
the change unstaged. On a tree that has never been cleaned, expect to
`git add` and retry two or three times as each phase settles. Run
`pre-commit run --all-files` once up front and take it as one diff instead.

---

## What it removes

### 1. Invisible and format Unicode (all text files)

Deleted outright. Every one of these renders as nothing, so removing them
does not change how the text looks.

| Codepoints | What they are |
| --- | --- |
| `U+200B` `U+200C` `U+200D` `U+2060` `U+FEFF` | Zero-width space, non-joiner, joiner, word joiner, ZWNBSP/BOM |
| `U+E0001`, `U+E0020`–`U+E007F` | Unicode **Tag block** — an invisible mirror of ASCII |
| `U+FE00`–`U+FE0F`, `U+E0100`–`U+E01EF` | Variation selectors VS1–VS256 |
| `U+E000`–`U+F8FF`, `U+F0000`–`U+FFFFD`, `U+100000`–`U+10FFFD` | **Private Use Areas** (all three) |
| `U+202A` `U+202B` `U+202C` `U+202D` `U+202E` | Bidi embeddings and overrides (LRE/RLE/PDF/LRO/RLO) |
| `U+061C` `U+200E` `U+200F` `U+2066`–`U+2069` | Bidi marks and isolates — *see the preservation rules below* |
| `U+00AD` | Soft hyphen |
| `U+034F` | Combining grapheme joiner |
| `U+2061`–`U+2064` | Invisible math operators (function application, times, separator, plus) |
| `U+206A`–`U+206F` | Deprecated format controls (symmetric swapping, digit shapes) |
| `U+180B`–`U+180E` | Mongolian free variation selectors and vowel separator |
| `U+17B4` `U+17B5` | Khmer inherent vowels |
| `U+115F` `U+1160` | Hangul choseong/jungseong fillers |
| `U+FFF9`–`U+FFFB` | Interlinear annotation anchors |
| any other `Cf` | Catch-all: anything in Unicode general category **Format** that is not explicitly allowlisted |

That last row is the important one. The list above is not an enumeration the
tool is limited to — anything Unicode classifies as a format character is
removed by default, so new carriers are covered without a code change.

### 2. Space homoglyphs (all text files)

**Replaced** with a plain `U+0020`, not deleted:

`U+00A0` (no-break) · `U+1680` (Ogham) · `U+2000`–`U+200A` (en/em quad, en/em,
three-per-em, four-per-em, six-per-em, figure, punctuation, thin, hair) ·
`U+202F` (narrow no-break) · `U+205F` (medium mathematical) · `U+3000`
(ideographic)

Sixteen codepoints in total. This is the one transformation that is *visible*
in rendered output — see [Sharp edges](#sharp-edges-to-check-before-you-adopt).

### 3. AI keys in YAML frontmatter (`.md` `.markdown` `.mdx` `.qmd` only)

A top-level frontmatter key is dropped — along with its indented block or list
items — when **any** of these hold:

1. The key name is one of:
   `generator`, `ai`, `ai_generated`, `ai-generated`, `claude`, `anthropic`,
   `openai`, `gemini`, `synthid`, `c2pa`, `content_credentials`,
   `contentcredentials`, `provenance`, `digital_source_type`,
   `digitalsourcetype`, `created_with`, `createdwith`, `model`, `llm`
2. The key name matches
   `generator|ai[-_ ]?generated|claude|anthropic|openai|gemini|synthid|c2pa|content.?credential|provenance|digital.?source|aigc`
3. **The key's value matches that same regex.**

If every key in the block is dropped, the empty `---` block is removed too.

Rule 3 is a footgun. `title: Comparing Claude and Gemini` deletes your
**title**. See [Sharp edges](#sharp-edges-to-check-before-you-adopt).

---

## What it deliberately keeps

The cleaner is not a blunt "delete every invisible character" filter. Several
invisible codepoints are load-bearing, and stripping them corrupts real text.
These are preserved:

| Preserved | Condition |
| --- | --- |
| `U+200D` ZWJ as **emoji glue** | Between two emoji bases — `👨‍👩‍👧`, `❤️‍🔥` stay intact |
| `U+FE0E` `U+FE0F` text/emoji selectors | Directly after an emoji base — `⚖️` keeps its presentation |
| `U+E0020`–`U+E007F` tag chars | Only inside a **complete** subdivision-flag sequence: `U+1F3F4` … `U+E007F` (`🏴󠁧󠁢󠁳󠁣󠁴󠁿`). A free-floating tag char is contraband and gets deleted. |
| `U+200C` ZWNJ / `U+200D` ZWJ as **script joiners** | Between two letters of the same joining script — Persian `می‌روم`, Devanagari `क्‍ष` |
| Variation selectors after a **CJK ideograph** | `U+FE00`–`U+FE0D` and `U+E0100`+ select ideograph variants |
| Mongolian FVS, Khmer inherent vowels, Hangul jamo fillers | Only directly after a base letter of their own script |
| `U+200E` `U+200F` `U+061C` marks, `U+2066`–`U+2069` isolates | Always, by default — legitimate in mixed RTL/LTR prose |
| Paired `U+202A`/`U+202B` … `U+202C` | Only when properly balanced. Overrides (`U+202D`/`U+202E`) are **never** preserved. |
| `U+0600`–`U+0605` `U+06DD` `U+070F` `U+08E2` `U+110BD` `U+110CD` | Orthographic Arabic/Syriac/Kaithi format marks |

The pattern throughout: an invisible character is kept **only when it sits
directly after a base from its own script** and is therefore doing real work.
The same codepoint floating on its own is treated as a carrier and removed.

Also preserved, mechanically:

- **CRLF line endings** in the body of a file (but see the frontmatter caveat).
- **Absence of a trailing newline** — the hook does not add one.
- **Non-UTF-8 bytes.** Files are decoded with `surrogateescape` and re-encoded
  the same way, so a latin-1 file round-trips byte-identically. A latin-1
  `0xA0` is *not* treated as `U+00A0` and is left alone.

---

## What it does *not* remove

Be clear-eyed about this list before you claim a repository is "clean".

- **Statistical watermarks (Layer B).** SynthID-Text, green-list biasing,
  Gumbel sampling. Not detectable by scanning codepoints and not removable
  without paraphrasing. Out of scope by design.
- **Stylistic tells.** Em-dashes, curly quotes, "delve", rule-of-three
  sentence structure. These are not watermarks and the hook does not touch
  punctuation or wording.
- **Whitespace-count encoding.** Trailing spaces, double spaces between
  sentences, and blank-line runs can encode bits. The hook does not normalise
  space *runs* — only space *codepoints*. Pair it with a
  `trailing-whitespace` hook if you care.
- **Homoglyph letters.** Cyrillic `а` for Latin `a`, fullwidth `Ａ` for `A`.
  The vendored cleaner supports this behind an `aggressive_homoglyphs` flag,
  but **the hook does not enable it** — the false-positive risk on real
  multilingual source is too high.
- **NFKC normalisation.** Supported upstream, not enabled here.
- **Images, PDF, DOCX, ODT, SVG, HTML.** `wm-hook` is wired only to the
  plain-text and Markdown-frontmatter paths; binary files are detected by magic
  bytes and **skipped untouched**. The vendored modules already implement
  cleaning for all of these formats, and a separate `wm-clean` CLI to expose
  them is specified in `.kiro/specs/container-cleaning/` — deliberately kept out
  of the hook, because PDF cleaning is best-effort, needs subprocesses, and
  degrades silently without `exiftool`/`qpdf`. None of that belongs at commit
  time.
- **Git metadata.** Commit messages, author trailers and `Co-Authored-By`
  lines are not inspected. This is a `pre-commit` hook over file contents, not
  a `commit-msg` hook.

---

## Which files it touches

The hook ships an explicit extension list rather than `types: [text]`:

```
md markdown mdx qmd qml txt text py js ts jsx tsx css json yaml yml toml
csv rs go c h cpp hpp java rb sh sql xml cfg ini env tex bib rst
```

**This list under-reaches, and that is the single biggest practical weakness
of the hook.** In a test repository with one `U+200B` planted in each of ten
tracked text files, the shipped hook cleaned two — eight watermarks survived.
Unmatched formats include `.mjs`, `.cjs`, `.html`, `.ipynb`, `.po`, `.tf`,
`.Rmd`, and extensionless files such as `Dockerfile`.

Three things to know:

- The regex is **case-sensitive**. `README.MD` does not match.
- Only `.md`, `.markdown`, `.mdx` and `.qmd` get the frontmatter pass. Every
  other extension gets the Unicode pass only.
- The in-code rationale for avoiding `types: [text]` is partly wrong.
  `identify` *does* know `.qml` (→ `qml`, `text`), and it tags `.MD` as
  `markdown` where the regex misses it. What `identify` genuinely does not know
  is `.qmd` and `.Rmd` (both return no tags). So `types: [text]` plus a small
  `files:` union for Quarto/R Markdown would cover strictly more than the
  current list.

Until the list is widened, add the formats you care about in your own config:

```yaml
      - id: wm-hook
        files: \.(mjs|cjs|html|po|tf|ipynb|Rmd)$
```

Regardless of extension, a file whose bytes look binary is **skipped and never
modified**. Detection is by magic number (ZIP, PDF, PNG, JPEG, ELF, SQLite,
fonts, …), embedded NUL bytes, or a control-byte density above 5%.

---

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | Every file was already clean (or was skipped as binary) |
| `1` | At least one file was modified — or, under `--check`, would be |
| `2` | At least one file could not be read, written or stat'd |

Note that `0` covers "skipped as binary" as well as "clean". A skipped file is
reported on stderr but does not fail the run.

---

## Sharp edges to check before you adopt

This hook **rewrites source files automatically**. Run
`pre-commit run --all-files` once and read the diff before you trust it. These
are the cases that bite, ordered by how likely they are to hurt.

### 1. A frontmatter *value* mentioning a vendor deletes the whole key

```yaml
---
title: Comparing Claude and Gemini    # ← the entire title is deleted
author: Marius
---
```

Rule 3 in [What it removes](#what-it-removes) matches on the value, and the
action is to drop the key, not to sanitise it. Any frontmatter field whose
value legitimately names an AI vendor — a blog post title, a `description`, a
`tags` list — is silently destroyed. Likewise `model: linear` in a stats
write-up: `model` is an unconditional key match.

**Mitigation:** exclude your content directory, or run `wm-hook-check` instead
of the autofix hook on prose repositories.

### 2. Private-use codepoints are deleted unconditionally

Nerd Font and Powerline glyphs live in `U+E000`–`U+F8FF`. A shell prompt, a
`.zshrc`, or a README with icon glyphs loses them with no preservation rule
and no warning:

```
prompt  arrow   →   prompt  arrow
```

There is no allowlist for this. If your repository ships Nerd Font glyphs in
tracked text files, exclude those paths.

### 3. Space normalisation rewrites typography and data

`U+00A0` and `U+202F` are correct French typography (`Bonjour !`, `Prix :`),
and they are common in i18n JSON, `.po`-style catalogues and `.tex` sources.
The hook flattens all sixteen space homoglyphs to `U+0020` with no opt-out:

```json
{"fr": "Bonjour ! Prix : 10 €"}   →   {"fr": "Bonjour ! Prix : 10 €"}
```

The same applies to test fixtures that assert on exact bytes, and to CSV data
where a no-break space is a value rather than formatting.

### 4. CRLF Markdown gets its frontmatter reflowed to LF

A `.md`/`.qmd` file with CRLF line endings **and** YAML frontmatter is
rewritten even when it contains no AI marks at all:

```
'---\r\ntitle: Hi\r\n---\r\n\r\nbody\r\n'  →  '---\ntitle: Hi\n---\n\r\nbody\r\n'
```

The frontmatter block is rebuilt with `\n` joins while the body keeps its
CRLF, producing mixed line endings and a diff on every frontmatter line. It
converges after one pass, but the first run on a Windows-authored tree will
churn every Markdown file with frontmatter. Blank lines at the top or bottom
of a frontmatter block are stripped for the same reason.

### 5. It can take two commits to converge

The frontmatter pass runs *before* the Unicode pass, and it anchors on a
literal `---` at byte zero. So:

- A file with a **BOM** before `---` has no detectable frontmatter on pass 1.
  Pass 1 strips the BOM; pass 2 then finds and drops the AI keys.
- A key with a zero-width space inside it — `gene​rator:` — does not
  match the key regex on pass 1. Pass 1 strips the ZWSP; pass 2 drops the key.

Both cases mean: commit fails, you re-stage, commit fails *again*, you
re-stage, third commit succeeds. It is also a mild evasion path — a
single-pass CI check reports clean on input that a second pass would flag.

**Fix:** running `clean_text` before `clean_markdown` in `cli.py` resolves
both.

### 6. The POSIX executable bit is lost on rewrite

`safe_write_bytes` writes to a `mkstemp` file and `chmod`s it to
`0o666 & ~umask`, so a cleaned file comes back `0644`. The `files:` pattern
matches `.sh` and `.py`, which are frequently `0755`. Git tracks the execute
bit, so cleaning an executable script silently commits a `100755 → 100644`
mode change. Windows is unaffected.

### 7. Trojan Source is only partly mitigated

RLO/LRO overrides (`U+202D`/`U+202E`) are stripped, which is the classic
Trojan Source vector. But **bidi isolates survive** by default, and so do
properly paired `RLE … PDF` embeddings:

```
x = 1 /* ⁦ if (a) ⁩ */     →     unchanged
```

Do not treat this hook as a CVE-2021-42574 defence. Use a dedicated bidi
linter if that is your threat model. The vendored cleaner has a `strip_bidi`
flag, but the CLI does not expose it.

### 8. A no-break space at column 0 corrupts YAML *and* hides the mark forever

The worst case found. `U+00A0` is ordinary content in YAML, but `U+0020` is
structural indentation. Normalising one into the other at column 0 turns a
top-level key into a continuation line:

```yaml
---
title: My Post
 model: claude-opus-4     # parses fine before the hook
author: Bob
---
```

After one run the file is `\n model: claude-opus-4\n` — it **no longer
parses**, and because the frontmatter scanner skips any line starting with a
space, `model: claude-opus-4` is now invisible to the tool. The second run
reports `clean`, exit `0`. The provenance key survives permanently, in a file
that is now broken.

This affects plain `.yaml`/`.yml` too — no frontmatter and no adversary
required, since NBSP is what a browser copy-paste of rendered YAML produces.
Unlike edge 5, reordering the passes does **not** fix it: by then the line is
already indented.

### 9. Invisible characters that are load-bearing in non-Latin scripts

Three confirmed classes of real data loss:

- **Thai, Lao, Khmer, Myanmar** use `U+200B` as the word and line-break
  separator. It is deleted. `{"msg":"สวัสดี​ชาวโลก"}` loses its word boundary.
- **Persian, Urdu, Arabic** `U+200C` (ZWNJ) is preserved *only* between two
  same-script letters. At the end of a value, before punctuation, next to a
  digit, or before a newline the guard does not fire and the ZWNJ is deleted —
  exactly where it is orthographically required.
- **`U+3000`** (ideographic space) is normalised to ASCII, mutating CJK text in
  CSV, JSON and prose.

### 10. A leading `---` thematic break is parsed as frontmatter

A Markdown file that opens with a horizontal rule is treated as having a YAML
block. Blank lines, the rules themselves, and body prose between them are
deleted.

### 11. Several published carriers survive the default configuration

The hook is not a complete Layer A filter. Confirmed survivors:

- **Tag-char smuggling behind a flag emoji.** Any printable-ASCII payload
  hidden between `U+1F3F4` and `U+E007F` is accepted as a "complete flag
  sequence" and preserved in full, regardless of length or content.
- **ZWJ between ASCII digits, `#`, `*` and arrows.** These count as emoji
  bases, so `1‍2‍3` keeps its joiners — a working bit channel in code and data
  files that neither clean nor `--check` reports.
- **Runs of `U+180B`–`U+180D`.** The Mongolian guard tests the raw previous
  character, which may be another selector, so only one per run is removed and
  `--check` reports 1 hit for 40.
- **Orthographic Arabic/Syriac `Cf` marks** are kept unconditionally, giving an
  invisible multi-symbol channel even in plain ASCII files.
- **Homoglyph letters** (Cyrillic `а`, fullwidth `Ａ`) — deliberately off.

### 12. Symlinked files error out (but pre-commit shields you)

`safe_write_bytes` refuses to write through a symlink, so `clean_one` returns
`error — cannot write` and exit `2`. In practice pre-commit never passes
symlinks to hooks, so this only bites direct CLI use.

### 13. Diagnostics are counts, not codepoints

Output is `unicode removed=7 replaced=2`. It does not say *which* codepoints,
so `--check` tells you a file is dirty without telling you what is in it. The
vendored `inspect_text()` produces a full per-codepoint report with offsets and
confidence levels; the CLI does not surface it.

### 14. Other confirmed rough edges

- The **UTF-8 BOM is stripped from `.csv`, `.sql` and `.xml`**, where it is a
  required encoding signal rather than a watermark.
- **`U+FE0F` is stripped after ℹ️ ‼️ ⁉️ ⤴️ ⤵️** — five emoji bases missing from
  the base table — silently downgrading them to text presentation.
- **Oversize files are an error (exit 2), not a skip**, so one large file fails
  the whole run.
- **A tracked filename starting with `-`** is parsed as an option and aborts
  the run in argparse.
- **`pass_filenames: false`** makes the hook die with an argparse usage error
  rather than no-op.

---

## Configuration

There is no config file and there are no tuning flags. The CLI accepts exactly
`--check`, `--version` and a list of paths. The cleaning parameters are fixed
at the hook's defaults:

| Parameter | Value | Effect |
| --- | --- | --- |
| `normalize_spaces` | `True` | Space homoglyphs → `U+0020` |
| `aggressive_homoglyphs` | `False` | Cyrillic/fullwidth letters left alone |
| `nfkc` | `False` | No NFKC normalisation |
| `strip_emoji_glue` | `False` | Emoji sequences preserved |
| `strip_bidi` | `False` | Directional marks and paired embeddings preserved |

Two environment variables act as guardrails:

| Variable | Default | Effect |
| --- | --- | --- |
| `WATERMARKS_MAX_INPUT_BYTES` | `268435456` (256 MiB) | Files above this are refused with exit `2` |
| `WATERMARKS_MAX_STDIN_BYTES` | `67108864` (64 MiB) | Unused by this CLI (paths only) |

Scope the hook with pre-commit's own `files` / `exclude` keys:

```yaml
      - id: wm-hook
        exclude: '^(tests/fixtures/|locales/|assets/nerdfonts/)'
```

---

## Provenance and vendoring

The cleaning logic is **not written here**. `src/wm_hook/_vendor/` holds
byte-exact copies of `service/scripts/` from
[`guillaumemeyer/watermarks-remover`](https://github.com/guillaumemeyer/watermarks-remover),
pinned by commit SHA in `_vendor/VENDORED.json` with a SHA-256 per file.

```
src/wm_hook/
  cli.py                  ← the only original code: batch + commit plumbing
  _vendor/
    text_unicode.py       ← Layer A cleaner
    container_meta.py     ← frontmatter / container metadata
    common.py             ← safe atomic writes, binary sniffing
    image_meta.py         ← not called by the hook; container_meta imports from it
    VENDORED.json         ← upstream ref + per-file SHA-256
```

Never edit `_vendor/` in place. To take upstream changes: bump `PINNED_REF` in
`refresh.sh`, run it, review the per-file change summary, test, commit.

```console
./refresh.sh            # fetch at PINNED_REF, rewrite VENDORED.json
./refresh.sh --check    # verify no drift against VENDORED.json (offline)
```

`refresh.sh --check` is worth wiring into CI — nothing currently enforces that
the vendored files still match their recorded hashes.

`cli.py` reaches the vendored modules by inserting `_vendor/` at the front of
`sys.path` at import time, so they import each other by bare name
(`from common import ...`) exactly as they do upstream. Two consequences worth
knowing: the very generic module name `common` shadows any other `common` for
the whole process, and importing `common` reconfigures the process's
stdin/stdout/stderr to UTF-8 as a side effect.

## Spec-driven development

This repository follows spec-driven development. Behaviour is defined in
`.kiro/` before it is implemented, and the sharp edges listed above are tracked
there as numbered requirements rather than as prose.

```
.kiro/
  steering/                     persistent project memory
    product.md                  what this is, and the three watermark channels
    tech.md                     stack, the vendoring rule, safety invariants
    structure.md                organization patterns and naming
  specs/
    watermark-removal/          the rewrite path
    watermark-detection/        the read-only path, hook wiring, CI gating
    container-cleaning/         wm-clean: DOCX, PDF, SVG, ODT, HTML, images
```

The specs split along the boundaries an adopter actually cares about:

| Spec | Owns | Phase |
| --- | --- | --- |
| `watermark-removal` | What is deleted, replaced and preserved; byte-level fidelity; single-pass convergence; write safety and file metadata; opt-out controls | tasks |
| `watermark-detection` | Read-only guarantee; finding granularity and confidence; machine-readable output; exit-code semantics; hook ids and stages; file-selection coverage | tasks |
| `container-cleaning` | `wm-clean`: format routing, document and image metadata removal, degraded-mode honesty, safe output handling | requirements |

Each spec carries `requirements.md`, `research.md`, `design.md` and `tasks.md`,
gated by the approval flags in its `spec.json`. Both are at `tasks-generated`
and `ready_for_implementation`: 106 EARS acceptance criteria, every one traced
to a design component and to at least one task.

The central architectural decision is recorded in
`watermark-removal/research.md`: **vendor the data, own the policy.** Most
confirmed defects live inside `_vendor/`, which is byte-exact and uneditable, so
the corrections go into an owned layer that consumes the vendored *codepoint
tables* while replacing the vendored *decision logic*. A divergence conformance
test records every intentional disagreement, so an upstream refresh that changes
semantics fails loudly instead of silently.

Requirements describe **corrected** behaviour, not current behaviour. Where the
shipped code contradicts a requirement, that gap is a defect with a
reproduction, not a spec error — see
[Sharp edges](#sharp-edges-to-check-before-you-adopt).

## License

MIT. See [LICENSE](LICENSE). The vendored files carry upstream's licensing —
check `guillaumemeyer/watermarks-remover` before redistributing.
