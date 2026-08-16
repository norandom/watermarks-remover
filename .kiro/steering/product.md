# Product Overview

`wm-hook` is a pre-commit hook that strips **AI provenance marks from text
files** before they enter git history. It targets the invisible Unicode
carriers that survive copy/paste out of a chat UI, plus AI generator keys in
Markdown/Quarto YAML frontmatter.

It serves developers and technical writers who paste model output into
repositories and do not want undetectable metadata riding along in their
commits.

## Core Capabilities

- **Layer A Unicode cleaning** — removes invisible/format codepoints
  (zero-width family, Unicode Tag block, variation selectors, private-use
  areas, bidi overrides) and normalizes 16 space homoglyphs to `U+0020`.
- **Frontmatter provenance removal** — drops AI generator keys from YAML
  frontmatter in `.md`/`.markdown`/`.mdx`/`.qmd`.
- **Two symmetric modes** — validation (`--check`, read-only) and removal
  (rewrite in place). Same detection path; `--check` short-circuits the write.
- **Context-aware preservation** — invisible characters that are load-bearing
  (emoji glue, script joiners, complete flag sequences, same-script fillers,
  RTL marks) are kept. Only free-floating carriers are removed.
- **Refusal over corruption** — binary files are detected and skipped
  untouched; non-UTF-8 bytes round-trip byte-identically.

## Target Use Cases

- Commit-time autofix in a repository that accepts AI-assisted contributions.
- Read-only CI gate that fails a build when marks are present.
- One-shot CLI cleaning of a file or a file list.

## Value Proposition

**Lossless by construction.** Every transformation preserves the rendered
appearance of the text. The product deliberately refuses the lossy half of the
problem: statistical/token-sampling watermarks (SynthID-Text, green-list
biasing) would require a paraphrase model that rewrites the author's prose,
which has no place in a `git commit`.

The three watermark channels, and where this product sits:

| Channel | Carrier | In scope |
| --- | --- | --- |
| **A — format/edit-based** | Invisible or visually identical codepoints | ✅ yes |
| **B — statistical** | Which tokens the model chose | ❌ never |
| **C — metadata** | Declared provenance fields | ⚠️ frontmatter only |

Scope discipline is the product. Claiming Layer B coverage, or silently
rewording prose, would break the core promise.

---
_Focus on patterns and purpose, not exhaustive feature lists_
