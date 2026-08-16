"""The vendored-constant gateway: completeness, identity, and import purity.

``wm_hook._tables`` is the only owned module allowed to reach into
``_vendor/`` (design.md "Boundary Commitments / Allowed Dependencies"). Two
properties make it worth its own module, and both are asserted here rather
than assumed:

* **It really is the whole gateway.** Every module-level constant table in
  ``_vendor/text_unicode.py`` is re-exported, and each re-export is the *same
  object* as upstream's. Introspecting the vendored module rather than
  restating a list means an upstream ``refresh.sh`` bump that adds a table
  fails here instead of silently leaving owned code with a stale inventory.

* **It costs nothing to import.** design.md's measured import-cost table
  permits ``text_unicode`` (standalone, side-effect free) and forbids
  ``container_meta``/``common`` in production, because those mutate process
  stdio to UTF-8 and pull ``image_meta`` with them. The purity check runs in a
  bare subprocess — the command-line entry point never imported — and a
  companion control imports ``container_meta`` in the same shape to prove the
  purity assertion can actually fail.

Codepoints are written as integers throughout. A literal invisible character
in this file would be rewritten by this repository's own pre-commit hook.
"""

from __future__ import annotations

import importlib
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from wm_hook import _tables

SRC_DIR = Path(__file__).resolve().parent.parent / "src"

#: Types a module-level constant table can have. Predicates and dataclasses in
#: the vendored module are callables/classes and are excluded by construction.
TABLE_TYPES = (frozenset, set, dict, range, tuple, list, re.Pattern)

#: Modules design.md forbids the gateway from pulling in, plus the entry point
#: the observable requires stay unimported.
FORBIDDEN_MODULES = ("common", "container_meta", "image_meta", "wm_hook.cli")


def vendored_text_unicode() -> ModuleType:
    """The vendored table module, by the bare name the gateway makes work."""
    return importlib.import_module("text_unicode")


def vendored_table_names(module: ModuleType) -> set[str]:
    """Every module-level constant table in *module*, by upstream name."""
    return {
        name
        for name, value in vars(module).items()
        if not name.startswith("__") and isinstance(value, TABLE_TYPES)
    }


def run_probe(body: str) -> dict:
    """Run *body* in a bare interpreter and return the JSON object it prints.

    The child gets ``src/`` through an explicit ``sys.path`` insertion rather
    than an environment variable, so the probe describes a plain process that
    has merely imported the package — not one configured to make the result
    come out right.
    """
    code = f"import json, sys\nSRC = {str(SRC_DIR)!r}\n{body}"
    completed = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    assert completed.returncode == 0, (
        f"probe exited {completed.returncode}\n"
        f"--- stdout ---\n{completed.stdout}\n--- stderr ---\n{completed.stderr}"
    )
    return json.loads(completed.stdout)


#: Captures stdio state before and after the import under test. ``errors`` is
#: recorded alongside ``encoding`` because ``common._configure_stdio`` changes
#: both, and on a host whose console codec is already UTF-8 only ``errors``
#: would move.
_PROBE_PREAMBLE = """
def stdio():
    return [
        sys.stdout.encoding, sys.stdout.errors,
        sys.stderr.encoding, sys.stderr.errors,
    ]

before = stdio()
sys.path.insert(0, SRC)
"""


class TestGatewayCompleteness:
    def test_reexports_every_vendored_table(self) -> None:
        """__all__ is exactly the vendored table inventory — no more, no less."""
        module = vendored_text_unicode()
        expected = vendored_table_names(module)
        assert expected, "found no constant tables in the vendored module"
        assert set(_tables.__all__) == expected

    def test_reexports_are_the_vendored_objects(self) -> None:
        """Each re-export is upstream's object, not a copy that can drift."""
        module = vendored_text_unicode()
        for name in sorted(vendored_table_names(module)):
            assert getattr(_tables, name) is getattr(module, name), name

    def test_exports_the_tables_the_design_names(self) -> None:
        """design.md "Allowed Dependencies" names these explicitly."""
        for name in (
            "STRIP_CODEPOINTS",
            "SPACE_HOMOGLYPHS",
            "LATIN_CONFUSABLES",
            "_ORTHOGRAPHIC_CF",
            "_VS_SUPPLEMENT",
            "_BIDI_CPS",
            "_PRESERVABLE_BIDI_CPS",
            "_SCRIPT_GLUE",
            "_SCRIPT_JOINERS",
        ):
            assert name in _tables.__all__, name

    def test_tables_carry_their_expected_contents(self) -> None:
        """Spot-check that the gateway hands over data, not empty placeholders."""
        assert 0x200B in _tables.STRIP_CODEPOINTS  # zero width space
        assert _tables.SPACE_HOMOGLYPHS[0x00A0] == " "  # no-break space
        assert _tables.LATIN_CONFUSABLES[0x0430] == "a"  # Cyrillic small a
        assert 0xE0100 in _tables._VS_SUPPLEMENT  # VS17
        assert 0x0600 in _tables._ORTHOGRAPHIC_CF  # Arabic number sign
        assert 0x202E in _tables._BIDI_CPS  # RLO
        assert 0x200F not in (_tables._BIDI_CPS - _tables._PRESERVABLE_BIDI_CPS)
        assert 0x115F in _tables._SCRIPT_GLUE  # Hangul choseong filler


class TestImportPurity:
    def test_import_is_free_of_stdio_and_forbidden_modules(self) -> None:
        """The observable: a bare process importing the gateway stays pristine."""
        payload = run_probe(
            _PROBE_PREAMBLE
            + """
import wm_hook._tables as tables

print(json.dumps({
    "before": before,
    "after": stdio(),
    "loaded": sorted(m for m in %r if m in sys.modules),
    "vendored_table_module_loaded": "text_unicode" in sys.modules,
    "tables_populated": 0x200B in tables.STRIP_CODEPOINTS,
}))
"""
            % (FORBIDDEN_MODULES,)
        )

        assert payload["loaded"] == []
        assert payload["before"] == payload["after"]
        assert payload["before"][0] == payload["after"][0]  # stdout encoding
        assert payload["vendored_table_module_loaded"] is True
        assert payload["tables_populated"] is True

    def test_the_purity_check_can_fail(self) -> None:
        """Control: the forbidden import does move the stdio state we watch.

        Without this, an assertion that stdio is unchanged would pass even if
        the gateway imported everything in sight.
        """
        payload = run_probe(
            _PROBE_PREAMBLE
            + """
import wm_hook._tables  # noqa: F401  (path insertion the bare names need)
import container_meta  # noqa: F401  (the module design.md forbids)

print(json.dumps({
    "before": before,
    "after": stdio(),
    "loaded": sorted(m for m in %r if m in sys.modules),
}))
"""
            % (FORBIDDEN_MODULES,)
        )

        assert payload["before"] != payload["after"]
        assert payload["loaded"] == ["common", "container_meta", "image_meta"]
