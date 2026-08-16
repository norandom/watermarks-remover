"""Put your own name in text, invisibly.

The mirror of the rest of the tool. Everything else removes marks somebody else
left; this adds one of your own.

Two modes, and the difference between them is the whole point:

    unkeyed    a label. Invisible, readable by anyone who looks, and copyable
               by anyone who reads it. Useful for marking your own drafts.
               It is NOT proof of authorship and the tool says so.

    keyed      the label plus an HMAC over the text. Moving it to different
               text breaks it, and editing the text breaks it. Making a new
               valid one needs the key.

A label on its own is a sticker, not a signature. If the mark is a fixed
string, anyone who can read it can paste it under their own paragraph. Binding
it to a hash of the text is what turns it into evidence.

Stdlib only: HMAC-SHA256, because the hook's zero-dependency guarantee is
adopter-visible and gated in CI. HMAC means the verifier needs the same secret,
so this proves "made by someone holding this key", not "made by this named
person" to a stranger. For public verification with Ed25519 see
research/signing/, which is allowed a dependency.

Layout. The label goes in the Unicode tag block, which mirrors ASCII, so
``wm-hook --detect`` decodes and shows it without knowing anything about
signing. The MAC goes in variation selectors, one byte each.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from wm_hook.carriers import carrier_class

PREFIX = "wm1:"
MAC_LEN = 32
KEY_LEN = 32
MAX_LABEL = 120


class SigningError(ValueError):
    """A signing or verification request that cannot be honoured."""


# ---------------------------------------------------------------------------
# What gets signed
# ---------------------------------------------------------------------------

def canonical(text: str) -> bytes:
    """The bytes a MAC covers.

    Carriers are removed first, so a signature never signs itself and a fixed
    point exists. Then NFC, line endings and trailing whitespace, so that an
    editor on save, a git checkout with autocrlf, or a decomposed accent from
    another operating system are not mistaken for tampering. Everything else
    counts: changing a word must break the mark.
    """
    stripped = "".join(c for c in text if carrier_class(ord(c)) is None)
    stripped = unicodedata.normalize("NFC", stripped)
    lines = [ln.rstrip() for ln in stripped.replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip().encode("utf-8")


def _mac(key: bytes, text: str, label: str) -> bytes:
    return hmac.new(
        key, canonical(text) + b"\x00" + label.encode("utf-8"), hashlib.sha256
    ).digest()


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------

def _to_tags(s: str) -> str:
    return "".join(chr(0xE0000 + ord(c)) for c in s)


def _from_tags(s: str) -> str:
    return "".join(chr(ord(c) - 0xE0000) for c in s)


def _to_selectors(data: bytes) -> str:
    return "".join(chr(0xFE00 + b) if b < 16 else chr(0xE0100 + b - 16) for b in data)


def _selector_byte(ch: str) -> int | None:
    cp = ord(ch)
    if 0xFE00 <= cp <= 0xFE0F:
        return cp - 0xFE00
    if 0xE0100 <= cp <= 0xE01EF:
        return cp - 0xE0100 + 16
    return None


def _is_tag(ch: str) -> bool:
    return 0xE0000 <= ord(ch) <= 0xE007F


def keygen() -> bytes:
    return secrets.token_bytes(KEY_LEN)


def write_key(path: Path) -> None:
    """Write a new key, refusing to clobber an existing one.

    ``common.safe_write_bytes`` is deliberately not used here: it chmods to
    ``0o666 & ~umask`` so that cleaned files keep ordinary permissions, which
    is right for documents and wrong for a secret.

    O_EXCL matters more than the mode does. Overwriting a key silently destroys
    the ability to verify everything already signed with the old one, and the
    damage is invisible until someone tries.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):  # Windows
        flags |= os.O_BINARY
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        raise SigningError(
            f"{path} already exists. Refusing to overwrite a key: everything "
            f"signed with the old one would stop verifying."
        ) from None
    with os.fdopen(fd, "wb") as handle:
        handle.write(keygen())


# ---------------------------------------------------------------------------
# Sign
# ---------------------------------------------------------------------------

def sign(text: str, label: str, key: bytes | None = None) -> str:
    """Return ``text`` with an invisible label, optionally bound by a MAC."""
    label = label.strip()
    if not label:
        raise SigningError("the label is empty")
    if len(label) > MAX_LABEL:
        raise SigningError(f"label is longer than {MAX_LABEL} characters")
    if not label.isprintable() or not label.isascii():
        # The tag block mirrors ASCII and nothing else. Refusing is better than
        # silently mangling a name with an accent in it.
        raise SigningError("label must be printable ASCII")
    if find(text)[0] is not None:
        raise SigningError("this text is already signed; remove the old mark first")

    payload = _to_tags(PREFIX + label)
    if key is not None:
        payload += _to_selectors(_mac(key, text, label))
    body = text.rstrip("\n")
    tail = text[len(body):] or "\n"
    return body + payload + tail


# ---------------------------------------------------------------------------
# Find and verify
# ---------------------------------------------------------------------------

def find(text: str) -> tuple[str | None, bytes | None]:
    """The embedded label and MAC, if any."""
    label = None
    mac = None
    run: list[str] = []
    for ch in text + "\x00":
        if _is_tag(ch):
            run.append(ch)
            continue
        if run:
            decoded = _from_tags("".join(run))
            if decoded.startswith(PREFIX):
                label = decoded[len(PREFIX):]
            run = []
        if label is not None:
            break

    if label is not None:
        after = text.index(_to_tags(PREFIX + label)) + len(PREFIX) + len(label)
        acc = bytearray()
        for ch in text[after:]:
            b = _selector_byte(ch)
            if b is None:
                break
            acc.append(b)
        if len(acc) >= MAC_LEN:
            mac = bytes(acc[:MAC_LEN])
    return label, mac


@dataclass
class SignatureResult:
    label: str | None
    keyed: bool
    valid: bool | None   # None when there is nothing to check
    detail: str

    @property
    def proves_authorship(self) -> bool:
        return bool(self.valid)


def verify(text: str, key: bytes | None = None) -> SignatureResult:
    label, mac = find(text)
    if label is None:
        return SignatureResult(None, False, None, "no signature found")

    if mac is None:
        return SignatureResult(
            label, False, None,
            "label only, with no key binding. Anyone who reads this can copy "
            "it onto other text, so it is not proof of authorship.",
        )
    if key is None:
        return SignatureResult(
            label, True, None,
            "signed with a key, but no key was supplied to check it against",
        )

    expected = _mac(key, text, label)
    if hmac.compare_digest(expected, mac):
        return SignatureResult(label, True, True, "valid: this key signed this exact text")
    return SignatureResult(
        label, True, False,
        "MAC does not match. Either the text was changed after signing, the "
        "mark was copied from other text, or a different key made it.",
    )
