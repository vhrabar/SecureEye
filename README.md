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

Modern face recognition authentication for Linux using PAM.

---

## Overview

SecureEye is a clean, modern reimplementation of facial authentication for Linux systems. It enables users to
authenticate via face recognition while maintaining a modular, secure, and maintainable architecture.

This project is inspired by the Howdy project but is being redesigned with updated technologies, improved structure, and long-term maintainability in mind.

---

## Features

* Face recognition-based authentication
* PAM (Pluggable Authentication Modules) integration
* Modular recognition pipeline
* CLI tools for user management
* Designed for modern Python environments

---

## Status

Early development. Core architecture and modules are being actively built.

---

## Installation

### Building from Source

#### Dependencies

These mirror the package `Build-Depends` in `secureEye/debian/control`:

- Meson 0.64 or higher, Ninja, pkg-config, a C++ compiler (`build-essential`)
- Python 3 with pip (`python3`, `python3-pip`)
- `libpam0g-dev`, `libevdev-dev`, `libinih-dev` (INIReader is provided by
  `libinih-dev`; it is **not** downloaded, the build runs with
  `--wrap-mode=nodownload`)

The Qt GUI (`secureeye-gui`) is built from the same tree and needs Qt 6 on top
of the list above (it is not part of the `.deb` packages yet):

- `qt6-base-dev`, `qt6-base-dev-tools` (Core, Gui, Network)
- `qt6-declarative-dev`, `qt6-declarative-dev-tools` (Qml, Quick,
  QuickControls2, plus `qmlcachegen`/`qmltyperegistrar`)
- At **runtime** only: `qml6-module-org-kde-kirigami` and
  `libkf6qqc2desktopstyle-data` (the QML `org.kde.kirigami` import and the
  `org.kde.desktop` Quick Controls style)

#### Install Dependencies

On **Debian / Ubuntu**:

```bash
sudo apt-get update && sudo apt-get install -y \
    meson ninja-build pkg-config build-essential \
    python3 python3-pip python3-venv \
    libpam0g-dev libinih-dev libevdev-dev \
    qt6-base-dev qt6-base-dev-tools \
    qt6-declarative-dev qt6-declarative-dev-tools \
    qml6-module-org-kde-kirigami libkf6qqc2desktopstyle-data
```

On **Arch Linux** (`libinih` provides `INIReader`, `pam` provides the PAM headers):

```bash
sudo pacman -S --needed base-devel meson ninja pkgconf \
    python python-pip pam libinih libevdev
```

#### Build

```bash
meson setup build
meson compile -C build
```

> [!WARNING]
> Do **not** run `meson install` on a machine where you also use the packaged
> builds (`.deb`, `.rpm` or the AUR package). Meson's default prefix is
> `/usr/local`, and `/usr/local/lib/...` shadows the packaged `/usr/lib/...`
> systemd unit (and `/usr/local/bin` shadows `/usr/bin`), which breaks the
> daemon and CLI. On Debian and Fedora a bare `meson install` also does **not**
> create the recognition virtualenv, that is built by the `secureeye-authd`
> package at install time, so the daemon will not start. For a working system
> install, build and install your distribution's packages below.

### Debian / Ubuntu & derivatives

SecureEye ships as three packages:

- `libpam-secureeye` — the C/C++ PAM module (no Python)
- `secureeye-authd` — the authentication daemon and Python recognition runtime
- `secure-eye` — a transitional metapackage that depends on both

Download the latest `.deb` files from the
[GitHub releases page](https://github.com/vhrabar/SecureEye/releases) and
install all of them together so dependencies (including `python3-venv`) resolve:

```bash
sudo apt install ./libpam-secureeye_*.deb ./secureeye-authd_*.deb ./secure-eye_*.deb
```

On install, `secureeye-authd` builds its recognition virtualenv from the bundled
wheels (this takes a short while) and enables the `secureeye-authd.service`.

### PPA

```bash
sudo add-apt-repository ppa:vhrabar/tools
sudo apt update && sudo apt install secure-eye
```

### Fedora, RHEL & RPM-based systems

The easiest way is the
[COPR repository](https://copr.fedorainfracloud.org/coprs/vhrabar/SecureEye/).

On **Fedora**:

```bash
sudo dnf copr enable vhrabar/SecureEye
sudo dnf install secure-eye
```

On **RHEL / CentOS Stream / Rocky / AlmaLinux** (enable EPEL first for the `copr`
plugin and dependencies):

```bash
sudo dnf install epel-release
sudo dnf copr enable vhrabar/SecureEye
sudo dnf install secure-eye
```

This installs the same three packages as on Debian (`libpam-secureeye`,
`secureeye-authd`, `secure-eye`). On install, `secureeye-authd` builds its
recognition virtualenv from the bundled wheels and enables the
`secureeye-authd.service`.

Alternatively, download the `.rpm` files from the
[GitHub releases page](https://github.com/vhrabar/SecureEye/releases) and install
them together:

```bash
sudo dnf install ./libpam-secureeye-*.rpm ./secureeye-authd-*.rpm ./secure-eye-*.rpm
```

> [!NOTE]
> On Fedora/RHEL there is no `pam-auth-update`, so the PAM module is **not**
> enabled automatically. Enable it as shown in **Usage step 3b** below (the
> Debian-only `pam-auth-update` / `common-auth` steps do not apply).

### Arch Linux & derivatives

SecureEye is packaged for the AUR as `secureeye`, which builds two packages:

- `libpam-secureeye`: the C/C++ PAM module (no Python)
- `secureeye-authd`: the authentication daemon and Python recognition runtime

There is no transitional metapackage; install both. With an AUR helper:

```bash
paru -S libpam-secureeye secureeye-authd   # or: yay -S ...
```

Or manually with `makepkg` (the recognition dependencies `python-mediapipe`
and `python-sounddevice` also come from the AUR and must be built first):

```bash
git clone https://aur.archlinux.org/secureeye.git
cd secureeye
makepkg -si
```

You can also build straight from a checkout of this repository:

```bash
cd secureEye/archlinux/secureEye
makepkg -si
```

Unlike the `.deb`/`.rpm` packages, the Arch build does **not** bundle a recognition virtualenv: every dependency is a
real package and the daemon runs on the system interpreter, so there is nothing to rebuild after a Python upgrade. On
`aarch64` there is no MediaPipe, so the package depends on
`python-dlib` and ships `detector_backend = dlib` in the default config.

Following Arch policy, the service is **not** started for you:

```bash
sudo systemctl enable --now secureeye-authd.service
```

> [!NOTE]
> Arch has neither `pam-auth-update` nor `authselect`, so the PAM module is
> **not** enabled automatically. Enable it as shown in **Usage step 3c** below.

---

## Usage

**1. Set your camera device.** The default config ships with `device_path = none`,
so recognition does nothing until you point it at a real capture device. Open the
config and set `device_path` (e.g. `/dev/video0`):

```bash
sudo secureEye config
```

You can list capture-capable nodes with `v4l2-ctl --list-devices`. After changing
the device, restart the daemon: `sudo systemctl restart secureeye-authd`.

**2. Enroll your face.** SecureEye needs to learn your face so it can recognise
you later:

```bash
sudo secureEye add
```

**3. Make sure the PAM profile is enabled.**

**3a) Ubuntu / Debian.** It is normally enabled automatically on install, but
`pam-auth-update` will skip a profile it has already "seen" from a previous
install. Verify (and enable if needed):

```bash
grep -q pam_secureEye.so /etc/pam.d/common-auth && echo enabled || sudo pam-auth-update --enable secureEye.pam-config
```

**3b) Fedora / RHEL.** There is no `pam-auth-update`; enable the module with an
authselect custom profile:

```bash
sudo authselect create-profile secureeye -b local
# Add this line near the top of the auth section of
# /etc/authselect/custom/secureeye/{system,password}-auth:
#   auth  sufficient  pam_secureEye.so
sudo authselect select custom/secureeye --force
```

Or, for a single service (e.g. `sudo` only), add to `/etc/pam.d/sudo`:

```
auth  sufficient  pam_secureEye.so
```

Do **not** edit `/etc/pam.d/system-auth` directly as authselect overwrites it.

**3c) Arch Linux.** There is no `pam-auth-update` and no `authselect`; edit the PAM stack yourself. For a single service
(recommended, e.g. `sudo` only), add this as the **first** `auth` line of `/etc/pam.d/sudo`:

```
auth  sufficient  pam_secureEye.so
```

To cover every service that includes it (login, `sudo`, display-manager greeters, `polkit`), add the same line at the
top of the `auth` section of
`/etc/pam.d/system-auth` instead. That file belongs to the `pam` package, so back it up and re-apply your change when
pacman leaves a `system-auth.pacnew`
after an upgrade.

**4. Try it.** Open a new terminal and run `sudo -i` — you should be able to
authenticate by showing your face. If face auth fails or times out, SecureEye
falls back to your password. Please check
[this wiki page](https://github.com/vhrabar/SecureEye/wiki/Common-issues) if
you're experiencing problems or
[search](https://github.com/vhrabar/SecureEye/issues) for similar issues.

## CLI

The installer adds a `secureEye` command to manage face models for the current user. Use `secureEye --help` or
`man secureEye` to list the available options.

Usage:

```
secureEye [-U user] [-y] command [argument]
```

| Command    | Description                                 |
|------------|---------------------------------------------|
| `add`      | Add a new face model for a user             |
| `clear`    | Remove all face models for a user           |
| `config`   | Open the config file in your default editor |
| `disable`  | Disable or enable SecureEye                 |
| `list`     | List all saved face models for a user       |
| `re-enroll`| Recapture a user's face models under the currently configured recognizer |
| `remove`   | Remove a specific model for a user          |
| `snapshot` | Take a snapshot of your camera input        |
| `test`     | Test the camera and recognition methods     |
| `version`  | Print the current version number            |

---

## Development

### Architecture docs

- PAM/authd split overview: [docs/auth-architecture.md](docs/auth-architecture.md)
- IPC protocol contract: [docs/auth-protocol-v1.md](docs/auth-protocol-v1.md)
- PAM return-code mapping: [docs/pam-behavior-matrix.md](docs/pam-behavior-matrix.md)

### Requirements

* Python 3.12+
* uv / pip / virtualenv

### Docker PAM Automation

Use the Compose `pam-smoke` service to run an automated in-container PAM flow without touching host PAM.

`smoke` flow (build/install + PAM patch + sudo check):

```bash
docker compose --profile pam build pam-smoke
docker compose --profile pam run --rm pam-smoke
```

`full` flow (smoke + `secureEye add` + `secureEye test`):

```bash
PAM_FLOW=full docker compose --profile pam run --rm pam-smoke
```

Interactive flow (prompts for user/password/device and optional add/test):

```bash
PAM_FLOW=interactive docker compose --profile pam run --rm pam-smoke
```

Override camera device if needed:

```bash
SECUREEYE_VIDEO_DEVICE=/dev/video0 docker compose --profile pam run --rm pam-smoke
```

## License

This project is licensed under the GNU General Public License v2.0.

Copyright © 2026 Vedran Hrabar

It includes code derived from the Howdy project, which is licensed under the MIT License.
See the NOTICE file and `/licenses/MIT.txt` for details.

---

## Attribution

This project is inspired by the Howdy project.
Original authors and contributors are credited via the preserved Git history.

The project logo and banner were created with AI assistance.

---

## Contributing

Contributions are welcome, check the [Contributing guide](CONTRIBUTING.md) for guidelines.

---

## Disclaimer

This software interacts with system authentication mechanisms.
Use with caution and at your own risk.
