# Installing SecureEye

SecureEye is published as two packages:

- `secure-eye`: the C/C++ PAM module, the `secureeye-authd` daemon, the Python recognition runtime and the `secureEye`
  CLI. It replaces the older `libpam-secureeye` / `secureeye-authd` split, and the package manager swaps those out on
  upgrade.
- `secure-eye-gui`: the app, optional. It pulls in Qt 6 and Kirigami, so leave it out on headless machines.

The recognition backends are ordinary distribution packages, not a bundled virtualenv, and the daemon runs on the
system Python, so nothing needs rebuilding after a Python upgrade:

- mediapipe (`python3-mediapipe`, `python-mediapipe` on Arch): the default backend
- dlib (`python3-dlib`, `python-dlib` on Arch): the alternative

mediapipe is packaged for x86_64 and aarch64 on Ubuntu and Fedora, but for x86_64 only on Arch. Where it isn't
available, set `detector_backend = dlib` in `/etc/secureEye/config.ini` (or with `sudo secureEye config`) before first
use.

After installing, set up the camera, enroll your face and enable the PAM module as described under
[Usage](../README.md#usage) in the README. [Enabling the PAM module](#enabling-the-pam-module) below has the
per-distribution details for that last step.

- [Debian / Ubuntu & derivatives](#debian--ubuntu--derivatives)
- [Fedora, RHEL & RPM-based systems](#fedora-rhel--rpm-based-systems)
- [Arch Linux & derivatives](#arch-linux--derivatives)
- [Enabling the PAM module](#enabling-the-pam-module)
- [Building from source](#building-from-source)

## Debian / Ubuntu & derivatives

The packages and the recognition backends are in `ppa:vhrabar/tools`:

```bash
sudo add-apt-repository ppa:vhrabar/tools
sudo apt update
sudo apt install secure-eye
```

The app needs Ubuntu 26.04 or newer; Ubuntu 24.04 gets `secure-eye` only.

```bash
sudo apt install secure-eye-gui
```

Unlike the RPM and Arch packages, the Debian package enables and starts `secureeye-authd.service` on install.

## Fedora, RHEL & RPM-based systems

The packages are in the [SecureEye COPR](https://copr.fedorainfracloud.org/coprs/vhrabar/SecureEye/). The
recognition backends come from the [`vhrabar/python-extras`](https://copr.fedorainfracloud.org/coprs/vhrabar/python-extras/)
COPR, which is a runtime dependency of the SecureEye one, so `dnf copr enable` adds and enables it for you.

On Fedora:

```bash
sudo dnf copr enable vhrabar/SecureEye
sudo dnf install secure-eye
sudo dnf install secure-eye-gui   # the app, optional
```

On RHEL, CentOS Stream, Rocky or AlmaLinux 10, enable EPEL first. It provides the `copr` plugin and some of the
dependencies, including Kirigami for the app:

```bash
sudo dnf install epel-release
sudo dnf copr enable vhrabar/SecureEye
sudo dnf install secure-eye
sudo dnf install secure-eye-gui   # the app, optional
```

The package ships no systemd preset, so `%systemd_post` leaves the unit disabled. Start it yourself:

```bash
sudo systemctl enable --now secureeye-authd.service
```

> [!NOTE]
> Fedora and RHEL have no `pam-auth-update`, so the PAM module is not enabled automatically. Enable it as shown in
> [Fedora / RHEL](#fedora--rhel) below.

## Arch Linux & derivatives

`secure-eye` and `secure-eye-gui` are in the AUR, built together from one PKGBUILD. With an AUR helper:

```bash
paru -S secure-eye        # or: yay -S ...
paru -S secure-eye-gui    # the app, optional
```

Or by hand with `makepkg`. The recognition backends `python-dlib` and `python-mediapipe` also come from the AUR and
have to be built first. `makepkg -si` builds and installs both `secure-eye` and `secure-eye-gui`:

```bash
git clone https://aur.archlinux.org/secure-eye.git
cd secure-eye
makepkg -si
```

The PKGBUILD is also in this repository, under `secureEye/archlinux/secureEye/`:

```bash
cd secureEye/archlinux/secureEye
makepkg -si
```

Following Arch policy, the service is not started for you:

```bash
sudo systemctl enable --now secureeye-authd.service
```

> [!NOTE]
> Arch has neither `pam-auth-update` nor `authselect`, so the PAM module is not enabled automatically. Enable it as
> shown in [Arch Linux](#arch-linux) below.

## Enabling the PAM module

### Ubuntu / Debian

The module is normally enabled on install, but `pam-auth-update` skips a profile it has already seen from an earlier
install. Check it, and enable it if needed:

```bash
grep -q pam_secureEye.so /etc/pam.d/common-auth && echo enabled || sudo pam-auth-update --enable secureEye.pam-config
```

### Fedora / RHEL

Use an authselect custom profile:

```bash
sudo authselect create-profile secureeye -b local
# Add this line near the top of the auth section of
# /etc/authselect/custom/secureeye/{system,password}-auth:
#   auth  sufficient  pam_secureEye.so
sudo authselect select custom/secureeye --force
```

Or, for a single service (e.g. `sudo` only), add this to `/etc/pam.d/sudo`:

```
auth  sufficient  pam_secureEye.so
```

Don't edit `/etc/pam.d/system-auth` directly; authselect overwrites it.

### Arch Linux

Edit the PAM stack yourself. For a single service (recommended, e.g. `sudo` only), add this as the first `auth` line
of `/etc/pam.d/sudo`:

```
auth  sufficient  pam_secureEye.so
```

To cover every service that includes it (login, `sudo`, display manager greeters, polkit), add the same line at the
top of the `auth` section of `/etc/pam.d/system-auth` instead. That file belongs to the `pam` package, so back it up,
and re-apply your change when pacman leaves a `system-auth.pacnew` after an upgrade.

## Building from source

### Dependencies

These mirror the `Build-Depends` in `secureEye/debian/control`:

- Meson 0.64 or newer (1.7 or newer with the app), Ninja, pkg-config and a C++ compiler (`build-essential`)
- Python 3 (`python3`)
- `libpam0g-dev`, `libevdev-dev` and `libinih-dev`. `INIReader` comes from `libinih-dev`; the build runs with
  `--wrap-mode=nodownload`, so it is not downloaded.

The app (`secureeye-gui`) is built from the same tree and also needs Qt 6.9 or newer. Configure with
`-Dinstall_gui=false` to build without it.

- `qt6-base-dev`, `qt6-base-dev-tools` (Core, Gui, Network)
- `qt6-declarative-dev`, `qt6-declarative-dev-tools` (Qml, Quick, QuickControls2, plus `qmlcachegen` and
  `qmltyperegistrar`)
- At runtime only: `qml6-module-org-kde-kirigami` and `qml6-module-org-kde-desktop` (the `org.kde.kirigami` QML import
  and the `org.kde.desktop` Quick Controls style)

### Install dependencies

On Debian / Ubuntu:

```bash
sudo apt-get update && sudo apt-get install -y \
    meson ninja-build pkg-config build-essential \
    python3 \
    libpam0g-dev libinih-dev libevdev-dev \
    qt6-base-dev qt6-base-dev-tools \
    qt6-declarative-dev qt6-declarative-dev-tools \
    qml6-module-org-kde-kirigami qml6-module-org-kde-desktop
```

On Arch Linux (`libinih` provides `INIReader`, `pam` provides the PAM headers):

```bash
sudo pacman -S --needed base-devel meson ninja pkgconf \
    python python-pip pam libinih libevdev \
    qt6-base qt6-declarative kirigami qqc2-desktop-style
```

### Build

```bash
meson setup build
meson compile -C build
```

> [!WARNING]
> Don't run `meson install` on a machine where you also use the packaged builds (`.deb`, `.rpm` or AUR). Meson's
> default prefix is `/usr/local`, and the files it installs shadow the packaged ones: `/usr/local/lib/...` overrides
> the systemd unit in `/usr/lib/...`, and `/usr/local/bin` overrides `/usr/bin`. That breaks the daemon and the CLI.
> A bare `meson install` also doesn't pull in the recognition backends (`python3-mediapipe` / `python3-dlib`) that the
> packages depend on, so the daemon won't start. For a working system install, use your distribution's packages above.
