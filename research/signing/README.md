# Signing text with an invisible signature

The mirror of the rest of this project. Everything else asks whether someone
hid data in your text. This asks whether you can put your own name in text so
that it survives copying and cannot be faked.

Measured 2026-08-16. Research code, not part of the hook.

## The trap that makes the obvious version useless

The obvious design is to hide a name or an ID in the text. It does not work.

If the mark is a fixed string, anyone who can read it can copy it. An invisible
"written by Marius" proves nothing, because I can paste the same bytes under
your paragraph. A mark that is not tied to the text it marks is not a
signature. It is a sticker.

So the payload has to be a signature over the text itself:

```
canonical(text)  ->  SHA-256  ->  Ed25519 sign  ->  72 bytes  ->  invisible
```

Two things follow. Moving the mark to different text breaks it, because the
hash no longer matches. Making a new valid mark needs the private key. Anyone
can check it with the public key.

## Cost

The signature is 72 bytes: 4 magic, 4 key id, 64 Ed25519 signature. Variation
selectors carry one byte each, so it costs 72 invisible codepoints.

| Encoding | Bits per codepoint | Codepoints needed |
| --- | ---: | ---: |
| Variation selectors | 8 | **72** |
| Tag block (ASCII only, so base64 first) | 7 | 96 |
| Zero-width binary | 1 | 576 |

Selectors win. The signature is one contiguous run, so it does not need long
text to fit. Length only changes how much of the document it is:

| Visible characters | Overhead |
| ---: | ---: |
| 286 (a short note) | 25.2% |
| 905 | 7.96% |
| 2,775 | 2.59% |
| 12,775 (a long document) | **0.56%** |

Signing does not change a single visible byte.

## What it survives

Every row is something a signed document plausibly passes through. Measured,
not assumed.

| Transformation | Verifies | Why it matters |
| --- | --- | --- |
| Untouched | yes | the control |
| CRLF line endings | yes | git autocrlf on a Windows checkout |
| Trailing whitespace stripped | yes | almost every editor on save |
| NFC normalisation | yes | the canonical form |
| NFD normalisation | yes | macOS filesystem round-trip |
| NFKC normalisation | yes | search indexes and form fields |
| Leading text added | **no** | content changed, must fail |
| One word changed | **no** | content changed, must fail |
| Any carrier cleaner | **no** | including this project's own hook |

The first six survive because the canonical form removes carriers, applies NFC,
and normalises line endings and trailing whitespace before hashing. NFKC
survives because it does not touch variation selectors.

The last three fail, and two of them are meant to. Changing the text must break
the signature; that is what binding it to the content buys.

## The limit

The last row is the real one. **Any cleaner removes the signature**, including
`wm-hook`. So the result is one-sided, pointing the opposite way to the
detector:

- A valid signature proves authorship.
- **No signature proves nothing at all**, because deleting one is trivial and
  leaves no trace that anything was deleted.

This is not steganography. Run this project's own detector on a signed file and
it says `carrier`, correctly, on the `run` and `byte_aligned` evidence. A
signature is meant to be invisible to a reader, not concealed from a scanner.
Anyone who looks will find it, and anyone who finds it can delete it.

That makes it useful for attribution among cooperating parties, and useless
against an adversary who does not want your name on the text.

## Use

```bash
uv run --with cryptography python research/signing/sign.py keygen
uv run --with cryptography python research/signing/sign.py sign notes.md
uv run --with cryptography python research/signing/sign.py verify notes.md
```

`keygen` writes `wm-key` and `wm-key.pub`. Publish the public key; the private
key signs. Reproduce the table above with:

```bash
uv run --with cryptography python research/signing/robustness.py
```

## Why this is not in the hook

Scope. The hook removes carriers from text and does nothing else, and adding a
signer would put writing and removing carriers in the same tool. It also needs
a non-stdlib dependency, which the hook does not have and should not gain.
