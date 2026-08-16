#!/usr/bin/env python3
"""What an invisible signature survives, measured rather than assumed.

Every row is a transformation a signed document plausibly passes through
between being written and being checked. The result is the honest answer to
"can I sign my text this way", and it is not a flattering one.
"""

from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.path.insert(0, str(HERE.parents[1] / "src" / "wm_hook" / "core"))

from sign import PAYLOAD_LEN, keygen, sign, verify  # noqa: E402
from text_unicode import clean_text  # noqa: E402

from wm_hook.verdict import classify  # noqa: E402

SAMPLE = """# Release notes

The scheduler now retries failed jobs three times before giving up. Previously
a transient database timeout would drop the job silently, which made the retry
count in the dashboard meaningless.

Configuration is unchanged. Existing deployments pick this up on restart.
"""


def para(n: int) -> str:
    return SAMPLE + "\n".join(
        f"Paragraph {i} of filler text, long enough to be realistic prose "
        f"rather than a toy fixture used only to pad a measurement out."
        for i in range(n)
    )


TRANSFORMS = [
    ("untouched",
     lambda t: t,
     "the control"),
    ("CRLF line endings",
     lambda t: t.replace("\n", "\r\n"),
     "git autocrlf on a Windows checkout"),
    ("trailing whitespace stripped",
     lambda t: "\n".join(ln.rstrip() for ln in t.split("\n")),
     "almost every editor on save"),
    ("NFC normalisation",
     lambda t: unicodedata.normalize("NFC", t),
     "the canonical form itself"),
    ("NFD normalisation",
     lambda t: unicodedata.normalize("NFD", t),
     "macOS filesystem round-trip"),
    ("NFKC normalisation",
     lambda t: unicodedata.normalize("NFKC", t),
     "many search indexes and form fields"),
    ("leading text added",
     lambda t: "Edited by someone else.\n\n" + t,
     "content changed, must fail"),
    ("one word changed",
     lambda t: t.replace("three times", "five times"),
     "content changed, must fail"),
    ("this project's cleaner",
     lambda t: clean_text(t)[0],
     "wm-hook, or any other carrier stripper"),
]


def main() -> int:
    priv, pub = keygen()
    signed = sign(SAMPLE, priv, pub)

    print(f"payload            {PAYLOAD_LEN} bytes as {PAYLOAD_LEN} invisible codepoints")
    print(f"visible text       {len(SAMPLE)} characters")
    print(f"overhead           {100 * PAYLOAD_LEN / len(SAMPLE):.1f}% of the character count")
    print(f"visible bytes identical after signing: "
          f"{''.join(c for c in signed if ord(c) < 0xFE00) == SAMPLE.rstrip(chr(10)) + chr(10)}")

    print(f"\n{'transformation':<32} {'verifies':<9} {'expected':<9} why it matters")
    print("-" * 96)
    MUST_FAIL = {"leading text added", "one word changed", "this project's cleaner"}
    wrong = 0
    for name, fn, why in TRANSFORMS:
        ok, _ = verify(fn(signed), pub)
        expected = name not in MUST_FAIL
        mark = "yes" if ok else "NO"
        flag = "" if ok == expected else "   <-- UNEXPECTED"
        wrong += ok != expected
        print(f"{name:<32} {mark:<9} {'yes' if expected else 'no':<9} {why}{flag}")

    print(f"\nunexpected results: {wrong}")

    # A signature is invisible, not hidden. Our own detector should see it.
    v = classify(signed)
    print(f"\nOur own detector on the signed file: {v.level}"
          f" ({', '.join(e.name for e in v.evidence) or 'no evidence'})")
    print("A signature is meant to be invisible to a reader, not concealed from")
    print("a scanner. Anyone who looks will find it, and can delete it.")

    print("\nHow much text is needed:")
    print(f"{'visible chars':>14}  {'overhead':>9}")
    for n in (0, 5, 20, 100):
        t = para(n)
        print(f"{len(t):>14}  {100 * PAYLOAD_LEN / len(t):>8.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
