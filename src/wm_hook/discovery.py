"""Turning what a user typed into the list of files to actually look at.

pre-commit always hands over an explicit file list, so this exists for the
other caller: a person pointing the tool at a project directory. Refusing a
directory is defensible; accepting one and reporting "0 of 0 files are clean"
is not, and that is what the CLI used to do.

The extension allow-list is deliberate rather than content sniffing. ``identify``
and most type detectors do not know .qmd or .psd1, so a types-based filter
silently skips Quarto and PowerShell data files -- the same reason the
pre-commit hook ships an explicit ``files:`` pattern instead of ``types: [text]``.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

TEXT_EXTS = frozenset({
    ".md", ".markdown", ".mdx", ".qmd", ".rmd", ".txt", ".rst", ".tex",
    ".py", ".ps1", ".psm1", ".psd1", ".sh", ".bash", ".zsh",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".css", ".html",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml",
    ".rs", ".go", ".c", ".h", ".cpp", ".hpp", ".java", ".rb", ".sql", ".po",
})

#: Directories that hold code nobody in this repository wrote. Scanning them
#: produces findings against third-party material and, in the case of a built
#: ``site/``, against the very language packs the cleaner is known to damage.
SKIP_DIRS = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    ".pytest_cache", "target", ".mypy_cache", ".ruff_cache", ".tox", "site",
})


def iter_text_files(
    paths: Iterable[Path],
    *,
    exts: frozenset[str] = TEXT_EXTS,
    skip_dirs: frozenset[str] = SKIP_DIRS,
) -> Iterator[Path]:
    """Expand directories to their text files; pass explicit files through.

    A file named outright is always yielded, extension or not. Asking for a
    specific file is an instruction, not a suggestion, and second-guessing it
    would make the tool unusable on extensionless files like ``LICENSE``.
    Directory walks are filtered, because there the tool is guessing.
    """
    seen: set[Path] = set()
    for path in paths:
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.suffix.lower() not in exts or not child.is_file():
                    continue
                if any(part in skip_dirs for part in child.relative_to(path).parts[:-1]):
                    continue
                if child not in seen:
                    seen.add(child)
                    yield child
        elif path not in seen:
            seen.add(path)
            yield path
