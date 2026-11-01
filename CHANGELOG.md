# Changelog

All notable changes to SecureEye are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `secure-eye-gui`, the SecureEye app, as its own package on Debian/Ubuntu,
  Fedora and Arch, so headless installs of `secure-eye` pull in no Qt. It
  ships under the app ID `io.github.vhrabar.SecureEye`, with a desktop entry,
  an icon and AppStream metainfo. With it you can enroll face models with a
  live camera preview and remove them, run a recognition test that shows how
  close each frame comes to the `certainty` threshold, switch face login on
  and off, edit the configuration, and see and control the `secureeye-authd`
  service and the configured camera.
- The app works through `secureeye-authd`: the daemon owns the camera and the
  face models, so the app never opens the camera itself and needs no
  administrator rights to manage your own models. A login always takes
  priority; an enrollment or test running in the app is stopped when a login
  needs the camera.
- `secureEye re-enroll` replaces your face models after a change of recognizer,
  and keeps the models of the previous one so switching back still works.
- `--json` output for `list`, `remove`, `clear`, `disable`, `set` and
  `version`, for scripts.

### Changed

- Face models carry the recognizer that made them, and a login never compares
  models from different recognizers. If yours no longer match the configured
  one, the login says so and asks you to run `secureEye re-enroll`.
- Face model files are stored in a new format. Existing files keep working
  and are converted the first time they are changed; older releases cannot
  read converted files, so downgrading after that means enrolling again.
- Face models are owned by the `secureeye` daemon user and are no longer
  readable by other users.
- The daemon's socket is open to all users, and each request is checked
  against the user who sent it: you can only log in as, or manage the models
  of, yourself (root can do both for anyone). Screen lockers that run PAM as
  the logged-in user can now reach the daemon.
- The daemon handles several requests at once, so a client that stalls no
  longer holds up everyone else.

### Fixed

- Face login failed every time on systems with NumPy 2 (`only 0-dimensional
  arrays can be converted to Python scalars`).


## [0.2.1] - 2026-08-19

### Fixed

- COPR builds failed in the source stage, before any chroot was built:
  `.copr/Makefile` resolved the release version with `git describe` while make
  parsed the file, which happens before the recipe installs git. The version
  came out empty and `set-package-version.sh` aborted. It is now resolved
  inside the recipe, after git is installed, and a clone with no reachable tag
  fails with a message that says so rather than with a blank version.

## [0.2.0] - 2026-08-18

### Changed

- SecureEye now ships as a single `secure-eye` package on Debian, RPM and Arch,
  replacing `libpam-secureeye`, `secureeye-authd` and the transitional
  metapackage. Existing installs are swapped automatically on upgrade.
- The recognition backends are ordinary distribution packages instead of a
  bundled virtualenv: `python3-mediapipe` (amd64/x86_64 only) and
  `python3-dlib`, from `ppa:vhrabar/tools` on Ubuntu and
  `copr:vhrabar/python-extras` on Fedora. Select one with `detector_backend` in
  `/etc/secureEye/config.ini`.
- The daemon and the `secureEye` launcher run on the system Python interpreter,
  so nothing has to be rebuilt after a Python upgrade. The systemd unit and the
  launcher now use the interpreter meson was configured with rather than a
  hardcoded virtualenv path.
- Releases no longer carry `.deb` or `.rpm` attachments. Install from the PPA,
  COPR or the AUR instead.

### Added

- Arch Linux packaging is published to the AUR as `secure-eye`.
- `CHANGELOG.md` is the single source of truth for release notes.
  `scripts/set-package-version.sh` renders a release's section into the Debian
  and RPM changelogs, and `scripts/changelog-section.sh` extracts it for the
  GitHub release body.
- A single release workflow that runs the tests, verifies the deb, RPM and Arch
  packages build and install, and only then publishes to the Launchpad PPA,
  COPR and the AUR. COPR builds are pinned to the released tag.
- A Prepare release workflow that sets the version, tags it and drafts the
  release from the changelog.

### Removed

- The install-time virtualenv, the vendored Python wheels and the dpkg trigger
  that rebuilt the virtualenv whenever python3 was upgraded.

### Fixed

- Launchpad PPA uploads carry the real changelog entries; every upload
  previously read "New upstream release".
- Fedora and RHEL install instructions: the package ships no systemd preset, so
  `secureeye-authd.service` has to be enabled manually. The README claimed
  installation enabled it.
- The CLI reference lists the `set` command.

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
