
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

## Runtime venv

`secureeye-authd` builds its recognition virtualenv in
`/usr/lib/secureeye-authd/venv` from bundled wheels during package
installation (`%post`), fully offline. It is rebuilt on every upgrade
and removed on erase.

## Backends

- x86_64 / x86_64 ("+v3" Release suffix): mediapipe backend (vendored wheel).
- aarch64: dlib backend. Fedora does not package `python3-dlib`, so a
  dlib wheel built from source is vendored into the package and the
  shipped `config.ini` defaults to `detector_backend = dlib`.
