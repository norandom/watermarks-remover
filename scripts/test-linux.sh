#!/usr/bin/env bash
# Run the test suite on real Linux, via Dagger.
#
# Why this exists: the development host is Windows, which reports every
# writable file as 0o666 and has no os.fchmod. Requirement 8.1 -- the
# executable bit surviving a rewrite -- cannot be observed there, so eight of
# tests/test_atomic.py's assertions skip. A skipped test is not coverage.
#
# Dagger rather than raw docker, so the same pipeline runs unchanged on a
# workstation and on any CI runner. It needs only a container runtime.
#
# On a Windows workstation, invoke through the Debian WSL distro:
#
#   wsl.exe -d Debian -- bash /mnt/c/path/to/repo/scripts/test-linux.sh
#
# Never use the Debian-MW distro; it is reserved for other work.
#
# Note on symlinks: test_atomic.py's symlink assertions also skip on Windows,
# but that is not a coverage gap -- Windows only supports symlinks in developer
# mode, so they are atypical there. The refusal is a POSIX security property
# and is exercised here.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${WM_LINUX_IMAGE:-python:3.12-slim}"

DAGGER="${DAGGER:-dagger}"
command -v "$DAGGER" >/dev/null 2>&1 || DAGGER="$HOME/.local/bin/dagger"
if ! command -v "$DAGGER" >/dev/null 2>&1; then
    echo "dagger not found. Install: curl -fsSL https://dl.dagger.io/dagger/install.sh | BIN_DIR=\"\$HOME/.local/bin\" sh" >&2
    exit 127
fi

cd "$REPO_ROOT"

# Only the paths the suite reads are uploaded. .gitattributes and
# .pre-commit-hooks.yaml are not incidental: corpus tests assert the fixtures
# are pinned against CRLF translation and excluded from this repo's own hook.
#
# -ra surfaces skips. On Linux there should be none: a skip here means a
# platform gate is misfiring and an assertion is silently not running.
"$DAGGER" --progress=plain core \
    container \
    from --address="$IMAGE" \
    with-directory --path=/w/src --source=./src \
    with-directory --path=/w/tests --source=./tests \
    with-file --path=/w/pyproject.toml --source=./pyproject.toml \
    with-file --path=/w/.gitattributes --source=./.gitattributes \
    with-file --path=/w/.pre-commit-hooks.yaml --source=./.pre-commit-hooks.yaml \
    with-workdir --path=/w \
    with-env-variable --name=PYTHONDONTWRITEBYTECODE --value=1 \
    with-exec --args=pip,install,--quiet,--disable-pip-version-check,pytest \
    with-exec --args=python,-m,pytest,-q,-ra,-p,no:cacheprovider \
    stdout
