#!/usr/bin/env python3
"""Covert channels as encoder/decoder pairs, so capacity can be measured.

A technique count treats "we miss trailing-whitespace encoding" and "we miss an
unbounded tag payload" as one miss each. That is the wrong metric. The question
a countermeasure has to answer is how many bits an adversary can still push
through it.

So each channel here is a real codec: encode a payload into a host text, clean
the result, decode whatever survived. Residual capacity is measured in bits
recovered, not estimated from alphabet sizes, because the interesting channels
are the ones where the cleaner's own exemptions leave a hole.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

# --- bit plumbing -----------------------------------------------------------


def to_bits(data: bytes) -> list[int]:
    return [(b >> i) & 1 for b in data for i in range(7, -1, -1)]


def from_bits(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits) - 7, 8):
        v = 0
        for b in bits[i:i + 8]:
            v = (v << 1) | b
        out.append(v)
    return bytes(out)


@dataclass(frozen=True)
class Channel:
    key: str
    name: str
    #: bits the channel can carry in this host, before any cleaning
    capacity: Callable[[str], int]
    encode: Callable[[str, list[int]], str]
    decode: Callable[[str], list[int]]
    note: str = ""


# --- 1. zero-width binary ---------------------------------------------------

ZW0, ZW1 = "​", "‌"


def _zw_cap(host: str) -> int:
    return sum(1 for a, b in zip(host, host[1:]) if a.isalnum() and b.isalnum())


def _zw_enc(host: str, bits: list[int]) -> str:
    out, it = [], iter(bits)
    for a, b in zip(host, host[1:]):
        out.append(a)
        if a.isalnum() and b.isalnum():
            v = next(it, None)
            if v is not None:
                out.append(ZW1 if v else ZW0)
    out.append(host[-1:])
    return "".join(out)


def _zw_dec(text: str) -> list[int]:
    return [1 if c == ZW1 else 0 for c in text if c in (ZW0, ZW1)]


# --- 2. tag block, bare -----------------------------------------------------


def _tag_cap(host: str) -> int:
    # 6 bits per tag character; the block mirrors printable ASCII.
    return (len(host) // 4) * 6


def _tag_enc(host: str, bits: list[int]) -> str:
    payload = "".join(
        chr(0xE0020 + int("".join(map(str, bits[i:i + 6])).ljust(6, "0"), 2))
        for i in range(0, len(bits) - 5, 6)
    )
    return host + payload


def _tag_dec(text: str) -> list[int]:
    bits: list[int] = []
    for c in text:
        cp = ord(c)
        if 0xE0020 <= cp <= 0xE005F:
            bits += [int(x) for x in format(cp - 0xE0020, "06b")]
    return bits


# --- 3. tag block behind a flag emoji ---------------------------------------
# The exemption the cleaner grants to subdivision-flag sequences. Unbounded by
# construction: nothing checks the payload length or alphabet.

FLAG, CANCEL = "\U0001F3F4", "\U000E007F"


def _flag_cap(host: str) -> int:
    return (len(host) // 4) * 6


def _flag_enc(host: str, bits: list[int]) -> str:
    payload = "".join(
        chr(0xE0020 + int("".join(map(str, bits[i:i + 6])).ljust(6, "0"), 2))
        for i in range(0, len(bits) - 5, 6)
    )
    return host + FLAG + payload + CANCEL


def _flag_dec(text: str) -> list[int]:
    bits: list[int] = []
    for m in re.finditer(re.escape(FLAG) + r"([\U000E0020-\U000E007E]*)" + re.escape(CANCEL), text):
        for c in m.group(1):
            bits += [int(x) for x in format(ord(c) - 0xE0020, "06b")]
    return bits


# --- 4. variation selectors -------------------------------------------------

VS = [chr(0xFE00 + i) for i in range(16)] + [chr(0xE0100 + i) for i in range(240)]
VS_INDEX = {c: i for i, c in enumerate(VS)}


def _vs_cap(host: str) -> int:
    return sum(1 for c in host if c.isalnum()) * 8


def _vs_enc(host: str, bits: list[int]) -> str:
    out, i = [], 0
    for c in host:
        out.append(c)
        if c.isalnum() and i + 8 <= len(bits):
            v = int("".join(map(str, bits[i:i + 8])), 2)
            out.append(VS[v])
            i += 8
    return "".join(out)


def _vs_dec(text: str) -> list[int]:
    bits: list[int] = []
    for c in text:
        if c in VS_INDEX:
            bits += [int(x) for x in format(VS_INDEX[c], "08b")]
    return bits


# --- 5. private use ---------------------------------------------------------


def _pua_cap(host: str) -> int:
    return (len(host) // 4) * 12


def _pua_enc(host: str, bits: list[int]) -> str:
    payload = "".join(
        chr(0xE000 + int("".join(map(str, bits[i:i + 12])).ljust(12, "0"), 2))
        for i in range(0, len(bits) - 11, 12)
    )
    return host + payload


def _pua_dec(text: str) -> list[int]:
    bits: list[int] = []
    for c in text:
        if 0xE000 <= ord(c) <= 0xEFFF:
            bits += [int(x) for x in format(ord(c) - 0xE000, "012b")]
    return bits


# --- 6. space homoglyph -----------------------------------------------------

SP0, SP1 = " ", " "


def _sp_cap(host: str) -> int:
    return host.count(" ")


def _sp_enc(host: str, bits: list[int]) -> str:
    out, it = [], iter(bits)
    for c in host:
        if c == " ":
            v = next(it, None)
            out.append(SP1 if v else SP0)
        else:
            out.append(c)
    return "".join(out)


def _sp_dec(text: str) -> list[int]:
    return [1 if c == SP1 else 0 for c in text if c in (SP0, SP1)]


# --- 7. trailing whitespace count -------------------------------------------


def _tw_cap(host: str) -> int:
    return len(host.split("\n"))


def _tw_enc(host: str, bits: list[int]) -> str:
    out, it = [], iter(bits)
    for line in host.split("\n"):
        v = next(it, None)
        out.append(line + ("  " if v else " ") if v is not None else line)
    return "\n".join(out)


def _tw_dec(text: str) -> list[int]:
    bits = []
    for line in text.split("\n"):
        n = len(line) - len(line.rstrip(" "))
        if n:
            bits.append(1 if n >= 2 else 0)
    return bits


# --- 8. invisible non-Cf letters --------------------------------------------

HF0, HF1 = "ㅤ", "ﾠ"


def _hf_cap(host: str) -> int:
    return sum(1 for a, b in zip(host, host[1:]) if a.isalnum() and b.isalnum())


def _hf_enc(host: str, bits: list[int]) -> str:
    out, it = [], iter(bits)
    for a, b in zip(host, host[1:]):
        out.append(a)
        if a.isalnum() and b.isalnum():
            v = next(it, None)
            if v is not None:
                out.append(HF1 if v else HF0)
    out.append(host[-1:])
    return "".join(out)


def _hf_dec(text: str) -> list[int]:
    return [1 if c == HF1 else 0 for c in text if c in (HF0, HF1)]


# --- 9. braille blank -------------------------------------------------------

BR0, BR1 = "⠀", "⠂"


def _br_cap(host: str) -> int:
    return host.count(" ")


def _br_enc(host: str, bits: list[int]) -> str:
    out, it = [], iter(bits)
    for c in host:
        out.append(c)
        if c == " ":
            v = next(it, None)
            if v is not None:
                out.append(BR1 if v else BR0)
    return "".join(out)


def _br_dec(text: str) -> list[int]:
    return [1 if c == BR1 else 0 for c in text if c in (BR0, BR1)]


CHANNELS: tuple[Channel, ...] = (
    Channel("zero_width", "Zero-width binary", _zw_cap, _zw_enc, _zw_dec),
    Channel("tag_bare", "Tag block, bare", _tag_cap, _tag_enc, _tag_dec),
    Channel("tag_flag", "Tag block behind a flag emoji", _flag_cap, _flag_enc,
            _flag_dec, "exploits the subdivision-flag exemption"),
    Channel("var_selector", "Variation selectors", _vs_cap, _vs_enc, _vs_dec),
    Channel("private_use", "Private-use area", _pua_cap, _pua_enc, _pua_dec),
    Channel("space_homoglyph", "Space homoglyph", _sp_cap, _sp_enc, _sp_dec),
    Channel("trailing_ws", "Trailing-whitespace count", _tw_cap, _tw_enc, _tw_dec,
            "a whitespace count, not a codepoint"),
    Channel("hangul_filler", "Invisible non-Cf letters", _hf_cap, _hf_enc, _hf_dec,
            "category Lo, outside the strip rule"),
    Channel("braille_blank", "Braille pattern blank", _br_cap, _br_enc, _br_dec,
            "category So, outside the strip rule"),
)
