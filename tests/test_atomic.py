"""The write path: mode preservation, symlink refusal, all-or-nothing writes.

``wm_hook.atomic.write_atomic`` exists to fix one concrete regression. The
vendored ``common.safe_write_bytes`` chmods its temporary to the umask default
(``0o666 & ~umask``), so a cleaned file comes back ``0644``. The hook's
``files:`` pattern matches ``.sh`` and ``.py``, git tracks the execute bit, and
so cleaning an executable script used to smuggle a ``100755 -> 100644`` mode
change into the commit. Requirement 8.1 forbids exactly that.

**What this suite can and cannot observe on Windows.** Requirement 8.1 is a
POSIX-mode claim, and Windows has neither mode bits nor ``os.fchmod``: it
reports every writable file as ``0o666``, refuses ``os.replace`` over a
read-only file, and -- without the symlink-creation privilege -- cannot make a
link to refuse. The suite is therefore split deliberately:

* Tests marked :data:`requires_posix_modes` make the *real* filesystem claim --
  chmod ``0o755``, rewrite, read the mode back. They are the direct evidence
  for Requirement 8.1 and run on POSIX CI.
* The portable tests drive the same code path with the platform's answers faked
  at their source: :func:`fake_lstat_mode` makes ``os.lstat`` report the mode or
  file type the host cannot hold, and a spy stands in for ``os.fchmod``. These
  prove the capture-and-restore *plumbing* -- that the mode handed to ``fchmod``
  is the one read off the original, not a umask default -- which is precisely
  the defect being fixed. They cannot prove the kernel honours it.

Both halves are needed: the portable half fails loudly on any host if the
plumbing regresses, and the POSIX half closes the gap the faking leaves open.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from wm_hook import atomic

if TYPE_CHECKING:  # the harness types, without depending on how pytest imports it
    from tests.conftest import WorkTree

#: The genuinely POSIX-only assertions: a real mode, really restored.
requires_posix_modes = pytest.mark.skipif(
    not hasattr(os, "fchmod"),
    reason="platform has no POSIX file modes (os.fchmod is absent)",
)

SCRIPT = b"#!/bin/sh\necho original\n"
CLEANED = b"#!/bin/sh\necho cleaned\n"


def default_file_mode() -> int:
    """The umask default the vendored writer applies -- the behaviour we reject.

    Read by the round trip ``os.umask`` requires; there is no getter.
    """
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def file_mode(path: Path) -> int:
    """The permission bits of *path*, without the file-type bits."""
    return stat.S_IMODE(os.lstat(path).st_mode)


def directory_entries(directory: Path) -> list[str]:
    """Every name in *directory*, sorted -- a leftover temporary shows up here."""
    return sorted(entry.name for entry in directory.iterdir())


def fake_lstat_mode(
    monkeypatch: pytest.MonkeyPatch, target: Path, st_mode: int
) -> None:
    """Make ``os.lstat`` report *st_mode* for *target* only.

    Windows cannot hold a ``0o755`` file, and this host cannot create a symlink
    to refuse, so the one platform answer the production code reads is
    substituted at its source. Every other path -- including whatever
    ``tempfile`` and pytest stat along the way -- is delegated untouched, so the
    write under test is otherwise entirely real.
    """
    real_lstat = os.lstat
    target_name = os.fspath(target)

    def patched(path: Any, *args: Any, **kwargs: Any) -> os.stat_result:
        result = real_lstat(path, *args, **kwargs)
        try:
            is_target = os.fspath(path) == target_name
        except TypeError:  # an open descriptor, never our target
            return result
        if not is_target:
            return result
        fields = list(result)
        fields[0] = st_mode
        return os.stat_result(tuple(fields))

    monkeypatch.setattr(os, "lstat", patched)


def spy_on_fchmod(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int]]:
    """Record every ``os.fchmod(fd, mode)`` call and suppress the real one.

    Installed with ``raising=False`` so it also *creates* ``os.fchmod`` on
    Windows, where the attribute does not exist -- that is what lets the
    restoration path be exercised at all on this platform.
    """
    calls: list[tuple[int, int]] = []

    def record(fd: int, mode: int) -> None:
        os.fstat(fd)  # the descriptor must still be open when we are called
        calls.append((fd, mode))

    monkeypatch.setattr(os, "fchmod", record, raising=False)
    return calls


@pytest.fixture
def symlink_support(tmp_path: Path) -> None:
    """Skip unless this host can actually create a symbolic link."""
    probe_target = tmp_path / "symlink-probe-target"
    probe_target.write_bytes(b"")
    try:
        (tmp_path / "symlink-probe-link").symlink_to(probe_target)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - host dependent
        pytest.skip(f"this host cannot create symbolic links: {exc}")


@pytest.fixture
def script(work_tree: WorkTree) -> Path:
    """An existing regular file, alone in the working tree."""
    return work_tree.write_bytes("script.sh", SCRIPT)


class TestContentReplacement:
    """The baseline contract: exactly these bytes, and nothing else left over."""

    def test_replaces_the_contents_with_the_exact_bytes(self, script: Path) -> None:
        assert atomic.write_atomic(script, CLEANED) is None
        assert script.read_bytes() == CLEANED

    def test_writes_bytes_verbatim_without_newline_translation(
        self, work_tree: WorkTree
    ) -> None:
        """A text-mode handle would turn every LF into CRLF on Windows."""
        target = work_tree.write_bytes("doc.md", b"placeholder")
        payload = b"first\r\nsecond\nthird\r\n"
        atomic.write_atomic(target, payload)
        assert target.read_bytes() == payload

    def test_accepts_an_empty_payload(self, script: Path) -> None:
        atomic.write_atomic(script, b"")
        assert script.read_bytes() == b""

    def test_leaves_no_temporary_behind_on_success(
        self, work_tree: WorkTree, script: Path
    ) -> None:
        atomic.write_atomic(script, CLEANED)
        assert directory_entries(work_tree.root) == ["script.sh"]

    def test_stages_the_temporary_in_the_destination_directory(
        self, monkeypatch: pytest.MonkeyPatch, script: Path
    ) -> None:
        """Atomicity rests on this: ``os.replace`` is only atomic within one
        filesystem, so the temporary must be a sibling of the target."""
        real_replace = os.replace
        sources: list[Path] = []

        def record(src: Any, dst: Any, **kwargs: Any) -> None:
            sources.append(Path(os.fspath(src)))
            real_replace(src, dst, **kwargs)

        monkeypatch.setattr(os, "replace", record)
        atomic.write_atomic(script, CLEANED)

        assert len(sources) == 1
        assert sources[0].parent == script.parent
        assert sources[0].name != script.name


class TestModePreservation:
    """Requirement 8.1 -- the mode on disk before the write is the mode after."""

    @requires_posix_modes
    @pytest.mark.parametrize("original_mode", [0o755, 0o700, 0o640])
    def test_the_original_mode_survives_a_rewrite(
        self, script: Path, original_mode: int
    ) -> None:
        if original_mode == default_file_mode():
            pytest.skip(
                "this umask makes the buggy default indistinguishable from the "
                f"mode under test ({original_mode:o})"
            )
        os.chmod(script, original_mode)

        atomic.write_atomic(script, CLEANED)

        assert file_mode(script) == original_mode
        assert script.read_bytes() == CLEANED

    @requires_posix_modes
    def test_the_executable_bit_survives_a_rewrite(self, script: Path) -> None:
        """The regression in one line: an executable script stays executable.

        Non-vacuous by construction -- ``0o666 & ~umask`` can never carry an
        execute bit, so no umask makes this pass by accident.
        """
        os.chmod(script, 0o755)
        atomic.write_atomic(script, CLEANED)
        assert file_mode(script) & 0o111 == 0o111

    @pytest.mark.parametrize("original_mode", [0o755, 0o600])
    def test_restores_the_mode_read_off_the_original(
        self,
        monkeypatch: pytest.MonkeyPatch,
        script: Path,
        original_mode: int,
    ) -> None:
        """Portable: the mode handed to ``fchmod`` is the captured one.

        With the original reporting *original_mode*, a writer that applied the
        umask default instead is caught here on any platform.
        """
        fake_lstat_mode(monkeypatch, script, stat.S_IFREG | original_mode)
        calls = spy_on_fchmod(monkeypatch)

        atomic.write_atomic(script, CLEANED)

        assert [mode for _fd, mode in calls] == [original_mode]
        assert script.read_bytes() == CLEANED

    def test_restoration_targets_the_staged_file_before_the_move(
        self, monkeypatch: pytest.MonkeyPatch, script: Path
    ) -> None:
        """The chmod lands on the staged descriptor, before it is moved into
        place -- so the file never appears at its destination with the wrong
        mode, however briefly."""
        fake_lstat_mode(monkeypatch, script, stat.S_IFREG | 0o755)
        calls = spy_on_fchmod(monkeypatch)
        moved: list[str] = []
        real_replace = os.replace

        def record(src: Any, dst: Any, **kwargs: Any) -> None:
            assert calls, "the mode was restored after the move, not before it"
            moved.append(os.fspath(src))
            real_replace(src, dst, **kwargs)

        monkeypatch.setattr(os, "replace", record)
        atomic.write_atomic(script, CLEANED)

        assert len(moved) == 1
        assert isinstance(calls[0][0], int)  # a descriptor, not a path

    def test_skips_restoration_on_a_platform_without_posix_modes(
        self, monkeypatch: pytest.MonkeyPatch, work_tree: WorkTree, script: Path
    ) -> None:
        """Windows has no ``os.fchmod``; the write must still complete."""
        monkeypatch.delattr(os, "fchmod", raising=False)
        assert not hasattr(os, "fchmod")

        atomic.write_atomic(script, CLEANED)

        assert script.read_bytes() == CLEANED
        assert directory_entries(work_tree.root) == ["script.sh"]


class TestSymlinkRefusal:
    """Requirement 8.3 -- a pre-placed link must not redirect the write."""

    def test_refuses_a_real_symbolic_link(
        self, symlink_support: None, work_tree: WorkTree
    ) -> None:
        victim = work_tree.write_bytes("victim.txt", b"victim contents\n")
        link = work_tree.root / "link.sh"
        link.symlink_to(victim)

        with pytest.raises(OSError, match="symlink"):
            atomic.write_atomic(link, CLEANED)

        assert victim.read_bytes() == b"victim contents\n"
        assert link.is_symlink()
        assert directory_entries(work_tree.root) == ["link.sh", "victim.txt"]

    def test_refuses_a_target_that_reports_as_a_symbolic_link(
        self, monkeypatch: pytest.MonkeyPatch, work_tree: WorkTree, script: Path
    ) -> None:
        """Portable stand-in for the above on hosts that cannot create links."""
        fake_lstat_mode(monkeypatch, script, stat.S_IFLNK | 0o777)

        with pytest.raises(OSError, match="symlink"):
            atomic.write_atomic(script, CLEANED)

        assert script.read_bytes() == SCRIPT
        assert directory_entries(work_tree.root) == ["script.sh"]

    def test_refusal_happens_before_anything_is_staged(
        self, monkeypatch: pytest.MonkeyPatch, script: Path
    ) -> None:
        """No temporary is created at all -- not one that is cleaned up after."""
        fake_lstat_mode(monkeypatch, script, stat.S_IFLNK | 0o777)

        def forbidden(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("a temporary was staged for a symlink target")

        monkeypatch.setattr(atomic.tempfile, "mkstemp", forbidden)
        monkeypatch.setattr(os, "replace", forbidden)

        with pytest.raises(OSError, match="symlink"):
            atomic.write_atomic(script, CLEANED)


class _PartialWriteHandle:
    """A binary handle that writes half its payload and then fails.

    ``io.BufferedWriter`` rejects attribute assignment, so a partial-write
    failure has to be induced through a delegating wrapper rather than by
    patching ``write`` onto the real handle.
    """

    def __init__(self, handle: Any, error: OSError) -> None:
        self._handle = handle
        self._error = error

    def __enter__(self) -> _PartialWriteHandle:
        self._handle.__enter__()
        return self

    def __exit__(self, *exc_info: Any) -> Any:
        return self._handle.__exit__(*exc_info)

    def write(self, data: bytes) -> int:
        self._handle.write(data[: len(data) // 2])
        raise self._error

    def __getattr__(self, name: str) -> Any:
        return getattr(self._handle, name)


class TestFailureLeavesTheOriginalIntact:
    """Requirement 8.2 -- all of the write, or none of it."""

    #: Readable case name -> the step of the write to break, in order.
    FAILING_STEPS = {
        "1-partial-write": "write",
        "2-flush-to-disk": "fsync",
        "3-move-into-place": "replace",
    }

    @pytest.fixture(params=sorted(FAILING_STEPS))
    def induced_failure(
        self, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
    ) -> str:
        """Break exactly one step of the write with a plausible I/O error."""
        step = self.FAILING_STEPS[request.param]
        boom = OSError(28, "No space left on device")

        if step == "write":
            real_fdopen = os.fdopen

            def failing_fdopen(fd: int, *args: Any, **kwargs: Any) -> Any:
                return _PartialWriteHandle(real_fdopen(fd, *args, **kwargs), boom)

            monkeypatch.setattr(os, "fdopen", failing_fdopen)
        else:

            def failing(*args: Any, **kwargs: Any) -> None:
                raise boom

            monkeypatch.setattr(os, step, failing)
        return request.param

    def test_the_original_bytes_and_mode_are_untouched(
        self, induced_failure: str, work_tree: WorkTree, script: Path
    ) -> None:
        mode_before = file_mode(script)

        with pytest.raises(OSError):
            atomic.write_atomic(script, CLEANED)

        assert script.read_bytes() == SCRIPT, induced_failure
        assert file_mode(script) == mode_before
        assert directory_entries(work_tree.root) == ["script.sh"]

    @requires_posix_modes
    def test_an_executable_original_keeps_its_mode_after_a_failure(
        self, induced_failure: str, script: Path
    ) -> None:
        os.chmod(script, 0o755)

        with pytest.raises(OSError):
            atomic.write_atomic(script, CLEANED)

        assert file_mode(script) == 0o755
        assert script.read_bytes() == SCRIPT

    def test_a_failure_after_the_move_cannot_undo_it(
        self, monkeypatch: pytest.MonkeyPatch, work_tree: WorkTree, script: Path
    ) -> None:
        """The move is the commit point: once it returns, the new bytes are the
        file's bytes and the cleanup path must not delete them."""
        real_replace = os.replace
        moved: list[str] = []

        def replace_then_fail(src: Any, dst: Any, **kwargs: Any) -> None:
            real_replace(src, dst, **kwargs)
            moved.append(os.fspath(dst))
            raise KeyboardInterrupt("interrupted immediately after the move")

        monkeypatch.setattr(os, "replace", replace_then_fail)

        with pytest.raises(KeyboardInterrupt):
            atomic.write_atomic(script, CLEANED)

        assert moved, "the move never happened"
        assert script.read_bytes() == CLEANED
        assert directory_entries(work_tree.root) == ["script.sh"]

    def test_a_missing_target_is_refused_and_creates_nothing(
        self, work_tree: WorkTree
    ) -> None:
        """The precondition is that the path exists (design.md, atomic.py): with
        no original there is no mode to capture, so there is nothing safe to
        write."""
        with pytest.raises(FileNotFoundError):
            atomic.write_atomic(work_tree.path("absent.sh"), CLEANED)

        assert directory_entries(work_tree.root) == []
