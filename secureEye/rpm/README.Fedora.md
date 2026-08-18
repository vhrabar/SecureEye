
# SecureEye on Fedora / RPM-based systems

## PAM setup

Fedora has no `pam-auth-update`, so the PAM profile shipped for
Debian/Ubuntu (`usr/share/pam-configs/`) does not apply here. Enable the
module with an authselect custom profile:

```bash
sudo authselect create-profile secureeye -b local
# Add this line near the top of the auth section of
# /etc/authselect/custom/secureeye/{system,password}-auth:
#   auth  sufficient  pam_secureEye.so
sudo authselect select custom/secureeye --force
```

Or, for a single service (e.g. sudo only), add to `/etc/pam.d/sudo`:

```
auth  sufficient  pam_secureEye.so
```

Do NOT edit `/etc/pam.d/system-auth` directly — authselect will
overwrite it.

## Runtime

Nothing is bundled and there is no virtualenv: `secureeye-authd` runs on the
system Python interpreter (`/usr/bin/python3`), so there is nothing to rebuild
after a Python upgrade.

## Backends

The recognition backends are ordinary packages from the
[`vhrabar/python-extras`](https://copr.fedorainfracloud.org/coprs/vhrabar/python-extras/)
COPR, selected with `detector_backend` in `/etc/secureEye/config.ini`:

- `python3-mediapipe` — the default backend, **x86_64 only**
- `python3-dlib` — the alternative backend, and the only one on other
  architectures

Enable that COPR alongside the SecureEye one, or `dnf` cannot resolve the
dependencies:

```bash
sudo dnf copr enable vhrabar/python-extras
```

On non-x86_64 there is no mediapipe, so switch the backend before first use:

```bash
sudo secureEye config    # set detector_backend = dlib
```
