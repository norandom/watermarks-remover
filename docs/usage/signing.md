# Sign your own text

The rest of this tool removes marks that someone else left. `--sign` adds one
of yours.

The mark is invisible to a reader. It does not change a single visible
character. Anyone can still find it with a scanner, and anyone can delete it.

## Two modes, and the difference matters

| Command | What you get |
| --- | --- |
| `wm-hook --sign "name" FILE` | A label. Anyone who reads it can copy it. |
| `wm-hook --sign "name" --key FILE.key FILE` | A label tied to this exact text. |

A label on its own is a sticker, not a signature. If the mark is a fixed
string, anyone who reads it can paste it under their own paragraph. The tool
says so after an unkeyed run:

```text
This is a label, not proof. Anyone who reads it can copy it onto
other text. Pass --key to bind it to this text's content.
```

With a key, the mark includes an HMAC over the text. Copying it to other text
fails. Editing the text fails. Making a new valid one needs the key.

## Worked example

Make a key first. Keep it secret.

```console
$ wm-hook --keygen ~/.wm.key .
wrote a new key to ~/.wm.key. Keep it secret: anyone holding
it can produce marks indistinguishable from yours.
```

Sign a file:

```console
$ wm-hook --sign "Marius Ciepluch" --key ~/.wm.key report.md
signed  report.md  (51 invisible characters added)

Bound to the text. Editing the text invalidates the mark.
Any carrier cleaner removes it, including this tool. Do not run
wm-hook without --sign over a signed file, and exclude signed files
from the pre-commit hook.
```

Check it:

```console
$ wm-hook --verify --key ~/.wm.key report.md
VALID    report.md: 'Marius Ciepluch'
         valid: this key signed this exact text
```

Change one word, then check again:

```console
$ wm-hook --verify --key ~/.wm.key report.md
INVALID  report.md: 'Marius Ciepluch'
         MAC does not match. Either the text was changed after signing, the
         mark was copied from other text, or a different key made it.
```

## Other people can read your name

The label sits in the Unicode tag block, which mirrors ASCII. So anyone running
plain `--detect` sees it, without knowing this feature exists:

```console
$ wm-hook --detect report.md
1 file(s) scanned

      1  payload  hidden data found, and it can be read

Files with hidden data:
  report.md  reads: 'wm1:Marius Ciepluch'
```

That is on purpose. A mark nobody can read attributes nothing.

## What survives

The signature is checked against a canonical form of your text. Carriers are
removed first, so a signature never signs itself. Then Unicode NFC, line
endings, and trailing whitespace are normalised.

| Change | Still valid |
| --- | --- |
| CRLF line endings, from a Windows git checkout | yes |
| Trailing whitespace stripped by your editor | yes |
| NFC, NFD or NFKC normalisation | yes |
| Any word in the text changed | **no** |
| Mark copied onto different text | **no** |
| A different key | **no** |
| Any carrier cleaner, including `wm-hook` | **no** |

## The limit

This is the mirror of [what a detection result means](../experiment/what-it-means.md):

- A valid mark **proves** the key holder signed this exact text.
- A missing mark **proves nothing**. Removing one is trivial and leaves no
  trace that anything was there.

So it is useful between people who want the attribution to work. It is useless
against someone who does not want your name on the text.

!!! warning "Your own pre-commit hook will strip these"

    `wm-hook` without `--sign` removes invisible characters, and a signature is
    made of invisible characters. If you sign files in a repository that runs
    the hook, add them to the hook's `exclude` pattern.

## HMAC, not public-key

The mark uses HMAC-SHA256 from the Python standard library. The hook ships with
zero runtime dependencies, and that promise is checked in the release pipeline,
so a public-key library is not available here.

The cost is real. HMAC means the checker needs the same secret key. It proves
"made by someone holding this key". It cannot prove "made by Marius" to a
stranger who only has a public key.

If you need that, `research/signing/` has an Ed25519 version. It is research
code, it needs the `cryptography` package, and it is not part of the hook.

## Rules the tool enforces

- Labels must be printable ASCII, at most 120 characters. The tag block mirrors
  ASCII only, so an accented name would be corrupted rather than stored.
- A file can only be signed once. Sign again and it refuses.
- `--keygen` refuses to overwrite an existing key. Overwriting one would stop
  everything already signed with it from verifying, and you would not find out
  until you tried.
- Keys are written readable only by you, where the platform supports it.
