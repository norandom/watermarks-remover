"""The default report.

Printing one block per file buried ten real findings under forty lines of "all
legitimate", and never answered the question a reader has after a clean run:
was there any invisible material here at all? These tests pin the shape that
fixed it.
"""

from __future__ import annotations

import pytest

from wm_hook.cli import detect


def tag_block(s: str) -> str:
    return "".join(chr(0xE0000 + ord(c)) for c in s)


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "plain.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "emoji.md").write_text("hi ☀️\n", encoding="utf-8")
    (tmp_path / "marked.md").write_text(
        "Shipped." + tag_block("gen=claude") + "\n", encoding="utf-8")
    return tmp_path


def _run(paths, capsys, **kw):
    kw.setdefault("as_json", False)
    kw.setdefault("verbose", False)
    code = detect(list(paths), **kw)
    return code, capsys.readouterr().out


def test_default_reports_counts_not_one_block_per_file(tree, capsys):
    code, out = _run(sorted(tree.iterdir()), capsys)
    assert code == 1
    # The counts answer "was anything invisible here", which a list of clean
    # files never did.
    assert "3 file(s) scanned" in out
    assert "no invisible characters at all" in out
    assert "invisible characters, all legitimate" in out
    assert "hidden data found" in out


def test_default_does_not_print_clean_files(tree, capsys):
    _, out = _run(sorted(tree.iterdir()), capsys)
    assert "plain.py" not in out
    assert "emoji.md" not in out


def test_default_names_only_the_files_that_carry_something(tree, capsys):
    _, out = _run(sorted(tree.iterdir()), capsys)
    assert "marked.md" in out
    assert "reads: 'gen=claude'" in out


def test_the_caveat_appears_exactly_once(tree, capsys):
    # It used to be repeated under every single finding.
    _, out = _run(sorted(tree.iterdir()), capsys)
    assert out.count("does not mean a human wrote") == 1


def test_a_fully_clean_run_says_so_without_listing_anything(tmp_path, capsys):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    code, out = _run([tmp_path / "a.py"], capsys)
    assert code == 0
    assert "No hidden data in 1 file(s)." in out
    assert "Files with hidden data" not in out


def test_verbose_restores_the_per_file_reasons(tree, capsys):
    _, out = _run(sorted(tree.iterdir()), capsys, verbose=True)
    assert "tag_outside_flag" in out
    assert "CARRIER!" in out


def test_verbose_still_omits_files_with_nothing_invisible(tree, capsys):
    _, out = _run(sorted(tree.iterdir()), capsys, verbose=True)
    assert "plain.py" not in out


def test_json_output_is_unaffected_by_the_summary_rewrite(tree, capsys):
    import json

    code, out = _run(sorted(tree.iterdir()), capsys, as_json=True)
    data = json.loads(out)
    assert code == 1
    assert len(data) == 3
    assert sum(d["carrier_present"] for d in data) == 1


def test_scanning_nothing_is_an_error_not_a_clean_bill(tmp_path, capsys):
    code, out = _run([], capsys)
    assert code == 2
    assert "No hidden data" not in out
