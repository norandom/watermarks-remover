"""Replace a file's contents without changing anything else about the file.

This module exists because the vendored writer changes something else. Its
``safe_write_bytes`` chmods the temporary to ``0o666 & ~umask``, so every
rewritten file comes back ``0644``. The hook's ``files:`` pattern matches
``.sh`` and ``.py``, git tracks the execute bit, and the result is that
cleaning an executable script silently adds a ``100755 -> 100644`` mode change
to the commit -- an unrelated change, which Requirement 8 exists to forbid.

The fix is one line of intent: capture the original's mode and restore *that*
instead of a umask default. Everything around it is kept as the vendored
version had it, because those parts were already right -- a temporary in the
destination directory (so the move is a same-filesystem rename and therefore
atomic), ``fsync`` before the move, ``os.replace`` as the commit point, and a
refusal to write through a symbolic link.

The vendored function is not called or imported here. Importing
``_vendor.common`` reconfigures process stdin/stdout/stderr to UTF-8 as a side
effect (design.md "Allowed Dependencies"), and owning the write path is the
point of this module.
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

__all__ = ["write_atomic"]


def write_atomic(path: Path, data: bytes) -> None:
    """Replace the contents of *path* with *data*, preserving its mode.

    *path* must exist and be a regular file: its mode is the thing being
    preserved, so there is nothing to write safely without one. A symbolic
    link is refused rather than followed, so a pre-placed link cannot redirect
    the write onto an arbitrary victim file (Requirement 8.3).

    On failure the original is left exactly as it was and no temporary
    survives (Requirement 8.2). The move is the commit point: after it
    succeeds the new contents are the file's contents, and cleanup must not
    touch them.

    Raises:
        FileNotFoundError: *path* does not exist.
        OSError: *path* is a symbolic link, or the write itself failed.
    """
    dest = Path(path)

    # One lstat answers both questions -- is this a link, and what mode must
    # come back -- and answers them about the link itself, never its target.
    original = os.lstat(dest)
    if stat.S_ISLNK(original.st_mode):
        raise OSError(f"refusing to write through symlink: {dest}")
    original_mode = stat.S_IMODE(original.st_mode)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{dest.name}.", suffix=".tmp", dir=str(dest.parent)
    )
    try:
        # The descriptor is adopted immediately so that every exit from here
        # closes it. On Windows an open handle would block the cleanup unlink
        # and leave the temporary behind.
        with os.fdopen(fd, "wb") as handle:
            # mkstemp creates the temporary 0600. Restore the original's mode
            # before any bytes land, so the file is never visible at its
            # destination with the wrong permissions. Windows has no POSIX
            # mode bits and no os.fchmod, so restoration is skipped there.
            if hasattr(os, "fchmod"):
                os.fchmod(handle.fileno(), original_mode)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, dest)
    except BaseException:
        # BaseException, not Exception: a KeyboardInterrupt mid-write must not
        # leave a temporary either. If the move already succeeded, tmp_name no
        # longer exists and the unlink is a no-op -- the new contents stay.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
