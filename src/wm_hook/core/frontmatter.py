"""AI provenance keys in YAML frontmatter.

Extracted from the 1089-line ``container_meta.py`` this project started from.
That module also handled SVG, PDF, DOCX, ODT and HTML, none of which the hook
ever called, and pulled in a 1110-line image module for five call sites in
those unused paths. Scope here is text, so the rest is gone.

**Behaviour is preserved exactly, defects included.** This was a move, not a
repair. Three known defects live below and are marked; fixing them belongs to
``watermark-removal`` task 2.5, where the change can be reviewed as a change
rather than hidden inside a refactor.
"""

from __future__ import annotations

import re

__all__ = [
    "AI_FRONTMATTER_KEYS",
    "AI_META_NAME_RE",
    "inspect_markdown",
    "clean_markdown",
]

# Frontmatter keys that often carry AI provenance.
AI_FRONTMATTER_KEYS = frozenset(
    {
        "generator",
        "ai",
        "ai_generated",
        "ai-generated",
        "claude",
        "anthropic",
        "openai",
        "gemini",
        "synthid",
        "c2pa",
        "content_credentials",
        "contentcredentials",
        "provenance",
        "digital_source_type",
        "digitalsourcetype",
        "created_with",
        "createdwith",
        "model",
        "llm",
    }
)

AI_META_NAME_RE = re.compile(
    r"generator|ai[-_ ]?generated|claude|anthropic|openai|gemini|synthid|"
    r"c2pa|content.?credential|provenance|digital.?source|aigc",
    re.I,
)

# DEFECT (task 2.2 / 2.5): anchored at \A, so a byte-order mark or any
# invisible character before the opening delimiter hides the whole block for
# one pass. Also matches a leading thematic break as if it were frontmatter.
_FM_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)


def _parse_simple_yaml_keys(block: str) -> list[tuple[str, str, int]]:
    """Return (key, full_line, line_index) for top-level keys only."""
    rows: list[tuple[str, str, int]] = []
    for i, line in enumerate(block.splitlines()):
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line[0] in (" ", "\t", "-"):
            continue  # nested / list — leave alone
        m = re.match(r"^([A-Za-z0-9_.-]+)\s*:", line)
        if m:
            rows.append((m.group(1), line, i))
    return rows


def inspect_markdown(text: str) -> tuple[bool, bool, list[str], dict]:
    findings: list[str] = []
    has_ai = False
    m = _FM_RE.match(text)
    if not m:
        return False, False, [], {"has_frontmatter": False}
    block = m.group(1)
    keys = []
    for key, _line, _i in _parse_simple_yaml_keys(block):
        keys.append(key)
        if key.lower() in AI_FRONTMATTER_KEYS or AI_META_NAME_RE.search(key):
            has_ai = True
            findings.append(f"frontmatter key: {key}")
        val = _line.split(":", 1)[1] if ":" in _line else ""
        if AI_META_NAME_RE.search(val):
            has_ai = True
            findings.append(f"frontmatter value hit on {key}")
    c2pa = any("c2pa" in f.lower() or "content" in f.lower() for f in findings)
    return c2pa, has_ai, findings, {"has_frontmatter": True, "keys": keys}


def clean_markdown(text: str) -> tuple[str, list[str]]:
    actions: list[str] = []
    m = _FM_RE.match(text)
    if not m:
        return text, ["no YAML frontmatter"]
    block = m.group(1)
    body = text[m.end():]
    kept: list[str] = []
    dropping = False  # inside the nested block of a dropped top-level key
    for line in block.splitlines():
        stripped = line.strip()

        # Blank lines and comments belong to whichever block we are inside.
        if not stripped or stripped.startswith("#"):
            if not dropping:
                kept.append(line)
            continue

        # Continuation lines (nested mappings, list items) follow their parent.
        if line[0] in (" ", "\t", "-"):
            if not dropping:
                kept.append(line)
            continue

        km = re.match(r"^([A-Za-z0-9_.-]+)\s*:", line)
        if not km:
            dropping = False
            kept.append(line)
            continue

        key = km.group(1)
        val = line.split(":", 1)[1] if ":" in line else ""
        if key.lower() in AI_FRONTMATTER_KEYS or AI_META_NAME_RE.search(key):
            actions.append(f"drop frontmatter key: {key}")
            dropping = True
            continue
        # DEFECT (task 2.5): a value mentioning a vendor deletes the whole key.
        # `title: Comparing Claude and Gemini` loses the title.
        if AI_META_NAME_RE.search(val):
            actions.append(f"drop frontmatter key (value hit): {key}")
            dropping = True
            continue

        dropping = False
        kept.append(line)
    if not actions:
        actions.append("no AI frontmatter keys removed")
    # DEFECT (task 3.1): the block is rebuilt with LF joins while the body
    # keeps its own line endings, so CRLF markdown is rewritten with mixed
    # endings even when it carries no marks at all.
    new_block = "\n".join(kept).strip("\n")
    if new_block:
        out = f"---\n{new_block}\n---\n{body}"
    else:
        out = body.lstrip("\n")
        actions.append("removed empty frontmatter block")
    return out, actions
