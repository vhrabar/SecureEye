# SecureEye

Modern face recognition authentication for Linux using PAM.

---

## Overview

EyeAuth is a clean, modern reimplementation of facial authentication for Linux systems. It enables users to authenticate via face recognition while maintaining a modular, secure, and maintainable architecture.

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

### Manual Installation

### PPA

---

## Usage

*Coming soon.*

---

## Development

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

Contributions are welcome. Guidelines will be added as the project stabilizes.

---

## Disclaimer

This software interacts with system authentication mechanisms.
Use with caution and at your own risk.
