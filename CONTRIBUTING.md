# Contributing to SecureEye

Thank you for your interest in contributing.

---

## Project Scope

SecureEye is a modern reimplementation of facial authentication for Linux systems.
The project focuses on maintainability, modularity, and security.

---

## Getting Started

### Requirements

* Python 3.12+
* Git
* Virtual environment tools

### Setup

```bash
git clone https://github.com/vhrabar/secureEye
cd esecureEye
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Development Guidelines

### Code Style

* Python: Follow PEP8
* Python: Use type hints where appropriate
* Python: Format code using `black`
* Python: Lint using `ruff`
* C++: Use C++20+, prefer standard library features
* C++: 4-space indentation, max 100 characters per line
* C++: Snake_case for functions/variables, PascalCase for classes, UPPER_CASE for constants
* C++: Trailing _ for private members (e.g., buffer_)
* C++: Prefer RAII and smart pointers, avoid raw pointers
* C++: Open braces on the same line
* C++: Always check return values/errors; use std::optional or exceptions carefully

---

### Architecture Principles

* Keep modules small and focused
* Avoid global state
* Design for testability
* Keep recognition pipeline modular

---

### Commit Guidelines

* Use clear, descriptive commit messages
* Keep commits focused and minimal
* Reference issues where applicable

Example:

```bash
feat(recognition): add MediaPipe-based face detector
```

---

## Pull Requests

Before submitting a PR:

* Ensure code builds and runs
* Add or update tests if applicable
* Keep PRs focused on a single concern

PRs may be rejected if they:

* Introduce unnecessary complexity
* Break modular design
* Add unmaintained dependencies

---

## Testing

* Use `pytest`
* Avoid reliance on physical hardware (mock camera input)
* Ensure reproducible results

---

## Use of Generative AI

Contributions assisted by generative AI tools are permitted, but must meet strict quality standards.

* All submitted code must be **fully understood by the contributor**.
* Generated code must be **reviewed, tested, and validated** before submission.
* Submissions that contain low-quality, unverified, or irrelevant generated output (“AI slop”) will be rejected.
* Contributors are responsible for ensuring:

    * correctness
    * security
    * adherence to project architecture and standards

Large, uncurated AI-generated changes that do not demonstrate clear intent or understanding are not acceptable.

---

## Attribution

This project is inspired by the Howdy project (MIT License).
Original authors are credited via the preserved Git history.
See the `NOTICE` file for details.

---

## Security Considerations

This project interacts with system authentication (PAM).

* Do not introduce unsafe system calls
* Validate all external inputs
* Avoid insecure defaults

---

## Questions

Open an issue for discussion before making large changes.

---
