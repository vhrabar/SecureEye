# Contributing to SecureEye

Thanks for your interest in contributing.

## Repository layout

- `secureEye/src/pam`: the C/C++ PAM module (`pam_secureEye.so`)
- `secureEye/src/authd`, `auth`, `detectors`, `cli`: the Python daemon, recognition pipeline and `secureEye` CLI
- `secureEye/src/gui`: the Qt/Kirigami app (`secureeye-gui`)
- `secureEye/debian`, `secureEye/rpm`, `secureEye/archlinux`: packaging
- `tests/`: Python tests; the C++/Qt tests live next to the GUI sources and run through Meson
- `docs/`: architecture and protocol docs; start with [docs/auth-architecture.md](docs/auth-architecture.md)

## Setup

Requirements: Python 3.12+, Git and [uv](https://docs.astral.sh/uv/). To build the PAM module and the app you also
need Meson, Ninja, a C++ compiler, the PAM/inih/evdev headers and Qt 6.9+; the package lists per distribution are in
[docs/installation.md](docs/installation.md#building-from-source).

```bash
git clone https://github.com/vhrabar/SecureEye
cd SecureEye
uv sync                       # Python environment, including dev tools
uv run pre-commit install     # run the checks on every commit
```

To build and test the C++ side:

```bash
meson setup build
meson compile -C build
meson test -C build --print-errorlogs
```

Don't `meson install` on a machine that also has the packages installed; see the warning in
[docs/installation.md](docs/installation.md#build).

To try the app against a daemon running from your checkout, without touching `/etc` or the installed daemon, use
`tools/dev/gui-sandbox.sh`. To test the full PAM flow in a container, use the Docker `pam-smoke` service described in
the [README](README.md#pam-tests-in-docker); copy `.env.example` to `.env` to change the camera or the test user.

## Checks

CI runs these on every push and pull request to `main` and `dev`. The pre-commit hooks cover all of them except
clang-tidy and the tests, so run those yourself before opening a PR:

| Check                     | Command                                                     |
|---------------------------|-------------------------------------------------------------|
| All pre-commit hooks      | `uv run pre-commit run --all-files`                         |
| Python tests              | `uv run pytest`                                             |
| C++/Qt tests              | `meson test -C build`                                       |
| clang-tidy (needs build/) | `ninja -C build clang-tidy`                                 |

The hooks run ruff (format and lint), clang-format 22.1.8 (the version CI uses), shellcheck, whitespace and YAML/TOML
checks, and keep `uv.lock` and `requirements.txt` up to date.

## Code style

The formatter and linter configs are the rules; this section only covers what they don't.

- Python: `ruff format` and `ruff check`, configured in `pyproject.toml` (100 columns). Use type hints for new code.
- C++: `.clang-format` for layout (4 spaces, 120 columns) and `.clang-tidy` for naming and checks. In short:
  `camelBack` functions and variables, `CamelCase` types and enum values, `m_` prefix for private members, `k` prefix
  for constexpr constants. The code is C++23 (`meson.build`).
- C++: prefer RAII and standard library types to raw owning pointers, and check every return value. The PAM module
  fails closed: any error talking to the daemon must end in `PAM_AUTH_ERR`
  (see [docs/pam-behavior-matrix.md](docs/pam-behavior-matrix.md)).
- Editor settings (indentation, line endings) are in `.editorconfig`.

## Dependencies

Python dependencies are declared in `pyproject.toml` with exact pins and locked in `uv.lock`. `requirements.txt` is
generated from the lock for the Dockerfile and CodeQL; don't edit it by hand. After changing a dependency:

```bash
uv lock
uv export --no-dev --no-hashes --no-emit-project --format requirements-txt -o requirements.txt
```

The pre-commit hooks do both for you. The packages install the backends from distribution repositories, so a new
runtime dependency also has to be added to `secureEye/debian/control`, `secureEye/rpm/secure-eye.spec` and the
`PKGBUILD`.

## Tests

- Use `pytest`, under `tests/`.
- Don't depend on real hardware: mock the camera.
- Tests that need the real mediapipe package are marked `mediapipe_integration` and skip when it isn't installed.

## Commits and pull requests

- Target the `dev` branch.
- Use [Conventional Commits](https://www.conventionalcommits.org/) with a scope, and reference the issue where there
  is one:

  ```
  feat(recognition): add MediaPipe-based face detector #42
  ```

- Keep commits and PRs focused on one change, and add or update tests for it.
- Note user-visible changes under `## [Unreleased]` in `CHANGELOG.md`.

### Changelog

`CHANGELOG.md` is the single source of truth for release notes, in
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) format. Don't edit `secureEye/debian/changelog` or the
`%changelog` in `secureEye/rpm/secure-eye.spec` by hand: on release, `scripts/set-package-version.sh` renames
`## [Unreleased]` to the tag and renders that section into both, in each format's layout. A release with no matching
section still succeeds, but ships only "New upstream release X.Y.Z." to users.

### What gets a PR rejected

- Complexity the change doesn't need
- Recognition code moved into the PAM module, or anything else that breaks the PAM/daemon split
- New dependencies that are unmaintained or not packaged for the supported distributions

## Security

SecureEye sits in the authentication path, so:

- validate everything that crosses the socket or comes from config and user input
- don't add new privileged code paths or insecure defaults
- report vulnerabilities as described in [SECURITY.md](SECURITY.md), and don't disclose details publicly before a fix

## Use of generative AI

Contributions made with AI tools are welcome, on the same terms as any other code:

- You must understand everything you submit and be able to explain it in review.
- Generated code must be reviewed, tested and checked against the architecture and style above before you open a PR.
- You are responsible for its correctness and security.

Large, uncurated generated changes with no clear intent will be closed.

## License

By contributing, you agree that your contributions are licensed under the GPL-2.0 license of this project. Parts of
the code derive from [Howdy](https://github.com/boltgolt/howdy) (MIT); see [NOTICE](NOTICE).

Please also follow the [Code of Conduct](CODE_OF_CONDUCT.md).
