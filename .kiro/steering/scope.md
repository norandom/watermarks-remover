# Scope: text and Unicode carriers, nothing else

**Settled 2026-08-16.** One channel, done properly.

## In scope

Layer A invisible-Unicode carriers in text files. Detecting them, measuring
them, and removing them losslessly.

That is the whole of it.

## Out of scope, and removed

| Removed | Why |
| --- | --- |
| Images, C2PA manifests, pixel-domain work | different medium, different tooling. Upstream does it better |
| Container metadata: SVG, PDF, DOCX, ODT, HTML | documents, not text files; PDF cleaning is best-effort and needs subprocesses |
| **YAML frontmatter key removal** | provenance *metadata*, a different channel from a text carrier |
| Stylometry and writing-style analysis | measures register, not authorship; it is the humanizer's problem |
| Layer B statistical watermarks | keyed and undetectable; removal requires paraphrase, which destroys the prose |

## Why frontmatter went, specifically

It is the removal that will surprise someone reading old documentation, so the
reasoning is recorded rather than assumed.

Frontmatter key removal answered a different question. A zero-width character
is *hidden material in your text*; a `generator:` key is a *declared field*.
Removing the first cannot change what the text says, which is the guarantee
this tool is built on. Removing the second deletes content the author wrote.

And it was the worst code in the project. Three of the most serious defects
found were all in that feature:

- a value merely mentioning a vendor deleted the whole key, so
  `title: Comparing Claude and Gemini` lost its title;
- CRLF blocks were rebuilt with line feeds, rewriting mark-free files;
- a leading `---` thematic break was eaten as a frontmatter delimiter,
  deleting body prose.

Deleting the feature resolved all three, and voided Requirement 5 and task 2.5
with them. That is a better outcome than fixing them would have been.

**Frontmatter *recognition* stays.** `regions.py` still locates the block,
because a space homoglyph at the start of a YAML line is structurally
significant and replacing it changes how the file parses. Knowing where the
frontmatter is protects text; cleaning its keys was a different job.

## What "focus" bought

| | Before | After |
| --- | ---: | ---: |
| Modules in `core/` | 4 (3737 lines) | 3 (~1100) |
| Residual covert-channel capacity | 2405 b/KB | **142 b/KB** |
| Layer A detection recall | 85% | **100%** |

The correlation is not accidental. Every hour not spent on PDF metadata was an
hour spent measuring the one channel this tool claims, and the two fixes that
closed 94% of the residual capacity were both found by looking harder at text.

## The test for a future addition

Does it change what invisible material is in the text, and can it be removed
without changing what the text says?

If no, it belongs somewhere else.
