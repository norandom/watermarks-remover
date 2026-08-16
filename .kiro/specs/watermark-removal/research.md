# Research & Design Decisions

## Summary

- **Feature**: `watermark-removal`
- **Discovery Scope**: Extension (brownfield; the rewrite path already ships)
- **Key Findings**:
  - The defects are **not** distributed evenly. Almost all of them reduce to
    one missing capability: the cleaner has no idea *where in the file* a
    character sits. Position-blindness explains the YAML column-0 corruption,
    the CRLF frontmatter churn, the thematic-break destruction, and the
    two-pass non-convergence.
  - The second cluster is **classification policy**, not mechanism: private-use
    deletion, Thai `U+200B`, Persian ZWNJ at edge positions, digits counting as
    emoji bases, Mongolian FVS runs, and tag-char smuggling behind a flag are
    all single decisions inside one function, `_decide()`.
  - The vendoring rule and the fix list are in direct conflict. Most
    corrections live inside `_vendor/`, which is byte-exact and uneditable.
    Resolving that conflict is the central architectural question of this
    design.

## Research Log

### Where do the defects actually live?

- **Context**: The steering rule forbids editing `_vendor/`. Before choosing an
  architecture, establish how much of the fix list is even reachable from
  `cli.py`.
- **Sources Consulted**: `src/wm_hook/cli.py`, `_vendor/text_unicode.py`,
  `_vendor/container_meta.py`, `_vendor/common.py`; 21 adversarially confirmed
  findings with reproductions.
- **Findings**: Of the confirmed defects, roughly one in five is fixable in
  `cli.py` alone (pass ordering, exit-code treatment of oversize files, argv
  handling). The rest sit inside vendored functions:
  - `_decide()` — PUA, VS16 base gaps, digit/`#`/`*` as emoji bases, Mongolian
    FVS run masking, orthographic `Cf` channel, script-joiner edge positions.
  - `_valid_flag_tag_indices()` — unbounded tag payload after `U+1F3F4`.
  - `clean_markdown()` — value-hit key deletion, LF rebuild, thematic break,
    blank-line stripping.
  - `safe_write_bytes()` — executable-bit loss.
- **Implications**: A `cli.py`-only strategy cannot satisfy Requirements 3, 4,
  5 or 8. The design must either fork, upstream, or interpose.

### Is the NBSP column-0 defect really unfixable by reordering?

- **Context**: Several defects converge after a second pass, so pass ordering
  was the cheap candidate fix. This one reportedly does not.
- **Findings**: Confirmed by execution in both orderings and over three passes.
  Replacing `U+00A0` with `U+0020` at column 0 converts a top-level YAML key
  into a continuation line. Once indented, the frontmatter scanner skips the
  line permanently, so the provenance key is retained *and* the file no longer
  parses. Both orderings terminate in that state; a subsequent `--check`
  reports clean.
- **Implications**: This is the proof that ordering is not an architecture. The
  transformation must be **position-aware**, not merely sequenced. Elevated to
  the primary driver of the design.

### Can the vendored data tables be reused without the vendored policy?

- **Context**: If the classifier must be owned locally, does anything of value
  remain in `_vendor/text_unicode.py`?
- **Findings**: The module divides cleanly. The **data** — `STRIP_CODEPOINTS`,
  `SPACE_HOMOGLYPHS`, `_ORTHOGRAPHIC_CF`, `_VS_SUPPLEMENT`, the bidi and
  script-glue sets — is a curated Unicode inventory that genuinely benefits from
  upstream maintenance. The **policy** — `_decide()` and its helpers — is where
  every classification defect lives. The tables are plain module-level
  constants with no behavioural coupling.
- **Implications**: Vendor the data, own the policy. This preserves the value of
  `refresh.sh` (new codepoints flow in) while making the defective decisions
  local, testable and reviewable.

### Does `inspect_text` / `clean_text` symmetry survive an owned classifier?

- **Context**: `structure.md` records "one decision function" as a load-bearing
  invariant: detection and removal must never disagree.
- **Findings**: The invariant is a property of *having a single classifier*, not
  of that classifier being upstream's. Reimplementing it locally preserves the
  property provided both local callers use the local classifier.
- **Implications**: The `watermark-detection` spec must consume the same
  classifier. Recorded as a cross-spec revalidation trigger.

### Validating the central bet before implementation

- **Context**: The whole design rests on "the vendored tables are plain data and
  can be consumed without the vendored policy". If that is false, all twenty
  tasks are built on sand. Measured rather than assumed.
- **Findings**:
  1. **All fifteen tables are immutable plain data** — frozensets, dicts, a
     `range`, and one compiled pattern. Consuming them as constants works.
  2. **`text_unicode` is completely standalone and side-effect free.** It
     imports only stdlib and mutates nothing. The classifier's entire table
     dependency is free.
  3. **`container_meta` is not.** Importing it for two constants drags in
     `image_meta` *and* `common`, and mutates process stdio from the console
     codec to UTF-8 as a side effect. Three modules and a global mutation for a
     19-item frozenset and one regex.
  4. **The tables are not the whole inventory.** Fourteen helper predicates
     (`_is_private_use`, `_is_emoji_base`, `_is_cjk_ideograph`,
     `_joining_script`, `_is_hangul_jamo`, `_is_mongolian_base`, …) hold
     hardcoded ranges in code, plus seven inline literals inside `_decide`
     itself. These do **not** flow in through `refresh.sh`.
  5. **The divergence conformance test is constructible.** `_decide` is
     directly callable with a synthetic context, so enumerating
     codepoint-in-context disagreements is straightforward.
  6. **No region or column concept exists upstream.** `clean_markdown` takes
     only text and `_FM_RE` anchors on `\A---`. The segmentation component is
     genuinely new, not a reimplementation.
- **Implications**: The bet holds, with two corrections to how it was stated.
  - The frontmatter key vocabulary should be **re-declared locally**, not
    imported. The design already has to split it into unconditional and
    ambiguous sets for Requirement 5.3, so nothing is lost, and a drift test
    against the vendored values (imported in tests only, where the stdio side
    effect is harmless) catches upstream additions.
  - The claim "upstream table updates flow in automatically" is true only for
    the fifteen constants, not for the range predicates. Fortunately the
    defective ranges — the emoji base set, the Mongolian base range, the
    private-use test — are precisely the ones being replaced, so the loss is
    theoretical rather than practical. Recorded so nobody later assumes a
    refresh will fix a range bug.

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Verdict |
|--------|-------------|-----------|---------------------|---------|
| Fork `_vendor/` | Edit the vendored files directly | Simplest diff; every fix reachable | Destroys the vendoring rule and `refresh.sh --check`; upstream drift becomes unmergeable; contradicts steering | Rejected |
| `cli.py` compensation only | Pre/post-process around the vendored calls | Preserves byte-exactness perfectly | Cannot reach `_decide()`; fails Requirements 3, 4, 5, 8 | Rejected |
| Upstream the fixes | Patch `guillaumemeyer/watermarks-remover`, bump `PINNED_REF` | Correct long-term home; benefits everyone | Blocked on an external maintainer with unknown latency; cannot be a plan of record | Adopted as a **parallel** track, not the mechanism |
| Monkeypatch `_decide` at import | Rebind the vendored symbol at runtime | Small code footprint | Invisible coupling to a private function; silently breaks on refresh; untestable divergence | Rejected |
| **Vendor the data, own the policy** | Local classifier and frontmatter parser built on the vendored constant tables; local atomic writer | Every defect reachable; `_vendor/` stays byte-exact; upstream table updates still flow; divergence is explicit and testable | Duplicates ~200 lines of decision logic; divergence from upstream must be actively managed | **Selected** |

## Design Decisions

### Decision: Vendor the data, own the policy

- **Context**: Requirements 3, 4, 5 and 8 are unreachable without changing
  behaviour that lives inside byte-exact vendored files.
- **Alternatives Considered**: see the table above.
- **Selected Approach**: Introduce an owned policy layer in `src/wm_hook/`
  (`classify.py`, `frontmatter.py`, `atomic.py`, `policy.py`). It imports the
  **constant tables** from `_vendor/text_unicode.py` and
  `_vendor/container_meta.py` but not their decision functions. `_vendor/`
  remains byte-exact and `refresh.sh --check` continues to pass unchanged.
- **Rationale**: Puts each correction where it can be tested, keeps the
  upstream Unicode inventory flowing in, and turns an unmanaged conflict
  (steering rule vs. defect list) into an explicit, auditable divergence.
- **Trade-offs**: The repository gains real logic it must now maintain, so
  `structure.md`'s "one original file" description no longer holds. Accepted:
  the alternative is shipping known data-loss defects.
- **Follow-up**: A **divergence conformance test** enumerates every
  codepoint-in-context where the local classifier disagrees with the vendored
  `_decide()`, and asserts the set equals a recorded, justified list. An
  upstream refresh that changes semantics then fails loudly instead of silently.

### Decision: A single position-aware pass replaces two sequential passes

- **Context**: Requirements 4.1–4.3, 5.4, 5.6, 6.1 and 7.1–7.4 are all
  consequences of the cleaner not knowing where a character sits.
- **Alternatives Considered**:
  1. Reorder the existing passes — proven insufficient for the NBSP case.
  2. Loop to a fixpoint — converges, but masks the bug, multiplies cost, and
     still corrupts YAML.
- **Selected Approach**: Segment the document once into regions
  (`frontmatter-delimiter`, `frontmatter-body`, `document-body`), tolerating a
  leading BOM and invisible characters when locating the delimiters. Classify
  every character with its region and column known.
- **Rationale**: One mechanism resolves an entire cluster of requirements, and
  single-pass convergence becomes a structural property rather than a retry.
- **Trade-offs**: Region detection must be right; a misdetected region is a new
  class of bug. Mitigated by making region detection a separately tested unit.
- **Follow-up**: Distinguish a frontmatter delimiter from a thematic break
  (Requirement 5.4) inside region detection, not in the key scanner.

### Decision: Risky transforms become independently disableable, defaults unchanged

- **Context**: Requirement 9. Space normalization and private-use removal have
  legitimate false positives that no context rule fully resolves.
- **Selected Approach**: A single `CleanPolicy` value object carries one flag
  per risky transform, threaded through the classifier. Defaults preserve
  today's behaviour except where a requirement mandates a change (private-use
  preservation flips to on by default per Requirement 3.5).
- **Rationale**: Lets adopters keep the hook instead of excluding directories,
  and gives the detection spec something concrete to report against.
- **Trade-offs**: Configuration surface grows; mitigated by keeping it to a
  flat, documented set with no config file in this spec's scope.

### Decision: Own the atomic write to preserve file mode

- **Context**: Requirement 8.1. `_vendor/common.py:safe_write_bytes` chmods to
  `0o666 & ~umask`, discarding the executable bit that git tracks.
- **Selected Approach**: A local `atomic.py` that stats the original, writes via
  a same-directory temporary file, restores the original mode, and `os.replace`s
  into position — retaining the vendored symlink refusal and fsync behaviour.
- **Rationale**: Small, self-contained, and the only way to satisfy 8.1 without
  editing `_vendor/`.
- **Trade-offs**: Duplicates roughly 30 lines. Acceptable for a correctness fix
  on the write path.

## Risks & Mitigations

- **Divergence drift** — the local classifier and upstream silently grow apart.
  *Mitigation*: the divergence conformance test; `refresh.sh --check` in CI.
- **Region misdetection** — a bug here corrupts files that previously survived.
  *Mitigation*: region detection is a separately tested unit with a corpus of
  frontmatter, thematic-break, BOM and CRLF variants; every case asserts
  byte-identical output when no marks are present.
- **Scope creep into detection** — reporting requirements are tempting to solve
  here. *Mitigation*: the classifier returns structured decisions; formatting
  and exit codes stay in the detection spec.
- **Behaviour change surprises adopters** — private-use preservation and
  scoped space normalization change what the hook does.
  *Mitigation*: documented in the README's sharp-edges section and gated behind
  a version bump.
- **Maintenance burden grows** — the repository now owns real logic.
  *Mitigation*: `structure.md` must be re-synced after implementation.

## References

- `.kiro/steering/tech.md` — the vendoring rule and safety invariants.
- `.kiro/steering/structure.md` — the "one decision function" invariant.
- `src/wm_hook/_vendor/VENDORED.json` — pinned upstream ref and per-file hashes.
- Boucher & Anderson, *Trojan Source* (CVE-2021-42574) — bidi handling context.
- Kirchenbauer et al. (2023); Dathathri et al., *Nature* (2024) — Layer B
  background establishing why it stays out of scope.
