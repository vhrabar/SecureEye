# Output helpers shared by the CLI commands

import builtins
import json
import sys


def json_mode() -> bool:
    return getattr(builtins.secureEye_args, "json", False)


def say(*lines: str) -> None:
    """Print human readable output, suppressed in JSON mode."""
    if not json_mode():
        for line in lines:
            print(line)


def ok(data=None, *lines: str) -> None:
    """Report success. In JSON mode only data is printed, otherwise only the lines."""
    if json_mode():
        print(json.dumps({"ok": True, "data": data}))
    else:
        say(*lines)


def fail(code: str, message: str, *hints: str) -> None:
    """Report an error and exit with status 1. Hints are extra lines shown to people only."""
    if json_mode():
        print(json.dumps({"ok": False, "error": {"code": code, "message": message.strip()}}))
    else:
        say(message, *hints)
    sys.exit(1)
