#!/usr/bin/env bash
# Find invisible characters with ripgrep or grep. No Python, no install.
#
# WHAT THIS IS NOT
#
# This is not wm-hook. It finds every invisible character and stops there. It
# has no explanation layer, so it cannot tell an emoji presentation selector
# from a payload, or Devanagari orthography from smuggled bytes.
#
# In the measured corpus that difference was two orders of magnitude: 29
# carriers found, 27 of them entirely legitimate. A tool that reports the first
# number as a detection rate is lying to you, and this script reports the first
# number. Treat a hit as "look at this", never as "something is hidden here".
#
# Use it when you cannot install anything, or to sanity-check that wm-hook is
# looking at the files you think it is. Use wm-hook for a verdict.
#
#   scripts/detect.sh [PATH]        default: .
#
# Exit 0 if nothing was found, 1 if anything was.
set -uo pipefail

TARGET="${1:-.}"

# Each class separately, so the output says what was found and not merely that
# something was. The ranges match wm_hook/carriers.py; keep them in step.
#
# Deliberately excluded: U+FE0F on its own is nearly always a real emoji
# selector, so it is reported in its own class rather than mixed in with the
# classes that are usually payload.
CLASSES=(
  "zero width|[\x{200B}\x{200C}\x{200D}\x{2060}\x{FEFF}]"
  "tag block|[\x{E0000}-\x{E007F}]"
  "private use|[\x{E000}-\x{F8FF}\x{F0000}-\x{FFFFD}\x{100000}-\x{10FFFD}]"
  "bidi control|[\x{200E}\x{200F}\x{061C}\x{202A}-\x{202E}\x{2066}-\x{2069}]"
  "variation selector|[\x{FE00}-\x{FE0F}\x{E0100}-\x{E01EF}]"
  "space homoglyph|[\x{00A0}\x{1680}\x{2000}-\x{200A}\x{202F}\x{205F}\x{3000}]"
)

if command -v rg >/dev/null 2>&1; then
    ENGINE=rg
elif echo | grep -qP '' 2>/dev/null; then
    # Probing against /dev/null looks right and is not: it has no lines, so
    # grep exits 1 for "no match" and the probe fails even where -P works.
    # Feed it one line instead. GNU grep has -P; BSD and macOS grep do not.
    ENGINE=grep
else
    echo "needs ripgrep, or a grep built with -P (PCRE)." >&2
    echo "macOS: brew install ripgrep" >&2
    exit 127
fi

search() {   # search <pattern>
    case "$ENGINE" in
        rg)
            rg --no-messages --with-filename --line-number --no-heading \
               --color=never --hidden \
               --glob '!.git' --glob '!node_modules' --glob '!.venv' \
               --glob '!dist' --glob '!build' --glob '!target' --glob '!site' \
               "$1" "$TARGET"
            ;;
        grep)
            # \x{...} is PCRE syntax and works in GNU grep -P as well.
            grep -rInP --binary-files=without-match \
                 --exclude-dir={.git,node_modules,.venv,dist,build,target,site} \
                 "$1" "$TARGET"
            ;;
    esac
}

total=0
for entry in "${CLASSES[@]}"; do
    name="${entry%%|*}"
    pattern="${entry#*|}"
    hits="$(search "$pattern" 2>/dev/null || true)"
    [ -n "$hits" ] || continue
    n="$(printf '%s\n' "$hits" | wc -l | tr -d ' ')"
    total=$((total + n))
    printf '\n== %s (%s)\n' "$name" "$n"
    # Just the locations. Printing the line would print an invisible character
    # into your terminal, which is how this problem started.
    printf '%s\n' "$hits" | cut -d: -f1,2 | sort -u | sed 's/^/   /' | head -40
    [ "$n" -gt 40 ] && printf '   ... and %s more\n' "$((n - 40))"
done

if [ "$total" -eq 0 ]; then
    echo "No invisible characters in $TARGET."
    echo "That is not proof a human wrote it. Statistical watermarks leave no"
    echo "character trace at all."
    exit 0
fi

cat <<EOF

$total line(s) contain invisible characters.

Most of these are legitimate. Emoji need variation selectors, Arabic and
Devanagari need joiners, and a byte-order mark is just an encoding signature.
This script cannot tell those apart from hidden data.

For a verdict rather than a list:
  uvx --from git+https://github.com/norandom/watermarks-remover@v0.1.0a1 \\
      wm-hook --detect $TARGET
EOF
exit 1
