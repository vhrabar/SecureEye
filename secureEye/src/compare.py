# thin wrapper for auth logic

import sys

from auth import AuthSession, ExitCode


def main() -> int:
    if len(sys.argv) < 2:
        return int(ExitCode.ABORT)

    user = sys.argv[1]
    session = AuthSession()
    return session.run(user)


if __name__ == "__main__":
    sys.exit(main())
