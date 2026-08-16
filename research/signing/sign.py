#!/usr/bin/env python3
"""Sign text with an invisible, content-bound author signature.

This is the mirror of the rest of the project. Everything else asks "did
someone hide data in this text"; this asks "can I put my own name in text in a
way that survives copying and cannot be faked".

The naive version does not work, and it is worth saying why before the code.
If the signature is a fixed string -- a name, an ID, a hash of a key -- then
anyone who can read it can copy it into their own text. An invisible "written
by Marius" proves nothing, because I can paste it under your paragraph. A
signature that is not bound to the text it signs is not a signature. It is a
sticker.

So the payload here is a real signature over the text itself:

    canonical(text)  ->  SHA-256  ->  Ed25519 sign  ->  72 bytes  ->  invisible

Two properties follow. Moving the signature to different text breaks it,
because the hash no longer matches. Producing a new valid signature needs the
private key. Anyone can check it with the public key.

What it cannot do is survive deletion. Any cleaner removes it, including this
project's own. That gives the same one-sided result the detector has, pointing
the other way:

    a valid signature proves authorship
    no signature proves nothing at all, because removing one is trivial

Requires the `cryptography` package. This is research code and is not part of
the stdlib-only hook.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from wm_hook.carriers import carrier_class  # noqa: E402

MAGIC = b"WMS1"
SIG_LEN = 64
KEYID_LEN = 4
PAYLOAD_LEN = len(MAGIC) + KEYID_LEN + SIG_LEN  # 72 bytes


# ---------------------------------------------------------------------------
# Canonical form: what actually gets signed
# ---------------------------------------------------------------------------

def canonical(text: str) -> bytes:
    """The bytes a signature covers.

    Three normalisations, each chosen because the alternative breaks a
    signature for a reason the reader would call irrelevant:

      carriers removed    otherwise the signature would sign itself, and no
                          fixed point exists
      NFC                 so a Windows editor writing decomposed accents does
                          not invalidate a document signed on macOS
      line endings, trailing whitespace
                          so git's autocrlf and an editor stripping spaces are
                          not treated as forgery

    Everything else is deliberately in scope. Changing a word must break the
    signature; that is the point of binding it to the content.
    """
    stripped = "".join(c for c in text if carrier_class(ord(c)) is None)
    stripped = unicodedata.normalize("NFC", stripped)
    lines = [ln.rstrip() for ln in stripped.replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip().encode("utf-8")


def digest(text: str) -> bytes:
    return hashlib.sha256(canonical(text)).digest()


# ---------------------------------------------------------------------------
# Encoding: 72 bytes as invisible characters
# ---------------------------------------------------------------------------
#
# Variation selectors carry one arbitrary byte each, so 72 bytes costs 72
# codepoints. The tag block carries 7 bits and only ASCII, so the same payload
# base64-encoded would cost 96. Zero-width binary costs one bit per codepoint:
# 576 of them. Selectors win, and they need no minimum text length -- the
# signature is one contiguous run, not something spread across the document.

def _byte_to_selector(b: int) -> str:
    return chr(0xFE00 + b) if b < 16 else chr(0xE0100 + b - 16)


def _selector_to_byte(ch: str) -> int | None:
    cp = ord(ch)
    if 0xFE00 <= cp <= 0xFE0F:
        return cp - 0xFE00
    if 0xE0100 <= cp <= 0xE01EF:
        return cp - 0xE0100 + 16
    return None


def encode(payload: bytes) -> str:
    return "".join(_byte_to_selector(b) for b in payload)


def decode(text: str) -> bytes | None:
    """The longest selector run that starts with the magic bytes."""
    run: list[int] = []
    best: bytes | None = None
    for ch in text + "\x00":
        b = _selector_to_byte(ch)
        if b is None:
            if len(run) >= PAYLOAD_LEN:
                cand = bytes(run[:PAYLOAD_LEN])
                if cand.startswith(MAGIC):
                    best = cand
            run = []
        else:
            run.append(b)
    return best


# ---------------------------------------------------------------------------
# Sign and verify
# ---------------------------------------------------------------------------

def _crypto():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError:  # pragma: no cover
        raise SystemExit("needs `cryptography`: uv run --with cryptography ...")
    return ed25519, serialization


def keygen() -> tuple[bytes, bytes]:
    ed25519, serialization = _crypto()
    priv = ed25519.Ed25519PrivateKey.generate()
    raw = serialization.Encoding.Raw
    return (
        priv.private_bytes(
            encoding=raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        priv.public_key().public_bytes(
            encoding=raw, format=serialization.PublicFormat.Raw
        ),
    )


def key_id(public: bytes) -> bytes:
    return hashlib.sha256(public).digest()[:KEYID_LEN]


def sign(text: str, private: bytes, public: bytes) -> str:
    """Return text with an invisible signature appended."""
    ed25519, _ = _crypto()
    key = ed25519.Ed25519PrivateKey.from_private_bytes(private)
    sig = key.sign(digest(text))
    payload = MAGIC + key_id(public) + sig
    assert len(payload) == PAYLOAD_LEN
    # Appended, so the visible text is byte-identical up to this point.
    body = text.rstrip("\n")
    tail = text[len(body):]
    return body + encode(payload) + (tail or "\n")


def verify(text: str, public: bytes) -> tuple[bool, str]:
    ed25519, _ = _crypto()
    payload = decode(text)
    if payload is None:
        return False, "no signature found"
    if payload[len(MAGIC):len(MAGIC) + KEYID_LEN] != key_id(public):
        return False, "signature was made by a different key"
    sig = payload[len(MAGIC) + KEYID_LEN:]
    try:
        ed25519.Ed25519PublicKey.from_public_bytes(public).verify(sig, digest(text))
    except Exception:
        return False, "signature does not match this text"
    return True, "valid signature"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("keygen")
    g.add_argument("--out", type=Path, default=Path("wm-key"))
    s = sub.add_parser("sign")
    s.add_argument("file", type=Path)
    s.add_argument("--key", type=Path, default=Path("wm-key"))
    v = sub.add_parser("verify")
    v.add_argument("file", type=Path)
    v.add_argument("--pub", type=Path, default=Path("wm-key.pub"))
    a = p.parse_args()

    if a.cmd == "keygen":
        priv, pub = keygen()
        a.out.write_bytes(priv)
        a.out.with_suffix(".pub").write_bytes(pub)
        print(f"wrote {a.out} and {a.out.with_suffix('.pub')}")
        return 0
    if a.cmd == "sign":
        priv = a.key.read_bytes()
        pub = a.key.with_suffix(".pub").read_bytes()
        text = a.file.read_bytes().decode("utf-8")
        a.file.write_bytes(sign(text, priv, pub).encode("utf-8"))
        print(f"signed {a.file} ({PAYLOAD_LEN} invisible bytes appended)")
        return 0
    ok, why = verify(a.file.read_bytes().decode("utf-8"), a.pub.read_bytes())
    print(f"{'VALID  ' if ok else 'INVALID'} {a.file}: {why}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
