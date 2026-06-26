# SecureEye

Modern face recognition authentication for Linux using PAM.

---

## Overview

SecureEys is a clean, modern reimplementation of facial authentication for Linux systems. It enables users to
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

- Python 3.12 or higher (pip, setuptools, wheel)
- Meson 0.64 or higher
- Ninja
- INIReader (fetched automatically if missing)
- libevdev

#### Install Dependencies

```bash
sudo apt-get update && sudo apt-get install -y \
    python3 python3-pip python3-setuptools python3-wheel \
    cmake make build-essential \
    libpam0g-dev libinih-dev libevdev-dev python3-opencv \
    python3-dev libopencv-dev
```

#### Build & Install

```bash
meson setup build
meson compile -C build
```

You can also install SecureEye to your system with `meson install -C build`.

### Debian / Ubuntu & derivatives

Download the latest .deb from the [GitHub releases page](https://github.com/vhrabar/SecureEye/releases)
and install:

```bash
sudo apt install ./SecureEye-<version>.deb
sudo apt install -f
```
### PPA

```bash
sudo add-apt-repository ppa:vhrabar/secure-eye
sudo apt update && sudo apt install secureEye
```

---

## Usage

After installation, SecureEye needs to learn what your face look like so it can recognise you later. Run
`sudo secureEye add` to add a new face model.

If nothing went wrong we should be able to run sudo by just showing your face. Open a new terminal and run `sudo -i` to
see it in action. Please check [this wiki page](https://github.com/vhrabar/SecureEye/wiki/Common-issues) if you're
experiencing problems or [search](https://github.com/vhrabar/SecureEye/issues) for similar issues.

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
