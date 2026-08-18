#!/usr/bin/env bash
# Print one CHANGELOG.md section as plain markdown, for a GitHub release body.
#
#   scripts/changelog-section.sh 0.1.4
#   scripts/changelog-section.sh Unreleased
#
set -euo pipefail

want="${1:?usage: changelog-section.sh <version|Unreleased>}"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
changelog_md="$root/CHANGELOG.md"

[ -f "$changelog_md" ] || { echo "::error::$changelog_md is missing" >&2; exit 1; }

out="$(awk -v want="$want" '
    function hdrver(s,   i) {
        sub(/^##[ \t]+/, "", s)
        if (substr(s, 1, 1) == "[") {
            s = substr(s, 2); i = index(s, "]")
            if (i > 0) s = substr(s, 1, i - 1)
        } else { i = index(s, " "); if (i > 0) s = substr(s, 1, i - 1) }
        return s
    }
    /^## / { insec = (hdrver($0) == want); next }
    insec  { print }
' "$changelog_md" | sed -e '/./,$!d' | tac | sed -e '/./,$!d' | tac)"

[ -n "$out" ] || { echo "::error::CHANGELOG.md has no [$want] section, or it is empty" >&2; exit 1; }
printf '%s\n' "$out"
