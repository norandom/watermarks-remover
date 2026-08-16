#!/usr/bin/env bash
# Re-vendor the cleaning machinery from the upstream watermarks-remover repo.
#
# The vendored files in src/wm_hook/_vendor/ are BYTE-EXACT copies of
# service/scripts/ at the pinned upstream ref below — never edit them in
# place. To take upstream changes: bump PINNED_REF, run ./refresh.sh, review
# the per-file change summary, run your tests, commit.
#
# Usage:
#   ./refresh.sh           # fetch files at PINNED_REF + rewrite VENDORED.json
#   ./refresh.sh --check   # verify vendored files match VENDORED.json (no network)
set -euo pipefail

UPSTREAM_REPO="guillaumemeyer/watermarks-remover"
PINNED_REF="fcebf533583d7a313b348dbe421f3b4b17163b66"

DST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/src/wm_hook/_vendor"

# container_meta imports AI_META_HINTS/C2PA_MARKERS/run_optional_tools from
# image_meta, so image_meta must be vendored even though the hook never calls
# the image pipeline.
FILES=(common.py text_unicode.py container_meta.py image_meta.py)

if [[ "${1:-}" == "--check" ]]; then
    python3 - "$DST" "${FILES[@]}" <<'EOF'
import hashlib
import json
import sys
from pathlib import Path

dst = Path(sys.argv[1])
files = sys.argv[2:]
manifest = json.loads((dst / "VENDORED.json").read_text(encoding="utf-8"))
rc = 0
for f in files:
    actual = hashlib.sha256((dst / f).read_bytes()).hexdigest()
    if actual != manifest["sha256"].get(f):
        print(f"DRIFT: {f} does not match VENDORED.json", file=sys.stderr)
        rc = 1
sys.exit(rc)
EOF
    exit $?
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

for f in "${FILES[@]}"; do
    url="https://raw.githubusercontent.com/$UPSTREAM_REPO/$PINNED_REF/service/scripts/$f"
    curl -fsSL --proto '=https' --tlsv1.2 "$url" -o "$TMP/$f"
done

python3 - "$TMP" "$DST" "$UPSTREAM_REPO" "$PINNED_REF" "${FILES[@]}" <<'EOF'
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

tmp, dst = Path(sys.argv[1]), Path(sys.argv[2])
repo, ref = sys.argv[3], sys.argv[4]
files = sys.argv[5:]

old = json.loads((dst / "VENDORED.json").read_text(encoding="utf-8"))
new_hashes = {}
for f in files:
    data = (tmp / f).read_bytes()
    new_hashes[f] = hashlib.sha256(data).hexdigest()
    status = "UNCHANGED" if old["sha256"].get(f) == new_hashes[f] else "UPDATED"
    print(f"{status}: {f}")
    (dst / f).write_bytes(data)

manifest = {
    "source": f"{repo} service/scripts/ @ pinned ref (byte-exact copies; refresh with refresh.sh)",
    "upstream_repo": repo,
    "upstream_ref": ref,
    "refreshed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "sha256": new_hashes,
}
(dst / "VENDORED.json").write_text(
    json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
)
EOF
