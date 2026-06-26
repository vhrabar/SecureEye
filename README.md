# SecureEye

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

#### Install Dependencies

```bash
sudo apt-get update && sudo apt-get install -y \
    meson ninja-build pkg-config build-essential \
    python3 python3-pip python3-venv \
    libpam0g-dev libinih-dev libevdev-dev
```

#### Build

```bash
meson setup build
meson compile -C build
```

> [!WARNING]
> Do **not** run `meson install` on a machine where you also use the `.deb`
> packages. Meson's default prefix is `/usr/local`, and `/usr/local/lib/...`
> shadows the packaged `/usr/lib/...` systemd unit (and `/usr/local/bin` shadows
> `/usr/bin`), which breaks the daemon and CLI. A bare `meson install` also does
> **not** create the recognition virtualenv — that is built by the
> `secureeye-authd` package at install time — so the daemon will not start.
> For a working system install, build and install the Debian packages below.

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
sudo add-apt-repository ppa:vhrabar/secure-eye
sudo apt update && sudo apt install secure-eye
```

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

**3. Make sure the PAM profile is enabled.** It is normally enabled automatically
on install, but `pam-auth-update` will skip a profile it has already "seen" from a
previous install. Verify (and enable if needed):

```bash
grep -q pam_secureEye.so /etc/pam.d/common-auth && echo enabled || sudo pam-auth-update --enable secureEye.pam-config
```

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
* pip / virtualenv

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

It includes code derived from the Howdy project, which is licensed under the MIT License.
See the NOTICE file and `/licenses/MIT.txt` for details.

---

## Attribution

This project is inspired by the Howdy project.
Original authors and contributors are credited via the preserved Git history.

---

## Contributing

Contributions are welcome, check the [Contributing guide](CONTRIBUTING.md) for guidelines.

---

## Disclaimer

This software interacts with system authentication mechanisms.
Use with caution and at your own risk.
