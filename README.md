<!-- Light mode -->
![Logo (light)](assets/secureeye-banner-light.svg#gh-light-mode-only)

<!-- Dark mode -->
![Logo (dark)](assets/secureeye-banner.svg#gh-dark-mode-only)
# SecureEye

[![Tests](https://img.shields.io/github/actions/workflow/status/vhrabar/SecureEye/pytests.yml?style=for-the-badge&label=tests&logo=pytest&logoColor=white)](https://github.com/vhrabar/SecureEye/actions/workflows/pytests.yml)
[![Copr build status](https://copr.fedorainfracloud.org/coprs/vhrabar/SecureEye/package/secure-eye/status_image/last_build.png)](https://copr.fedorainfracloud.org/coprs/vhrabar/SecureEye/package/secure-eye/)

[![Latest release](https://img.shields.io/github/v/release/vhrabar/SecureEye?include_prereleases&sort=semver&style=for-the-badge&logo=github)](https://github.com/vhrabar/SecureEye/releases)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange?style=for-the-badge&logo=semver&logoColor=white)](#status)
[![License: GPL v2](https://img.shields.io/badge/License-GPL_v2-orange?style=for-the-badge&logo=gnu&logoColor=white)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)

Face recognition login for Linux, through PAM.

## Overview

SecureEye lets you authenticate with your face anywhere PAM is used: `sudo`, login, the lock screen, polkit. It
started as a rework of [Howdy](https://github.com/boltgolt/howdy) and keeps its CLI, but splits the work in two: a
small C/C++ PAM module, and the `secureeye-authd` daemon, which runs as its own unprivileged service account and owns
the camera and the face models. The module only talks to the daemon over a UNIX socket, so no Python or recognition
code runs inside the process that is authenticating you.

## Features

* Face login for any PAM service, falling back to your password when recognition fails or times out
* mediapipe (default; x86_64 and aarch64, x86_64 only on Arch) or dlib recognition backend, chosen in the config
* `secureEye` CLI to enroll, list and remove face models and to test the camera
* Desktop app to enroll with a live preview, run a recognition test against the `certainty` threshold and edit the
  configuration
* Native packages for Ubuntu, Fedora/RHEL and Arch; the daemon runs on the system Python, with no bundled virtualenv

## Status

Alpha. It works for daily use, but the config format and the daemon protocol may still change between releases.

## Installation

SecureEye is packaged for Ubuntu (PPA), Fedora and RHEL (COPR) and Arch (AUR) as two packages: `secure-eye` is the
PAM module, the `secureeye-authd` daemon and the `secureEye` CLI; `secure-eye-gui` is the optional app. See
[docs/installation.md](docs/installation.md) for RHEL, manual and from-source builds, and what each package sets up.

**Ubuntu** (24.04 or newer; the app needs 26.04 or newer). The daemon is started for you:

```bash
sudo add-apt-repository ppa:vhrabar/tools
sudo apt update
sudo apt install secure-eye secure-eye-gui
```

**Fedora**:

```bash
sudo dnf copr enable vhrabar/SecureEye
sudo dnf install secure-eye secure-eye-gui
sudo systemctl enable --now secureeye-authd.service
```

**Arch Linux** (AUR):

```bash
paru -S secure-eye secure-eye-gui   # or: yay -S ...
sudo systemctl enable --now secureeye-authd.service
```

Leave out `secure-eye-gui` on machines without a desktop. On Arch the default recognition backend, mediapipe, is
x86_64 only; on other architectures set `detector_backend = dlib` with `sudo secureEye config` before first use.

## Usage

**1. Set your camera device.** The default config ships with `device_path = none`, so recognition does nothing until
you point it at a real capture device. Open the config and set `device_path` (e.g. `/dev/video0`):

```bash
sudo secureEye config
```

You can list capture-capable nodes with `v4l2-ctl --list-devices`. After changing the device, restart the daemon:
`sudo systemctl restart secureeye-authd`.

**2. Enroll your face.** SecureEye needs a model of your face to recognise you later:

```bash
sudo secureEye add
```

**3. Make sure the PAM module is enabled.**

On Ubuntu and Debian it is enabled on install; check it with:

```bash
grep -q pam_secureEye.so /etc/pam.d/common-auth && echo enabled || sudo pam-auth-update --enable secureEye.pam-config
```

On Fedora and Arch you enable it yourself. For `sudo` only, add this as the first `auth` line of `/etc/pam.d/sudo`:

```
auth  sufficient  pam_secureEye.so
```

To use it everywhere (login, lock screen, polkit), see
[Enabling the PAM module](docs/installation.md#enabling-the-pam-module): an authselect profile on Fedora,
`/etc/pam.d/system-auth` on Arch.

**Or use the app.** Start SecureEye from your application menu, or run `secureeye-gui` as your normal user (not with
`sudo`):

- the Dashboard shows whether face login is on, whether the daemon is running and whether the configured camera is
  found
- Face models → Enroll captures a model with a live camera preview; closing the dialog turns the camera off right away
- Run recognition test shows, frame by frame, how close you come to the `certainty` threshold; use it to tune
  `certainty` or to see whether you need another model, e.g. one with glasses
- Configuration edits `/etc/secureEye/config.ini`; saving asks for your password through polkit

The app talks to `secureeye-authd`, which owns the camera and the face models, so the daemon has to be running. You
can only manage your own face models. Step 3 (enabling the PAM module) still has to be done once.

**4. Try it.** Open a new terminal and run `sudo -i`; you should be able to authenticate by showing your face. If
face auth fails or times out, SecureEye falls back to your password. If something doesn't work, check
[Common issues](https://github.com/vhrabar/SecureEye/wiki/Common-issues) on the wiki or
[search the issues](https://github.com/vhrabar/SecureEye/issues).

## CLI

The `secureEye` command manages face models for the current user. Run `secureEye --help` or `man secureEye` for all
options.

```
secureEye [-U user] [-y] command [argument]
```

| Command     | Description                                                              |
|-------------|--------------------------------------------------------------------------|
| `add`       | Add a new face model for a user                                          |
| `clear`     | Remove all face models for a user                                        |
| `config`    | Open the config file in your default editor                              |
| `disable`   | Disable or enable SecureEye                                              |
| `list`      | List all saved face models for a user                                    |
| `re-enroll` | Recapture a user's face models under the currently configured recognizer |
| `remove`    | Remove a specific model for a user                                       |
| `set`       | Set a config option (`secureEye set certainty 3`)                        |
| `snapshot`  | Take a snapshot of your camera input                                     |
| `test`      | Test the camera and recognition methods                                  |
| `version`   | Print the current version number                                         |

## Development

### Docs

- Installation details and building from source: [docs/installation.md](docs/installation.md)
- PAM/authd split overview: [docs/auth-architecture.md](docs/auth-architecture.md)
- IPC protocol contract: [docs/auth-protocol-v1.md](docs/auth-protocol-v1.md)
- Management protocol used by the app: [docs/auth-protocol-v2.md](docs/auth-protocol-v2.md)
- PAM return-code mapping: [docs/pam-behavior-matrix.md](docs/pam-behavior-matrix.md)

### Requirements

* Python 3.12+
* [uv](https://docs.astral.sh/uv/): `uv sync` sets up the environment; see the [Contributing guide](CONTRIBUTING.md)

### Running the app against a development daemon

`tools/dev/gui-sandbox.sh` builds the app, starts `secureeye-authd` from this checkout as your user on its own socket,
with the config and face models in `.devroot/`, and runs the app against it. The installed daemon and `/etc` are not
touched. Saving the configuration and the face login switch are blocked in the sandbox, since they would write to
`/etc` through pkexec.

```bash
tools/dev/gui-sandbox.sh
```

### PAM tests in Docker

The Compose `pam-smoke` service runs the PAM flow inside a container, without touching the host's PAM config.

`smoke` (build and install, patch PAM, check `sudo`):

```bash
docker compose --profile pam build pam-smoke
docker compose --profile pam run --rm pam-smoke
```

`full` (`smoke`, then `secureEye add` and `secureEye test`):

```bash
PAM_FLOW=full docker compose --profile pam run --rm pam-smoke
```

`interactive` (prompts for user, password and device, with optional add/test):

```bash
PAM_FLOW=interactive docker compose --profile pam run --rm pam-smoke
```

To use a different camera:

```bash
SECUREEYE_VIDEO_DEVICE=/dev/video0 docker compose --profile pam run --rm pam-smoke
```

## Contributing

Contributions are welcome; see the [Contributing guide](CONTRIBUTING.md).

## License

This project is licensed under the GNU General Public License v2.0.

Copyright © 2026 Vedran Hrabar

It includes code derived from the Howdy project, which is licensed under the MIT License. See the [NOTICE](NOTICE)
file and [licenses/MIT.txt](licenses/MIT.txt) for details. Howdy's original authors and contributors are credited in
the preserved Git history.

## AI usage

- The project icon and banner were made with Claude Design.
- Claude Code was used for debugging and for proofreading the docs.

## Disclaimer

This software interacts with system authentication mechanisms. Use it with caution and at your own risk.
