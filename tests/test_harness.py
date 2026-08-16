"""Sentinel coverage for the shared test harness (tasks.md 1.1).

Every later module in this suite leans on these three fixtures, so a
regression here would silently weaken every downstream assertion: the
byte-identity claims of Requirement 11.1 and 11.3 are only as trustworthy as
the writer that produces the input bytes, and the corpus assertions of 11.1
and 11.4 are only as trustworthy as the enumeration that finds their
annotations.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# A BOM, CRLF endings, a provenance key and an interior zero-width space: the
# four things this spec must never mangle on the way in to a test.
PAYLOAD = b"\xef\xbb\xbf---\r\ngenerator: Claude\r\n---\r\n\xe2\x80\x8bbody"

# Escaped, not literal. This repository ships a hook that strips U+200B from
# text files, the rule that would spare it between Thai bases does not land
# until 2.6, and a self-hosted run must not be able to edit this constant.
THAI_WITH_ZWSP = "\u0e01\u200b\u0e02".encode()


# --------------------------------------------------------------------------
# Throwaway working tree
# --------------------------------------------------------------------------


def test_work_tree_starts_empty(work_tree):
    assert work_tree.root.is_dir()
    assert list(work_tree.root.iterdir()) == []


def test_work_tree_writes_and_reads_exact_bytes(work_tree):
    written = work_tree.write_bytes("docs/post.md", PAYLOAD)

    # No newline translation, no encoding round-trip, no BOM stripping.
    assert written.read_bytes() == PAYLOAD
    assert work_tree.read_bytes("docs/post.md") == PAYLOAD
    assert written.parent == work_tree.root / "docs"


def test_work_tree_refuses_paths_outside_the_tree(work_tree):
    with pytest.raises(ValueError, match="escaped.md"):
        work_tree.write_bytes("../escaped.md", b"x")


# --------------------------------------------------------------------------
# Policy variants
# --------------------------------------------------------------------------


def test_policy_variant_defaults_match_the_documented_flags(
    policy_variant, policy_field_defaults
):
    # design.md "Data Models / Domain Model" — CleanPolicy's field list and
    # documented defaults. Task 2.1 constructs the real value object; the
    # harness only needs the vocabulary.
    assert dict(policy_field_defaults) == {
        "normalize_spaces": True,
        "strip_private_use": False,
        "strip_bom": False,
        "strip_bidi": False,
        "strip_emoji_glue": False,
        "aggressive_homoglyphs": False,
        "drop_frontmatter_keys": True,
    }
    assert dict(policy_variant().fields) == dict(policy_field_defaults)
    assert dict(policy_variant().overrides) == {}


def test_policy_variant_applies_overrides_without_mutating_the_defaults(
    policy_variant, policy_field_defaults
):
    variant = policy_variant(strip_private_use=True, normalize_spaces=False)

    assert variant.overrides == {
        "strip_private_use": True,
        "normalize_spaces": False,
    }
    assert variant.fields["strip_private_use"] is True
    assert variant.fields["normalize_spaces"] is False
    assert variant.fields["drop_frontmatter_keys"] is True

    # The shared default table survives a variant being built from it.
    assert policy_field_defaults["strip_private_use"] is False
    assert policy_field_defaults["normalize_spaces"] is True


def test_policy_variant_rejects_an_unknown_flag(policy_variant):
    with pytest.raises(KeyError, match="strip_watermarks"):
        policy_variant(strip_watermarks=True)


def test_policy_variant_rejects_a_non_boolean_flag(policy_variant):
    with pytest.raises(TypeError, match="strip_bom"):
        policy_variant(strip_bom="yes")


# --------------------------------------------------------------------------
# Annotated corpus enumeration
# --------------------------------------------------------------------------


def _write_manifest(work_tree, mapping):
    return work_tree.write_bytes(
        "corpus/manifest.json", json.dumps(mapping).encode("utf-8")
    )


def test_corpus_loader_enumerates_annotated_entries(work_tree, corpus_loader):
    work_tree.write_bytes("corpus/flag.md", b"\xf0\x9f\x8f\xb4")
    work_tree.write_bytes("corpus/thai.txt", THAI_WITH_ZWSP)
    _write_manifest(
        work_tree,
        {
            "thai.txt": {"protected_by": "zwsp-word-separator"},
            "flag.md": {"protected_by": "emoji-base"},
        },
    )

    entries = corpus_loader(work_tree.path("corpus"))

    # Sorted by name, and the manifest is not itself an entry.
    assert [entry.name for entry in entries] == ["flag.md", "thai.txt"]
    assert entries[1].read_bytes() == THAI_WITH_ZWSP
    assert entries[1].annotation("protected_by") == "zwsp-word-separator"
    assert entries[1].path == work_tree.path("corpus/thai.txt")


def test_corpus_loader_rejects_an_unannotated_file(work_tree, corpus_loader):
    work_tree.write_bytes("corpus/lonely.md", b"x")
    _write_manifest(work_tree, {})

    with pytest.raises(ValueError, match="lonely.md"):
        corpus_loader(work_tree.path("corpus"))


def test_corpus_loader_rejects_an_annotation_without_a_file(work_tree, corpus_loader):
    _write_manifest(work_tree, {"ghost.md": {"protected_by": "nothing"}})

    with pytest.raises(ValueError, match="ghost.md"):
        corpus_loader(work_tree.path("corpus"))


def test_corpus_loader_rejects_a_non_object_annotation(work_tree, corpus_loader):
    work_tree.write_bytes("corpus/plain.md", b"x")
    _write_manifest(work_tree, {"plain.md": "zwsp-word-separator"})

    with pytest.raises(TypeError, match="plain.md"):
        corpus_loader(work_tree.path("corpus"))


def test_corpus_entry_reports_a_missing_annotation_by_name(work_tree, corpus_loader):
    work_tree.write_bytes("corpus/plain.md", b"x")
    _write_manifest(work_tree, {"plain.md": {"protected_by": "nothing"}})

    (entry,) = corpus_loader(work_tree.path("corpus"))

    with pytest.raises(KeyError, match="expected_policy"):
        entry.annotation("expected_policy")


def test_corpus_loader_requires_a_manifest(work_tree, corpus_loader):
    work_tree.write_bytes("corpus/plain.md", b"x")

    with pytest.raises(FileNotFoundError, match="manifest.json"):
        corpus_loader(work_tree.path("corpus"))


def test_corpus_loader_requires_the_directory_to_exist(work_tree, corpus_loader):
    with pytest.raises(FileNotFoundError, match="corpus"):
        corpus_loader(work_tree.path("corpus"))


def test_corpus_root_points_at_the_suite_corpus_directory(corpus_root):
    # design.md "File Structure Plan" — tests/corpus/{preservation,carriers}.
    assert corpus_root.name == "corpus"
    assert corpus_root.parent == Path(__file__).resolve().parent
