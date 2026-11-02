#!/usr/bin/env bash
# Build and test SecureEye with coverage, then write per-category results to out/.
#
#   ci/coverage.sh
#
# Env overrides:
#   BUILD_DIR   meson build dir with -Db_coverage=true (default: build-cov)
#   OUT_DIR     output dir (default: out)
#   SHA         commit shown in the PR comment footer
#   REPORT_URL  link shown in the PR comment footer
#
# Outputs:
#   out/badges/<id>.json  shields.io endpoint badges
#   out/comment.md        PR comment / step summary table
#   out/html/             HTML reports (cpp/ from gcovr, python/ from coverage.py)
#
set -euo pipefail

cd "$(dirname "$0")/.."

BUILD_DIR=${BUILD_DIR:-build-cov}
OUT_DIR=${OUT_DIR:-out}
COVERAGE_VERSION=7.17.0
GCOVR_VERSION=8.8

# Project env plus the two coverage tools, without adding them to uv.lock.
tools=(uv run --locked --with "coverage==${COVERAGE_VERSION}" --with "gcovr==${GCOVR_VERSION}")

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR/html/cpp" "$OUT_DIR/html/python"

echo "::group::C++ build + tests"
if [[ -d "$BUILD_DIR" ]]; then
    meson setup --reconfigure "$BUILD_DIR" -Db_coverage=true
    find "$BUILD_DIR" -name '*.gcda' -delete
else
    meson setup "$BUILD_DIR" -Db_coverage=true --buildtype=debug
fi
meson compile -C "$BUILD_DIR"
meson test -C "$BUILD_DIR" --print-errorlogs
echo "::endgroup::"

echo "::group::Python tests"
"${tools[@]}" coverage run --data-file="$BUILD_DIR/.coverage" \
    --source=secureEye/src -m pytest tests/
"${tools[@]}" coverage html --data-file="$BUILD_DIR/.coverage" \
    -d "$OUT_DIR/html/python" --omit='tests/*,*/tests/*'
echo "::endgroup::"

echo "::group::gcovr"
# One gcov pass over everything under secureEye/src; categories are filtered
# from this tracefile by coverage_summary.py.
"${tools[@]}" gcovr --root . "$BUILD_DIR" \
    --filter 'secureEye/src/' \
    --exclude '(.+/)?tests/' --exclude '(.+/)?subprojects/' \
    --json "$BUILD_DIR/gcovr.json" \
    --html-details "$OUT_DIR/html/cpp/index.html" \
    --print-summary
echo "::endgroup::"

cat > "$OUT_DIR/html/index.html" <<'EOF'
<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>SecureEye coverage</title></head>
<body><h1>SecureEye coverage</h1>
<ul><li><a href="cpp/index.html">C++ (GUI, PAM)</a></li>
<li><a href="python/index.html">Python (Backend)</a></li></ul>
</body></html>
EOF

"${tools[@]}" python ci/coverage_summary.py \
    --gcovr-json "$BUILD_DIR/gcovr.json" \
    --coverage-data "$BUILD_DIR/.coverage" \
    --out "$OUT_DIR" \
    --sha "${SHA:-}" \
    --report-url "${REPORT_URL:-}"
