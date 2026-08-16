"""Shared fixtures for the watermark-removal suite.

This module is the whole test harness. It supplies the three things every
later test module in this spec needs, and deliberately nothing else:

* **A throwaway working tree with an exact-bytes writer.** Requirements 6 and
  11.1/11.3 are byte-identity claims. A test that wrote its input through
  ``open(..., "w")`` would hand the cleaner text that Python had already
  newline-translated, and the claim would be vacuous. Every input this suite
  produces goes through :func:`write_exact_bytes`.

* **A policy-variant factory.** The transform flags are exercised in
  combinations (Requirement 9, and the per-entry policies of Requirement
  11.4), so the field vocabulary is stated in exactly one place here.

* **An annotated-corpus loader.** The preservation and carrier corpora are
  data directories whose entries carry their own assertions: the rule that
  protects an entry (Requirement 11.1) or the policy it must be cleaned under
  and the residue it may keep (Requirement 11.4). Annotations live in a
  sidecar manifest rather than inside the files, because a preservation entry
  must be byte-identical after cleaning and therefore cannot carry a comment.

The policy-variant factory produces plain mappings, not ``CleanPolicy``
instances: the harness must import cleanly before any owned module exists,
and the value object arrives with tasks.md 2.1. A variant's ``overrides`` is
directly splattable into that constructor once it does.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable

import pytest

TESTS_DIR = Path(__file__).resolve().parent

#: Root of the annotated corpora (design.md "File Structure Plan").
CORPUS_ROOT = TESTS_DIR / "corpus"

#: Entries that must come out byte-identical (Requirement 11.1).
PRESERVATION_CORPUS = CORPUS_ROOT / "preservation"

#: Entries that must be cleaned under their annotated policy (Requirement 11.4).
CARRIERS_CORPUS = CORPUS_ROOT / "carriers"

#: Sidecar annotation file, one per corpus directory.
CORPUS_MANIFEST_NAME = "manifest.json"

#: ``CleanPolicy``'s field vocabulary and documented defaults, from design.md
#: "Data Models / Domain Model". Three of these differ from the shipped
#: behaviour by requirement: private-use characters are preserved (3.5), a
#: required byte-order mark is preserved (6.5), and space normalisation becomes
#: position-aware rather than unconditional (4.1).
POLICY_FIELD_DEFAULTS: Mapping[str, bool] = MappingProxyType(
    {
        "normalize_spaces": True,
        "strip_private_use": False,
        "strip_bom": False,
        "strip_bidi": False,
        "strip_emoji_glue": False,
        "aggressive_homoglyphs": False,
        "drop_frontmatter_keys": True,
    }
)


# --------------------------------------------------------------------------
# Throwaway working tree
# --------------------------------------------------------------------------


def write_exact_bytes(path: Path, data: bytes) -> Path:
    """Write *data* to *path* verbatim, creating parent directories.

    Binary mode throughout: no newline translation, no encoding, no BOM
    handling. What goes in is what a later assertion compares against.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


@dataclass(frozen=True)
class WorkTree:
    """A disposable directory that a test may rewrite files inside."""

    root: Path

    def path(self, relpath: str | os.PathLike[str]) -> Path:
        """Resolve *relpath* inside the tree, refusing anything that escapes."""
        candidate = Path(self.root, relpath).resolve()
        if candidate != self.root and not candidate.is_relative_to(self.root):
            raise ValueError(
                f"path escapes the work tree: {relpath!r} resolves to {candidate}"
            )
        return candidate

    def write_bytes(self, relpath: str | os.PathLike[str], data: bytes) -> Path:
        """Create a file inside the tree with exactly *data* as its contents."""
        return write_exact_bytes(self.path(relpath), data)

    def read_bytes(self, relpath: str | os.PathLike[str]) -> bytes:
        """Read a file inside the tree verbatim."""
        return self.path(relpath).read_bytes()


@pytest.fixture
def work_tree(tmp_path: Path) -> WorkTree:
    """An empty, per-test working tree the suite may write and rewrite in."""
    root = tmp_path / "worktree"
    root.mkdir()
    return WorkTree(root=root.resolve())


# --------------------------------------------------------------------------
# Policy variants
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class PolicyVariant:
    """One point in the transform-flag space.

    ``fields`` is every documented flag with the variant's value applied;
    ``overrides`` is exactly what the caller named, ready to splat into the
    ``CleanPolicy`` constructor that tasks.md 2.1 introduces.
    """

    fields: Mapping[str, bool]
    overrides: Mapping[str, bool]


def make_policy_variant(**overrides: bool) -> PolicyVariant:
    """Build a policy variant, rejecting anything outside the documented set.

    Validating here is what stops a downstream test from asserting against a
    flag that does not exist — a misspelled keyword would otherwise be
    silently accepted today and silently ignored once the real value object
    lands.
    """
    unknown = sorted(set(overrides) - set(POLICY_FIELD_DEFAULTS))
    if unknown:
        known = ", ".join(sorted(POLICY_FIELD_DEFAULTS))
        raise KeyError(
            f"unknown policy field(s): {', '.join(unknown)}; known fields are {known}"
        )

    non_boolean = sorted(
        name for name, value in overrides.items() if not isinstance(value, bool)
    )
    if non_boolean:
        raise TypeError(
            "policy fields are boolean flags; got a non-boolean for: "
            + ", ".join(non_boolean)
        )

    fields = dict(POLICY_FIELD_DEFAULTS)
    fields.update(overrides)
    return PolicyVariant(
        fields=MappingProxyType(fields),
        overrides=MappingProxyType(dict(overrides)),
    )


@pytest.fixture(scope="session")
def policy_field_defaults() -> Mapping[str, bool]:
    """The documented default for every transform flag."""
    return POLICY_FIELD_DEFAULTS


@pytest.fixture(scope="session")
def policy_variant() -> Callable[..., PolicyVariant]:
    """Factory for a transform-flag variant; see :func:`make_policy_variant`."""
    return make_policy_variant


# --------------------------------------------------------------------------
# Annotated corpus enumeration
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusEntry:
    """One corpus file together with the annotations that describe it."""

    name: str
    path: Path
    annotations: Mapping[str, Any]

    def read_bytes(self) -> bytes:
        return self.path.read_bytes()

    def annotation(self, key: str) -> Any:
        """Fetch an annotation, naming the entry when it is absent."""
        try:
            return self.annotations[key]
        except KeyError:
            raise KeyError(
                f"corpus entry {self.name!r} in {self.path.parent} carries no "
                f"{key!r} annotation"
            ) from None


def load_corpus(directory: str | os.PathLike[str]) -> tuple[CorpusEntry, ...]:
    """Enumerate an annotated corpus directory, sorted by entry name.

    The manifest and the directory contents must agree exactly. An
    unannotated file is a hole in the suite's coverage and a stale annotation
    describes a file that no longer exists — both fail loudly rather than
    quietly shrinking what a corpus test actually checks.
    """
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"corpus directory does not exist: {directory}")

    manifest_path = directory / CORPUS_MANIFEST_NAME
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"corpus directory {directory} has no {CORPUS_MANIFEST_NAME}"
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise TypeError(
            f"{manifest_path} must hold a JSON object mapping file name to annotations"
        )

    present = {
        entry.name
        for entry in directory.iterdir()
        if entry.is_file() and entry.name != CORPUS_MANIFEST_NAME
    }
    unannotated = sorted(present - set(manifest))
    orphaned = sorted(set(manifest) - present)
    if unannotated or orphaned:
        raise ValueError(
            f"{manifest_path} is out of step with {directory}: "
            f"unannotated files: {unannotated or 'none'}; "
            f"annotations without a file: {orphaned or 'none'}"
        )

    entries = []
    for name in sorted(present):
        annotations = manifest[name]
        if not isinstance(annotations, dict):
            raise TypeError(
                f"annotations for {name!r} in {manifest_path} must be a JSON "
                f"object, got {type(annotations).__name__}"
            )
        entries.append(
            CorpusEntry(
                name=name,
                path=directory / name,
                annotations=MappingProxyType(dict(annotations)),
            )
        )
    return tuple(entries)


@pytest.fixture(scope="session")
def corpus_root() -> Path:
    """Root of the annotated corpora."""
    return CORPUS_ROOT


@pytest.fixture(scope="session")
def corpus_loader() -> Callable[..., tuple[CorpusEntry, ...]]:
    """Enumerate an annotated corpus directory; see :func:`load_corpus`."""
    return load_corpus
