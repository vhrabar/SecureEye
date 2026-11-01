#!/usr/bin/env python3
"""Rewrite a debian/ directory to build secure-eye without the GUI.

For Ubuntu series that cannot build the GUI (no Kirigami for Qt 6, Qt < 6.9,
meson < 1.7), e.g. noble. Drops the secure-eye-gui binary package and its
install list, the build dependencies only the GUI needs, and configures meson
with -Dinstall_gui=false.

    scripts/debian-without-gui.py path/to/debian
"""

import re
import sys
from pathlib import Path

GUI_PACKAGE = "secure-eye-gui"
# Build-Depends only the GUI needs
GUI_BUILD_DEPS = re.compile(r"^(qt6-\S+|desktop-file-utils|appstream)$")


def strip_control(text: str) -> str:
    paragraphs = re.split(r"\n\s*\n", text.strip())
    kept = [p for p in paragraphs if not re.match(rf"Package:\s*{GUI_PACKAGE}\s*$", p, re.M)]
    if len(kept) == len(paragraphs):
        sys.exit(f"debian/control has no {GUI_PACKAGE} package")

    source = kept[0].split("\n")
    out = []
    in_build_depends = False
    for line in source:
        if line.startswith("Build-Depends:"):
            in_build_depends = True
            out.append(line)
            continue
        if in_build_depends and line.startswith(" "):
            name = line.strip().rstrip(",")
            if GUI_BUILD_DEPS.match(name.split()[0]):
                continue
            out.append(line)
            continue
        in_build_depends = False
        out.append(line)

    # the dropped entries may have been the last ones; the list must not end in a comma
    source_text = "\n".join(out)
    source_text = re.sub(r",(\n(?! ))", r"\1", source_text)
    source_text = re.sub(r",\Z", "", source_text)
    kept[0] = source_text
    return "\n\n".join(kept) + "\n"


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    debian = Path(sys.argv[1])

    control = debian / "control"
    control.write_text(strip_control(control.read_text()))

    rules = debian / "rules"
    text = rules.read_text()
    if "-Dinstall_gui=true" not in text:
        sys.exit("debian/rules does not pass -Dinstall_gui=true")
    rules.write_text(text.replace("-Dinstall_gui=true", "-Dinstall_gui=false"))

    (debian / f"{GUI_PACKAGE}.install").unlink(missing_ok=True)
    print(f"{debian}: built without {GUI_PACKAGE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
