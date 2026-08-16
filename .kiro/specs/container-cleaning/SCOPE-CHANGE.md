# Scope change: images removed

**2026-08-16.** Images and all pixel-domain work are **out of scope for this
project**. This spec is retained but reduced to document containers only.

## What was removed

- PNG, JPEG, WebP, AVIF and HEIC metadata stripping
- C2PA and JUMBF manifest handling in images
- SynthID pixel scoring
- CtrlRegen and MarkDiffusion pixel-domain removal
- The deferred `pixel-watermark-removal` follow-on spec

Requirement 3 of `requirements.md` is void. Requirement 1's format routing
covers document containers only. Requirement 7's per-format fixtures no longer
include image formats.

## Why

The project's interest is **text and Unicode carriers**. Images are a different
medium with different tooling, different failure modes and, unlike text, a
mature and already-solved metadata story. Carrying them widened the surface
without serving the question the project exists to answer.

Upstream's image support remains available for anyone who needs it; nothing
here forecloses using it directly.

## What this spec still covers

Document containers whose payload is text: SVG, PDF, DOCX, ODT, HTML. These
stay in scope because their bodies contain the same Layer A carriers the text
path handles, and because their metadata is a declared-provenance channel
directly comparable to Markdown frontmatter.

Their status is unchanged: **requirements only, not started, not scheduled.**
The active work is text.
