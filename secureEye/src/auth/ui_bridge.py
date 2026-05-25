# TODO: Integartion with future Qt-based GUI
from __future__ import annotations


class AuthUiBridge:
    """Placeholder bridge that mimics compare message API.

    - "M": main text
    - "S": subtext
    """

    def __init__(self, enabled_stdout: bool = False):
        self.enabled_stdout = enabled_stdout

    def start(self) -> None:
        """No-op placeholder for future GUI startup."""
        return None

    def send(self, kind: str, message: str) -> None:
        """Send a message to the UI placeholder."""
        if self.enabled_stdout:
            print(f"UI[{kind}] {message}")

    def close(self) -> None:
        """No-op placeholder for future GUI shutdown."""
        return None
