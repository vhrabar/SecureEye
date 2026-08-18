# Changelog

All notable changes to SecureEye are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Release automation reads this file: on `release: published`,
`scripts/set-package-version.sh` renames `## [Unreleased]` to the tag and
renders that section into `secureEye/debian/changelog` and the RPM
`%changelog`. Write notes under `## [Unreleased]`; never edit the generated
files by hand.

## [Unreleased]

## [0.1.3] - 2026-07-23

First Arch release: SecureEye now packages and installs on Arch-like
distributions, alongside the existing Debian/Ubuntu/RPM support.

### Fixed

- Implemented detector caching and reduced time constraints on CPU-based
  systems.

## [0.1.2] - 2026-07-05

First RPM release: SecureEye now packages and installs on Fedora and
RHEL-family distributions, alongside the existing Debian/Ubuntu support.

### Added

- RPM packaging mirroring the Debian split layout: three packages —
  `libpam-secureeye` (PAM module), `secureeye-authd` (daemon plus the Python
  recognition runtime), and the `secure-eye` transitional metapackage.
- COPR distribution (`vhrabar/SecureEye`): install on Fedora with
  `dnf copr enable vhrabar/SecureEye && dnf install secure-eye`.
- GitHub Actions workflow building RPMs for x86_64, x86_64-v3 and aarch64,
  attaching them to GitHub releases, with an install smoke test.
- `scripts/build-rpm.sh`, to build the RPMs in a Fedora container.
- aarch64 dlib backend: since Fedora ships no `python3-dlib` and there is no
  prebuilt aarch64 wheel, the dlib recognition wheel (pinned to 20.0.1) is
  compiled from source during the RPM build.

## [0.1.1] - 2026-07-02

### Fixed

- MediaPipe no longer uses a non-existing PipAudio on some configurations.

## [0.1.0] - 2026-06-27

Initial release, tagged `v0.1.0-alpha`. SecureEye is a modern reimplementation
of facial authentication for Linux, derived from
[Howdy](https://github.com/boltgolt/howdy).

This is an early, pre-1.0 release. Facial recognition is a convenience factor
and should not be relied on as a sole authentication method.

### Highlights

- New detection pipeline: dlib replaced by MediaPipe and FaceNet embeddings,
  with dlib still available as an optional backend.
- Fail-safe PAM architecture: a minimal C/C++ PAM module talks to a Python
  daemon over a UNIX socket, keeping Python and MediaPipe out of the
  authentication path.
- Split packaging into separate PAM, daemon and transitional metapackages.
- Config-driven CLI for managing models and configuration.

### Added

Project and governance:

- Forked and rebranded Howdy as SecureEye, preserving the derived work through
  git history, with a `NOTICE` and bundled MIT licence for the inherited code.
- Added a Code of Conduct, Contributing guide and Security policy.
- Configured clang-tidy, ruff and pyproject tooling.

Detection:

- Replaced the dlib pipeline with a MediaPipe-based face detector, using
  FaceNet embeddings and new preprocessing utilities. dlib is retained as an
  optional backend.
- Added a config-driven detector factory with lazy imports, so the CLI and GUI
  tools only load the backend they actually need.

Architecture — the PAM and authd split:

- Split authentication into a minimal C/C++ PAM module and a Python
  authentication daemon communicating over a UNIX-domain socket. This keeps
  Python and MediaPipe out of the PAM path, so authentication fails safe.
- Added the `secureeye-authd` daemon: socket server, bounded request
  validation, versioned IPC protocol (v1) encode/decode, and cooperative
  cancellation with a timeout budget.
- Reworked the PAM module into an IPC client that enforces a wait timeout and
  falls back to password when the daemon is unavailable.
- Refactored the former `compare.py` monolith into focused modules: errors,
  types, frame ops, matching, model store, auth session and UI bridge.

CLI:

- Config-driven entrypoint with dynamic module loading and model-management
  commands: `add`, `clear`, `config`, `disable`, `list`, `remove`, `snapshot`,
  `test` and `version`.

Packaging:

- Split into three packages: `libpam-secureeye` (PAM module only),
  `secureeye-authd` (daemon and Python runtime) and `secure-eye` (transitional
  metapackage).
- Installs a systemd service and sysusers entry for the daemon.
- Vendors pinned Python dependencies as wheels and builds the runtime venv on
  the target host at install time; the venv is rebuilt on python3 upgrades via
  a dpkg trigger.

Documentation:

- Added architecture, IPC protocol v1 and PAM behaviour-matrix docs.
- Expanded the README with installation, usage and Docker PAM smoke-test
  instructions.

CI and containers:

- Added a GitHub Actions test workflow, CodeQL analysis and Dependabot.
- Added a Dockerfile and Compose setup for the test environment and the PAM
  `sudo` smoke-test flows.
