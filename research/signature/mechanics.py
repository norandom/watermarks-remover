#!/usr/bin/env python3
"""Mechanical fingerprint features: the residue a prose rewrite leaves behind.

The premise. A humanizer pass rewrites *wording*. It does not usually touch
indentation width, list-marker choice, fence style, quote characters, spacing
around punctuation, or blank-line habits. Those are emitted by the generator
and copied through edits, so they survive exactly the transformation that
destroys a style signature.

That makes them the interesting features for two purposes at once:

  detection -- what still identifies the producer after a rewrite
  removal   -- and therefore precisely what you would normalise to stop it

Nothing here is prose style. No word lists, no cadence, no "delve into".
Every feature is a mechanical choice with a defensible normal form, which is
what makes "what to strip" answerable rather than a matter of taste.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter

# --- helpers ----------------------------------------------------------------

_FENCE = re.compile(r"^(\s*)(```|~~~)(.*)$")
_ATX = re.compile(r"^(#{1,6})\s")
_SETEXT = re.compile(r"^(=+|-+)\s*$")
_LIST = re.compile(r"^(\s*)([-*+])\s")
_ORDERED = re.compile(r"^(\s*)(\d+)([.)])\s")
_TABLE = re.compile(r"^\s*\|")


def _lines(t: str) -> list[str]:
    return t.split("\n")


def _nonblank(t: str) -> list[str]:
    return [l for l in _lines(t) if l.strip()]


def _safe(num: float, den: float) -> float:
    return num / den if den else 0.0


# --- whitespace mechanics ---------------------------------------------------

def trailing_space_rate(t: str) -> float:
    ls = _lines(t)
    return _safe(sum(1 for l in ls if l != l.rstrip() and l.strip()), len(ls))


def tab_indent_rate(t: str) -> float:
    ind = [l for l in _lines(t) if l[:1] in (" ", "\t")]
    return _safe(sum(1 for l in ind if l.startswith("\t")), len(ind))


def blank_run_mean(t: str) -> float:
    runs, cur = [], 0
    for l in _lines(t):
        if l.strip():
            if cur:
                runs.append(cur)
            cur = 0
        else:
            cur += 1
    return statistics.mean(runs) if runs else 0.0


def final_newline(t: str) -> float:
    return 1.0 if t.endswith("\n") else 0.0


def indent_step(t: str) -> float:
    """Modal indentation increment. 2 and 4 are different houses."""
    widths = sorted({len(l) - len(l.lstrip(" ")) for l in _lines(t)
                     if l.startswith(" ") and l.strip()})
    steps = [b - a for a, b in zip(widths, widths[1:]) if 0 < b - a <= 8]
    return float(Counter(steps).most_common(1)[0][0]) if steps else 0.0


# --- markdown mechanics -----------------------------------------------------

def bullet_marker_dash(t: str) -> float:
    marks = [m.group(2) for l in _lines(t) if (m := _LIST.match(l))]
    return _safe(sum(1 for m in marks if m == "-"), len(marks))


def ordered_marker_dot(t: str) -> float:
    marks = [m.group(3) for l in _lines(t) if (m := _ORDERED.match(l))]
    return _safe(sum(1 for m in marks if m == "."), len(marks))


def atx_heading_rate(t: str) -> float:
    atx = sum(1 for l in _lines(t) if _ATX.match(l))
    setext = sum(1 for l in _lines(t) if _SETEXT.match(l))
    return _safe(atx, atx + setext)


def fence_backtick_rate(t: str) -> float:
    f = [m.group(2) for l in _lines(t) if (m := _FENCE.match(l))]
    return _safe(sum(1 for x in f if x == "```"), len(f))


def fence_language_rate(t: str) -> float:
    """Fraction of opening fences carrying an info string."""
    opens, tagged, inside = 0, 0, False
    for l in _lines(t):
        m = _FENCE.match(l)
        if not m:
            continue
        if not inside:
            opens += 1
            if m.group(3).strip():
                tagged += 1
            inside = True
        else:
            inside = False
    return _safe(tagged, opens)


def table_rate(t: str) -> float:
    return _safe(sum(1 for l in _lines(t) if _TABLE.match(l)), len(_nonblank(t)))


def heading_depth_mean(t: str) -> float:
    d = [len(m.group(1)) for l in _lines(t) if (m := _ATX.match(l))]
    return statistics.mean(d) if d else 0.0


# --- punctuation and character mechanics ------------------------------------

def curly_quote_rate(t: str) -> float:
    curly = sum(t.count(c) for c in "‘’“”")
    straight = t.count("'") + t.count('"')
    return _safe(curly, curly + straight)


def em_dash_rate(t: str) -> float:
    """Em/en dashes per 1000 characters. A mechanical choice, not word choice."""
    return _safe(t.count("—") + t.count("–"), len(t)) * 1000


def unicode_ellipsis_rate(t: str) -> float:
    return _safe(t.count("…"), t.count("…") + t.count("..."))


def spaced_em_dash(t: str) -> float:
    """Of em dashes present, how many are surrounded by spaces."""
    total = t.count("—")
    spaced = len(re.findall(r"\s—\s", t))
    return _safe(spaced, total)


def double_space_after_period(t: str) -> float:
    single = len(re.findall(r"\.\s(?=[A-Z])", t))
    double = len(re.findall(r"\.\s\s+(?=[A-Z])", t))
    return _safe(double, single + double)


def line_length_p90(t: str) -> float:
    ls = [len(l) for l in _nonblank(t)]
    if not ls:
        return 0.0
    return float(sorted(ls)[int(0.9 * (len(ls) - 1))])


def hard_wrap_rate(t: str) -> float:
    """Fraction of prose lines landing in a 70-85 column band: hand-wrapped."""
    ls = [len(l) for l in _nonblank(t) if not l.lstrip().startswith(("|", "#", "-", "*", ">"))]
    return _safe(sum(1 for n in ls if 70 <= n <= 85), len(ls))


MECHANICS = {
    "trailing_space_rate": trailing_space_rate,
    "tab_indent_rate": tab_indent_rate,
    "blank_run_mean": blank_run_mean,
    "final_newline": final_newline,
    "indent_step": indent_step,
    "bullet_marker_dash": bullet_marker_dash,
    "ordered_marker_dot": ordered_marker_dot,
    "atx_heading_rate": atx_heading_rate,
    "fence_backtick_rate": fence_backtick_rate,
    "fence_language_rate": fence_language_rate,
    "table_rate": table_rate,
    "heading_depth_mean": heading_depth_mean,
    "curly_quote_rate": curly_quote_rate,
    "em_dash_per_1k": em_dash_rate,
    "unicode_ellipsis_rate": unicode_ellipsis_rate,
    "spaced_em_dash": spaced_em_dash,
    "double_space_sentence": double_space_after_period,
    "line_length_p90": line_length_p90,
    "hard_wrap_rate": hard_wrap_rate,
}

#: For each feature, the normal form that erases it. This is the "what to
#: strip" answer, and it is why mechanical features were chosen over stylistic
#: ones: each has a defensible canonical value.
NORMALISATION = {
    "trailing_space_rate": "strip trailing whitespace",
    "tab_indent_rate": "convert indentation to spaces",
    "blank_run_mean": "collapse consecutive blank lines to one",
    "final_newline": "ensure exactly one final newline",
    "indent_step": "reindent to a fixed step",
    "bullet_marker_dash": "normalise list markers to a single character",
    "ordered_marker_dot": "normalise ordered-list delimiters",
    "atx_heading_rate": "convert setext headings to ATX",
    "fence_backtick_rate": "normalise code fences to backticks",
    "fence_language_rate": "require or strip fence info strings consistently",
    "table_rate": "no safe normal form; structural choice",
    "heading_depth_mean": "no safe normal form; structural choice",
    "curly_quote_rate": "fold curly quotes to straight",
    "em_dash_per_1k": "fold em and en dashes to hyphen or rephrase",
    "unicode_ellipsis_rate": "fold U+2026 to three periods",
    "spaced_em_dash": "normalise spacing around dashes",
    "double_space_sentence": "collapse to a single inter-sentence space",
    "line_length_p90": "rewrap to a fixed column",
    "hard_wrap_rate": "rewrap, or stop wrapping",
}
