# SecureEye Split Architecture (PAM + authd)

## Goal

Keep PAM deterministic and minimal while moving Python/MediaPipe runtime into an isolated helper daemon.

## Components

1. PAM module (`pam_secureEye.so`)
    - Runs inside PAM stack
    - Performs PAM pre-checks and user messaging
    - Sends auth request to daemon over Unix socket
    - Enforces strict timeout and fail-closed behavior for daemon communication

2. IPC boundary
    - Unix socket: `/run/secureeye/authd.sock`
    - Strict framed protocol (`docs/auth-protocol-v1.md`)
    - Bounded payloads and versioned messages

3. Authentication daemon (`secureeye-authd`)
    - Runs under dedicated service account (not root)
    - Hosts Python runtime and MediaPipe dependencies
    - Uses existing auth pipeline (`secureEye/src/auth/session.py`)

## Failure domain split

- PAM-side failures must remain deterministic and immediate.
- Python/media runtime failures are isolated in daemon process scope.
- Daemon communication failures are mapped to `PAM_AUTH_ERR` (project fail-closed policy).

## Packaging target

- `libpam-secureeye`
    - PAM shared object and PAM config integration
    - No Python runtime dependency

- `secureeye-authd`
    - Python modules and MediaPipe dependency chain
    - systemd service unit and runtime socket provisioning

