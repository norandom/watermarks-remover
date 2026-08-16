# Layer A benchmarks

Two metrics over the same catalogue. The second is the useful one.

- `benchmark.py` — **technique recall**: what fraction of published schemes are
  detected. Easy to read, and it weights an unbounded hole the same as a
  trickle.
- `capacity.py` — **residual channel capacity**: how many bits an adversary can
  still push through after cleaning. Measured, not estimated.

## Residual capacity, measured 2026-08-16

Each channel is a real codec. A maximal payload is encoded into 4 KB of
carrier-free ASCII prose, the cleaner runs, and whatever decodes back out is
counted.

```bash
python research/recall/capacity.py
python research/recall/capacity.py --json --host-kb 16
```

| Channel | pre b/KB | post b/KB | survives |
| --- | ---: | ---: | ---: |
| **Tag block behind a flag emoji** | 1535 | **1535** | **100%** |
| **Invisible non-`Cf` letters** | 728 | **728** | **100%** |
| **Braille pattern blank** | 128 | **128** | **100%** |
| Trailing-whitespace count | 14 | 14 | 100% |
| Space homoglyph | 128 | 0 | 0.2% |
| Zero-width binary | 728 | 0 | 0% |
| Tag block, bare | 1535 | 0 | 0% |
| Variation selectors | 6953 | 0 | 0% |
| Private-use area | 3070 | 0 | 0% |

**Total: 14,817 bits/KB before cleaning, 2,405 after — 16.2% survives.**

That is roughly **300 bytes of payload per kilobyte of host text**. Enough for
a URL, a session token or a run identifier in a single README, invisibly.

### What the metric changes

Technique recall says 85%, which sounds like a tool that mostly works.

Capacity says one hole carries **64% of everything that gets through**, and
that hole — the subdivision-flag exemption — is *unbounded by construction*.
Nothing checks the payload length or alphabet between `U+1F3F4` and `U+E007F`,
so an adversary sets the rate, not the host text.

A count ranked that equal with trailing-whitespace encoding at 14 b/KB, a
channel 100 times narrower. The capacity metric ranks the fix order by itself
instead of relying on someone noticing.

### Priority that falls out

1. **Bound the flag payload.** 64% of residual, and the fix is a length and
   alphabet check on a conforming 2–6 character subdivision code. Specified as
   `watermark-removal` task 2.4(b).
2. **Invisible non-`Cf` letters** — 30% of residual. `U+3164`, `U+FFA0`.
   Category `Lo`, so the category-based strip rule cannot see them.
3. **Braille blank** — 5%. Category `So`, same cause.
4. Everything else is rounding.

Items 2 and 3 share one root: the strip rule is *"Unicode general category
`Cf`"*, which is forward-compatible for format characters and blind to
invisible characters classified as letters or symbols. Closing them means
naming exceptions, which trades one failure mode for another and should be a
deliberate decision rather than a reflex.

## Technique recall

What fraction of published invisible-carrier techniques does this tool actually
catch? Answered with a number rather than a shrug.

**Measured 2026-08-16** against the shipped cleaner at `_vendor` commit
`fcebf53`.

```bash
python research/recall/benchmark.py            # table
python research/recall/benchmark.py --json     # machine-readable
python research/recall/benchmark.py --verbose  # leaked carriers per technique
```

## Result

| | |
| --- | --- |
| Techniques catalogued | 24 |
| In scope for Layer A | 20 |
| **Detection recall** | **17 / 20 (85.0%)** |
| Removal correct | 17 / 24 (70.8%) |
| Documented out-of-scope gaps | 4 |
| **Layer B recall** | **0 of 1 known scheme** |

Detection and removal are scored separately on purpose. They are different
questions, and a technique can be correctly detected while being correctly
*not* removed — private-use characters are the clearest case, since the
specification preserves them by default to protect icon-font glyphs.

## The three detection failures

These are genuine, and the benchmark flags them as unexpected rather than
quietly folding them into the denominator.

### 1. Tag block hidden behind a flag emoji — the serious one

An arbitrary payload placed between `U+1F3F4` and `U+E007F` is **neither
detected nor removed**. The subdivision-flag exemption accepts any length, so
the entire tag alphabet becomes available to an attacker who prefixes a flag.

This is an *active evasion*, not an accident. It defeats the scanner completely.
A conforming subdivision code is 2–6 characters from a restricted alphabet;
bounding the payload closes it. Specified as `watermark-removal` task 2.4(b).

### 2 and 3. Homoglyph substitution is not reported

Cyrillic `а` in `pаypаl.cоm` and fullwidth `ＡＢＣ` are invisible to
`inspect_text`, because confusable handling is gated behind the same
`aggressive_homoglyphs` flag that governs *removal*.

That coupling is the defect. Whether to rewrite a homoglyph is a policy
question with a real false-positive cost on multilingual source. Whether to
*tell you one is there* is not. A scanner should say "there is a Cyrillic
character in your hostname" and leave the rewrite decision to you.

**Detection and removal policy should be decoupled.** Not currently specified;
belongs in `provenance-survey`.

## Documented out-of-scope gaps

Recorded rather than silently missed. Each is a real technique this tool does
not cover, with the reason.

| Technique | Why not covered |
| --- | --- |
| Hangul filler `U+3164`, `U+FFA0` | category `Lo`, not `Cf` — renders as nothing but is a letter |
| Braille pattern blank `U+2800` | category `So` — renders as whitespace |
| Line/paragraph separator `U+2028`, `U+2029` | categories `Zl`/`Zp`; removal would alter layout |
| Trailing-whitespace count encoding | a whitespace *count*, not a codepoint — pair with a `trailing-whitespace` hook |

The first three share a cause: the strip rule is "Unicode general category
`Cf`", which is forward-compatible for format characters but blind to
invisible characters that are categorised as letters, symbols or separators.
Extending it means enumerating exceptions, which trades one failure mode for
another.

## Layer B

Zero of one known scheme, and this is not a shortfall in the implementation.

Claude's text watermark is statistical. No publicly available method detects
it: Anthropic states that detection documentation is forthcoming and has not
published a scheme or keys. Key recovery is a real research result
([Jovanović, Staab & Vechev, ICML 2024](https://proceedings.mlr.press/v235/jovanovic24a.html))
but works by **actively querying the watermarked API**, not by analysing an
existing corpus, and its headline capability is *spoofing* — falsely stamping
human text as machine-written — which is a worse hazard than scrubbing.

Passive analysis of text you already have recovers nothing. The green/red
partition is reseeded per token by a keyed hash, so there is no fixed direction
for a decomposition to find; that is the security definition, not an oversight.

## How to extend the catalogue

`techniques.py` holds one `Technique` per scheme: a construction, a payload,
and two independent expectations (`detect`, `remove`), plus a `residue` list
for codepoints that may legitimately survive and a `policy` for non-default
flags.

A technique naming a flag the shipped cleaner lacks — `strip_private_use`,
`strip_bom` — is describing target behaviour from the specification. The
benchmark reports it as `spec-only flag` rather than crashing or scoring it as
a pass.

Add a technique when you find one published. A rising catalogue with a falling
recall is the honest signal that the field has moved.
