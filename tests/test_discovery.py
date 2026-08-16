"""Expanding a directory into the files to look at.

The bug this prevents is not a crash. It is a directory argument producing
"0 of 0 file(s) carry a covert carrier" -- a reassuring summary for a scan that
never happened.
"""

from __future__ import annotations

from wm_hook.discovery import SKIP_DIRS, TEXT_EXTS, iter_text_files


def _tree(root):
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / "README.md").write_text("# hi\n", encoding="utf-8")
    (root / "logo.png").write_bytes(b"\x89PNG\r\n")
    (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
    for skip in (".git", "node_modules", "site"):
        d = root / skip
        d.mkdir()
        (d / "vendored.js").write_text("// not ours\n", encoding="utf-8")
    nested = root / "src" / "pkg"
    nested.mkdir(parents=True)
    (nested / "deep.py").write_text("y = 2\n", encoding="utf-8")
    return root


def test_a_directory_expands_to_its_text_files(tmp_path):
    found = {p.name for p in iter_text_files([_tree(tmp_path)])}
    assert found == {"a.py", "README.md", "deep.py"}


def test_third_party_directories_are_not_scanned(tmp_path):
    found = list(iter_text_files([_tree(tmp_path)]))
    assert not [p for p in found if set(p.parts) & SKIP_DIRS]


def test_binary_extensions_are_not_offered(tmp_path):
    assert ".png" not in TEXT_EXTS
    assert "logo.png" not in {p.name for p in iter_text_files([_tree(tmp_path)])}


def test_a_named_file_is_honoured_whatever_its_extension(tmp_path):
    # Asking for a specific file is an instruction. Filtering it would make the
    # tool unusable on LICENSE, Makefile, Dockerfile and every dotfile.
    _tree(tmp_path)
    for name in ("LICENSE", "logo.png"):
        assert list(iter_text_files([tmp_path / name])) == [tmp_path / name]


def test_a_file_named_twice_is_scanned_once(tmp_path):
    _tree(tmp_path)
    both = list(iter_text_files([tmp_path, tmp_path / "a.py"]))
    assert len(both) == len(set(both))


def test_mixed_files_and_directories_both_work(tmp_path):
    _tree(tmp_path)
    found = {p.name for p in iter_text_files([tmp_path / "src", tmp_path / "LICENSE"])}
    assert found == {"deep.py", "LICENSE"}


def test_an_empty_directory_yields_nothing_rather_than_erroring(tmp_path):
    (tmp_path / "empty").mkdir()
    assert list(iter_text_files([tmp_path / "empty"])) == []
