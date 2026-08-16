#!/usr/bin/env bash
# Build and verify a release, in a container, via Dagger.
#
# Implements Requirement 5 of .kiro/specs/ci-pipeline. The ordering is the
# whole point: nothing is published until every gate has passed for the exact
# commit being released, and the gates run on real Linux rather than on the
# Windows development host, where eight write-path assertions silently skip.
#
#   scripts/release.sh 0.1.0a1              verify and build only
#   scripts/release.sh 0.1.0a1 --publish    ... then tag and publish
#
# On a Windows workstation, invoke the build through the Debian WSL distro and
# publish from PowerShell:
#
#   wsl.exe -d Debian -- bash /mnt/c/path/to/repo/scripts/release.sh 0.1.0a1
#
# Never use the Debian-MW distro; it is reserved for other work.
#
# --publish is deliberately NOT used on the Windows path. git inside WSL,
# reading a working tree on /mnt/c, reports spurious modifications against a
# tree that Windows git calls clean. A release gate that cannot trust "is the
# tree clean" is not a gate, so tagging is driven from the Windows side where
# git is authoritative. On a Linux CI runner there is no such split and
# --publish does the whole thing.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${WM_LINUX_IMAGE:-python:3.12-slim}"
PUBLISH=0
VERSION="${1:-}"
shift || true
for arg in "$@"; do
    case "$arg" in
        --publish) PUBLISH=1 ;;
        *) echo "unknown argument: $arg" >&2; exit 2 ;;
    esac
done

step()  { printf '\n\033[1m== %s\033[0m\n' "$1"; }
fail()  { printf '\033[31mFAILED: %s\033[0m\n' "$1" >&2; exit 1; }

# --- Requirement 6.4: fail before doing any work, not partway through -------

[ -n "$VERSION" ] || fail "usage: release.sh <version> [--publish]"

DAGGER="${DAGGER:-dagger}"
command -v "$DAGGER" >/dev/null 2>&1 || DAGGER="$HOME/.local/bin/dagger"
command -v "$DAGGER" >/dev/null 2>&1 || fail \
    "dagger not found. curl -fsSL https://dl.dagger.io/dagger/install.sh | BIN_DIR=\"\$HOME/.local/bin\" sh"

if [ "$PUBLISH" = 1 ]; then
    command -v gh >/dev/null 2>&1 || fail "gh not found, and --publish needs it"
    # Requirement 6.3: credentials from the environment, never from the repo.
    gh auth status >/dev/null 2>&1 || [ -n "${GH_TOKEN:-}" ] || fail \
        "no GitHub credentials; set GH_TOKEN or run gh auth login"
fi

cd "$REPO_ROOT"

# --- Requirement 5.4: the declared version and the tag must agree -----------

step "version agreement"
# tr -d '\r' because on a Windows working tree pyproject.toml is CRLF, and the
# captured version would carry a trailing carriage return -- producing the
# uniquely unhelpful "declares 0.1.0a1 but asks for 0.1.0a1". A CI checkout is
# LF and would never show it, which is precisely why it has to be handled here.
DECLARED="$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1 | tr -d '\r')"
[ -n "$DECLARED" ] || fail "no version found in pyproject.toml"
if [ "$DECLARED" != "$VERSION" ]; then
    fail "pyproject declares $DECLARED but the release asks for $VERSION"
fi
echo "  pyproject and tag agree on $VERSION"

# --- Requirement 5.6: the tag must be usable as a rev: with no further steps -
#
# Which means the documented rev: has to be the tag actually being released.
# Pinning it by hand in six files is exactly the step a release forgets, and
# the failure is silent: the docs keep working, they just point at the wrong
# version. So it is a gate rather than a checklist item.

step "documentation pins this version"
PINNED=(README.md docs/usage/hook.md docs/usage/detect.md
        .pre-commit-hooks.yaml src/wm_hook/cli.py)
for f in "${PINNED[@]}"; do
    [ -f "$f" ] || fail "$f is missing"
    if grep -q '<tag>' "$f"; then
        fail "$f still contains the <tag> placeholder"
    fi
    grep -q "v$VERSION" "$f" || fail "$f does not reference v$VERSION"
done
echo "  ${#PINNED[@]} files pin v$VERSION"

# --- Requirement 5.3: refuse a version that is already published ------------
#
# "Published" means a release exists, not merely that a tag does. The two are
# different, and conflating them breaks the normal trigger: pushing v0.1.0a1
# is how a release starts, so by the time this runs in CI the tag necessarily
# already exists. Rejecting that would make the workflow reject its own cause.

step "version is unpublished"
TAG="v$VERSION"
TAG_EXISTS=0

if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
    TAG_EXISTS=1
    if [ "$(git rev-parse "$TAG^{commit}")" != "$(git rev-parse HEAD)" ]; then
        fail "tag $TAG exists but points at a different commit than HEAD"
    fi
    echo "  $TAG already exists and points at HEAD; releasing that"
else
    echo "  $TAG does not exist yet"
fi

if [ "$PUBLISH" = 1 ] && gh release view "$TAG" >/dev/null 2>&1; then
    fail "release $TAG is already published"
fi

# --- Requirements 2 and 4: verification on a POSIX host, in a container -----
#
# One `dagger core` chain builds the container, runs the suite, builds the
# distribution and inspects it. Splitting it into separate invocations would
# rebuild the image each time; the per-gate reporting comes from the script
# that runs inside instead, which names the gate it is on before running it.

step "verify and build on Linux (dagger)"

# Dagger's export merges into an existing directory rather than replacing it,
# so a stale wheel from an earlier build survives and `gh release create
# dist/*.whl` would then attach two different versions to one release. Caught
# exactly that way: a 0.1.0 wheel from the morning sitting beside 0.1.0a1.
rm -rf dist


GATES=$(cat <<'INNER'
set -eu
cd /w

echo "-- gate: test suite (-ra, so a skip is visible)"
# A skip on Linux means a platform gate is misfiring and an assertion is
# silently not running. That is why the Windows suite is not sufficient here.
python -m pytest -q -ra -p no:cacheprovider

echo "-- gate: pre-commit manifest is valid YAML with the expected hook ids"
python - <<'PY'
import sys
try:
    import yaml
except ImportError:
    sys.exit("PyYAML missing in the build image")
hooks = yaml.safe_load(open(".pre-commit-hooks.yaml"))
ids = {h["id"] for h in hooks}
missing = {"wm-hook", "wm-hook-check"} - ids
if missing:
    sys.exit(f"manifest is missing hook ids: {sorted(missing)}")
for h in hooks:
    for key in ("id", "name", "entry", "language"):
        if key not in h:
            sys.exit(f"hook {h.get('id')!r} lacks {key!r}")
print(f"   hook ids: {sorted(ids)}")
PY

echo "-- gate: build the distribution"
python -m build --outdir /w/dist >/dev/null

echo "-- gate: distribution declares no runtime dependencies"
# The stdlib-only guarantee is adopter-visible: it is why the hook can run in
# a pre-commit environment with nothing preinstalled.
python - <<'PY'
import pathlib, sys, zipfile
whl = next(pathlib.Path("/w/dist").glob("*.whl"))
with zipfile.ZipFile(whl) as z:
    meta = next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))
    deps = [l for l in z.read(meta).decode().splitlines()
            if l.startswith("Requires-Dist:")]
if deps:
    sys.exit("distribution declares runtime dependencies: " + "; ".join(deps))
print("   no Requires-Dist, stdlib only")
PY

echo "-- gate: distribution contains the modules the tool cannot run without"
python - <<'PY'
import pathlib, sys, zipfile
whl = next(pathlib.Path("/w/dist").glob("*.whl"))
required = {
    "wm_hook/cli.py", "wm_hook/carriers.py", "wm_hook/verdict.py",
    "wm_hook/payload.py", "wm_hook/discovery.py", "wm_hook/policy.py",
    "wm_hook/atomic.py", "wm_hook/regions.py",
    "wm_hook/core/text_unicode.py", "wm_hook/core/flags.py",
    "wm_hook/core/common.py",
}
with zipfile.ZipFile(whl) as z:
    names = set(z.namelist())
missing = sorted(required - names)
if missing:
    sys.exit(f"distribution is missing: {missing}")
print(f"   {len(required)} required modules present")
PY

echo "-- gate: the built wheel actually runs, from a clean install"
# Installing the artifact and exercising it is the only check that the console
# script, the package layout and the core/ path insertion all still line up.
python -m venv /tmp/probe
/tmp/probe/bin/pip install --quiet --disable-pip-version-check /w/dist/*.whl
printf 'clean text\n' > /tmp/clean.md
/tmp/probe/bin/wm-hook --detect /tmp/clean.md
printf 'carrier here\xf3\xa0\x81\xa7\xf3\xa0\x81\xa5\xf3\xa0\x81\xae\n' > /tmp/dirty.md
if /tmp/probe/bin/wm-hook --detect /tmp/dirty.md; then
    echo "   FAILED: --detect exited 0 on a file carrying a tag block" >&2
    exit 1
fi
echo "   installed wheel detects a carrier and exits 1"

echo "-- all gates passed"
INNER
)

"$DAGGER" --progress=plain core \
    container \
    from --address="$IMAGE" \
    with-directory --path=/w/src --source=./src \
    with-directory --path=/w/tests --source=./tests \
    with-file --path=/w/pyproject.toml --source=./pyproject.toml \
    with-file --path=/w/README.md --source=./README.md \
    with-file --path=/w/LICENSE --source=./LICENSE \
    with-file --path=/w/.gitattributes --source=./.gitattributes \
    with-file --path=/w/.pre-commit-hooks.yaml --source=./.pre-commit-hooks.yaml \
    with-workdir --path=/w \
    with-env-variable --name=PYTHONDONTWRITEBYTECODE --value=1 \
    with-exec --args=pip,install,--quiet,--disable-pip-version-check,pytest,build,pyyaml \
    with-new-file --path=/w/gates.sh --contents="$GATES" \
    with-exec --args=bash,/w/gates.sh \
    directory --path=/w/dist \
    export --path=./dist

echo "  artifacts exported to ./dist"
ls -1 dist

# Name the exact artifacts rather than globbing the directory, so what gets
# attached to the release cannot depend on what happens to be lying around.
WHEEL="$(ls dist/*-"$VERSION"-py3-none-any.whl 2>/dev/null || true)"
SDIST="$(ls dist/*-"$VERSION".tar.gz 2>/dev/null || true)"
[ -n "$WHEEL" ] || fail "no wheel built for $VERSION"
[ -n "$SDIST" ] || fail "no sdist built for $VERSION"
[ "$(printf '%s\n' $WHEEL | wc -l)" = 1 ] || fail "more than one wheel matches $VERSION"
echo "  releasing $(basename "$WHEEL") and $(basename "$SDIST")"

# --- Requirement 5.5: record what changed since the previous release --------

step "changelog since the previous release"
# --exclude, because when CI is triggered by the tag push the tag being
# released is itself the most recent one; without it the range is empty and
# the release notes come out blank.
PREV="$(git describe --tags --abbrev=0 --exclude="$TAG" 2>/dev/null || true)"
if [ -n "$PREV" ]; then
    RANGE="$PREV..HEAD"
    echo "  since $PREV"
else
    RANGE="HEAD"
    echo "  no previous tag; this is the first release"
fi
git log --no-merges --format='- %s' "$RANGE" | tee dist/CHANGELOG-"$VERSION".md

# --- Requirement 5.1, 5.2, 5.6 ----------------------------------------------

if [ "$PUBLISH" != 1 ]; then
    step "not publishing"
    echo "  gates passed and artifacts are built."
    echo "  Re-run with --publish, or tag and publish from the host."
    exit 0
fi

step "publish"
# A PEP 440 pre-release segment in the version is the single source of truth
# for the GitHub pre-release flag, so the two can never disagree.
PRERELEASE=""
case "$VERSION" in
    *a*|*b*|*rc*|*dev*) PRERELEASE="--prerelease" ;;
esac

if [ "$TAG_EXISTS" = 0 ]; then
    git tag -a "$TAG" -m "Release $TAG"
    git push origin "$TAG"
else
    echo "  reusing the existing $TAG"
fi
# shellcheck disable=SC2086
gh release create "$TAG" "$WHEEL" "$SDIST" \
    --title "$TAG" \
    --notes-file dist/CHANGELOG-"$VERSION".md \
    $PRERELEASE
echo "  published $TAG${PRERELEASE:+ (pre-release)}"
