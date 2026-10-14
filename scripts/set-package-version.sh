#!/usr/bin/env bash

set -euo pipefail

version="${1:?usage: set-package-version.sh <version>}"
case "$version" in
    [0-9]*) ;;
    *) echo "::error::version must start with a digit, got '$version'" >&2; exit 1 ;;
esac

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
changelog="$root/secureEye/debian/changelog"
spec="$root/secureEye/rpm/secure-eye.spec"
pkgbuild="$root/secureEye/archlinux/secureEye/PKGBUILD"
changelog_md="$root/CHANGELOG.md"

msg="${CHANGELOG_MSG:-New upstream release ${version}.}"
name="${DEBFULLNAME:-Vedran Hrabar}"
mail="${DEBEMAIL:-vedran.hrabar@outlook.com}"

# Render the CHANGELOG.md section for $1 in style $2 (deb|rpm).
render_changelog() {
    local want=$1 style=$2 out
    [ -f "$changelog_md" ] || return 1
    out="$(awk -v want="$want" -v style="$style" '
        # Version token out of a "## [1.2.3] - date" / "## 1.2.3" heading.
        function hdrver(s,   i) {
            sub(/^##[ \t]+/, "", s)
            if (substr(s, 1, 1) == "[") {
                s = substr(s, 2)
                i = index(s, "]")
                if (i > 0) s = substr(s, 1, i - 1)
            } else {
                i = index(s, " ")
                if (i > 0) s = substr(s, 1, i - 1)
            }
            return s
        }
        # Greedy wrap so generated entries stay inside 76 columns.
        function wrap(prefix, cont, text,   words, n, i, line, started) {
            n = split(text, words, /[ \t]+/)
            started = 0
            for (i = 1; i <= n; i++) {
                if (!started)                                    { line = prefix words[i]; started = 1 }
                else if (length(line) + 1 + length(words[i]) <= 76) { line = line " " words[i] }
                else                                             { print line; line = cont words[i] }
            }
            if (started) print line
        }
        function flush(   text) {
            if (buf == "") return
            if (style == "deb") {
                if (group != "") {
                    if (group != shown) { print "  * " group; shown = group }
                    wrap("    - ", "      ", buf)
                } else {
                    wrap("  * ", "    ", buf)
                }
            } else {
                text = (group != "") ? group ": " buf : buf
                wrap("- ", "  ", text)
            }
            buf = ""
        }
        /^## /   { flush(); insec = (hdrver($0) == want); group = ""; shown = ""; next }
        !insec   { next }
        /^### /  { flush(); group = $0; sub(/^###[ \t]+/, "", group); next }
        /^[ \t]*$/                { flush(); next }
        /^[ \t]*[-*][ \t]+/       { flush(); buf = $0; sub(/^[ \t]*[-*][ \t]+/, "", buf); next }
        # Anything else continues the current bullet, or starts a bare one.
        {
            line = $0; sub(/^[ \t]+/, "", line)
            buf = (buf == "") ? line : buf " " line
        }
        END { flush() }
    ' "$changelog_md")"
    [ -n "$out" ] || return 1
    printf '%s\n' "$out"
}

# Rename "## [Unreleased]" to "## [X.Y.Z] - <today>" and open a fresh empty unr
promote_unreleased() {
    local tmp
    render_changelog Unreleased deb >/dev/null || return 1
    tmp="$(mktemp)"
    awk -v ver="$version" -v today="$(date +%F)" '
        /^##[ \t]+\[?[Uu]nreleased\]?/ && !done {
            print "## [Unreleased]"
            print ""
            print "## [" ver "] - " today
            done = 1
            next
        }
        { print }
    ' "$changelog_md" > "$tmp"
    mv "$tmp" "$changelog_md"
    echo "CHANGELOG.md: promoted [Unreleased] -> [$version]"
}

# Date for $version, taken from its "## [X.Y.Z] - YYYY-MM-DD" heading so the
# generated entries are identical in CI, on COPR and locally. Nothing is
# committed back, so a clock-derived date would make every build differ.
entry_date() {
    local fmt=$1 d
    d="$(awk -v want="$version" '
        $0 ~ "^##[ \t]+\\[?" want "\\]?([ \t]|$)" {
            if (match($0, /[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]/))
                print substr($0, RSTART, RLENGTH)
            exit
        }' "$changelog_md")"
    if [ -z "$d" ]; then
        echo "::warning::CHANGELOG.md [$version] has no date; using today's, so this build is not reproducible." >&2
        d="$(date -u +%F)"
    fi
    LC_ALL=C date -u -d "$d 00:00:00" "+$fmt"
}

deb_body=""
rpm_body=""
render_changelog "$version" deb >/dev/null || promote_unreleased || true
if deb_body="$(render_changelog "$version" deb)" \
   && rpm_body="$(render_changelog "$version" rpm)"; then
    echo "CHANGELOG.md: using the [$version] section"
else
    echo "::warning::CHANGELOG.md has no [$version] section and no [Unreleased] content; falling back to '$msg'"
    deb_body="  * ${msg}"
    rpm_body="- ${msg}"
fi

# --- debian ---------------------------------------------------------------
current="$(sed -n '1s/^[^ ]* (\([^)]*\)).*/\1/p' "$changelog")"
if [ "$current" = "$version" ]; then
    echo "debian/changelog already at $version"
else
    tmp="$(mktemp)"
    {
        printf 'secure-eye (%s) unstable; urgency=medium\n\n' "$version"
        printf '%s\n\n' "$deb_body"
        printf ' -- %s <%s>  %s\n\n' "$name" "$mail" \
            "$(entry_date '%a, %d %b %Y %H:%M:%S +0000')"
        cat "$changelog"
        [ -n "$(tail -c 1 "$changelog")" ] && printf '\n'
    } > "$tmp"
    mv "$tmp" "$changelog"
    echo "debian/changelog: $current -> $version"
fi

# --- rpm ------------------------------------------------------------------

sed -i -E "s/^(%\{!\?pkg_version:%global pkg_version )[^}]*(\})/\1${version}\2/" "$spec"
grep -q "pkg_version ${version}}" "$spec" \
    || { echo "::error::failed to set pkg_version in $spec" >&2; exit 1; }

if grep -qE "^\* .* - ${version}-" "$spec"; then
    echo "rpm spec: %changelog already has $version"
else
    tmp="$(mktemp)"
    {
        printf '* %s %s <%s> - %s-1\n' \
            "$(entry_date '%a %b %d %Y')" "$name" "$mail" "$version"
        printf '%s\n\n' "$rpm_body"
    } > "$tmp"
    awk -v entryfile="$tmp" '
        /^%changelog$/ && !done {
            print
            while ((getline line < entryfile) > 0) print line
            close(entryfile)
            done = 1
            next
        }
        { print }
    ' "$spec" > "$tmp.spec"
    mv "$tmp.spec" "$spec"
    rm -f "$tmp"
fi
echo "rpm spec: pkg_version -> $version"

# --- arch -----------------------------------------------------------------

sed -i -E "s/^pkgver=.*/pkgver=${version}/" "$pkgbuild"
sed -i -E "s/^pkgrel=.*/pkgrel=1/" "$pkgbuild"
if [ -n "${SRC_SHA256:-}" ]; then
    sed -i -E "0,/^sha256sums=\('[^']*'/s//sha256sums=('${SRC_SHA256}'/" "$pkgbuild"
    grep -q "sha256sums=('${SRC_SHA256}'" "$pkgbuild" \
        || { echo "::error::failed to set sha256sums[0] in $pkgbuild" >&2; exit 1; }
    echo "PKGBUILD: pkgver -> $version, sha256sums[0] -> $SRC_SHA256"
else
    echo "PKGBUILD: pkgver -> $version (sha256sums left untouched)"
fi
