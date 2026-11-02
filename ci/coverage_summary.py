#!/usr/bin/env python3
"""
Turn raw coverage data into per-category badges and a PR comment.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

MARKER = "<!-- coverage-comment -->"

# (minimum percent, colour), checked top to bottom.
THRESHOLDS = [(90, "brightgreen"), (75, "green"), (60, "yellow"), (40, "orange"), (0, "red")]


def colour_for(percent: int | None) -> str:
    if percent is None:
        return "lightgrey"
    for minimum, colour in THRESHOLDS:
        if percent >= minimum:
            return colour
    return "red"


def cpp_counts(tracefile: Path, filters: list[str], excludes: list[str]) -> tuple[int, int]:
    """Covered/total lines for C++ sources matching any of `filters`."""
    if not filters or not tracefile.is_file():
        return 0, 0
    with tempfile.TemporaryDirectory() as tmp:
        summary = Path(tmp) / "summary.json"
        cmd = ["gcovr", "--root", ".", "--add-tracefile", str(tracefile)]
        for f in filters:
            cmd += ["--filter", f]
        for e in excludes:
            cmd += ["--exclude", e]
        cmd += ["--json-summary", str(summary)]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        data = json.loads(summary.read_text())
    return int(data.get("line_covered", 0)), int(data.get("line_total", 0))


def python_counts(data_file: Path, includes: list[str], omits: list[str]) -> tuple[int, int]:
    """Covered/total statements for Python sources matching any of `includes`."""
    if not includes or not data_file.is_file():
        return 0, 0
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        cmd = [
            "coverage",
            "json",
            f"--data-file={data_file}",
            f"--include={','.join(includes)}",
            "-o",
            str(report),
        ]
        if omits:
            cmd.append(f"--omit={','.join(omits)}")
        # Exit status 1 with "No data to report" means nothing matched: treat as zero lines.
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            if "No data to report" in result.stdout + result.stderr:
                return 0, 0
            sys.stderr.write(result.stdout + result.stderr)
            result.check_returncode()
        totals = json.loads(report.read_text())["totals"]
    return int(totals["covered_lines"]), int(totals["num_statements"])


def static_badge(label: str, message: str, colour: str) -> str:
    def esc(s: str) -> str:
        # shields.io static badge path escaping: '-' -> '--', '_' -> '__', rest URL-encoded.
        return quote(s.replace("-", "--").replace("_", "__"), safe="")

    return f"https://img.shields.io/badge/{esc(label)}-{esc(message)}-{colour}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--config", type=Path, default=Path("ci/coverage_categories.json"))
    ap.add_argument("--gcovr-json", type=Path, required=True, help="gcovr JSON tracefile")
    ap.add_argument("--coverage-data", type=Path, required=True, help="coverage.py data file")
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--sha", default="", help="commit shown in the comment footer")
    ap.add_argument("--report-url", default="", help="link to the HTML report / CI run")
    args = ap.parse_args()

    config = json.loads(args.config.read_text())
    cpp_exclude = config.get("cpp_exclude", [])
    python_omit = config.get("python_omit", [])

    badges_dir = args.out / "badges"
    badges_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for cat in config["categories"]:
        c_cov, c_tot = cpp_counts(args.gcovr_json, cat.get("cpp", []), cpp_exclude)
        p_cov, p_tot = python_counts(args.coverage_data, cat.get("python", []), python_omit)
        covered, total = c_cov + p_cov, c_tot + p_tot

        percent = round(100 * covered / total) if total else None
        message = f"{percent}%" if percent is not None else "n/a"
        colour = colour_for(percent)
        label = cat["label"]

        badge = {"schemaVersion": 1, "label": label, "message": message, "color": colour}
        (badges_dir / f"{cat['id']}.json").write_text(json.dumps(badge) + "\n")

        rows.append((label, message, colour, covered, total))
        print(f"{label:<10} {message:>5}  ({covered}/{total} lines)")

    lines = [
        MARKER,
        "## Coverage",
        "",
        "| Category | Coverage |",
        "| --- | --- |",
    ]
    for label, message, colour, covered, total in rows:
        badge_md = f"![{label}]({static_badge(label, message, colour)})"
        lines.append(f"| {label} | {badge_md} <sub>{covered}/{total} lines</sub> |")
    footer = []
    if args.sha:
        footer.append(f"Line coverage at `{args.sha[:7]}`.")
    if args.report_url:
        footer.append(f"[Full HTML report]({args.report_url})")
    if footer:
        lines += ["", "<sub>" + " ".join(footer) + "</sub>"]
    (args.out / "comment.md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
