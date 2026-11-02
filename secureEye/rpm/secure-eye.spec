# RPM packaging for SecureEye
#
# CI passes:
#   --define "pkg_version X.Y.Z"       (from the release tag)
#   --define "rel_suffix .v3"          (x86-64-v3 build only)
#   --define "march x86-64-v3"         (x86-64-v3 build only)
#
# Sources:
#   Source0  git archive of the tree
#   Source1  sysusers fragment
#
# Nothing is bundled: the recognition backends are ordinary packages from
# copr:vhrabar/python-extras (python3-mediapipe on x86_64/aarch64; python3-dlib) and
# the rest come from Fedora. Add that COPR as an external repository of the
# SecureEye project so the builds and installs can resolve them.

%{!?pkg_version:%global pkg_version 0.3.2}


%undefine __brp_python_bytecompile

# secure-eye-gui needs meson >= 1.7 (qt.qml_module). RHEL 10 and its rebuilds
# (AlmaLinux) ship meson 1.4, so they get the core package only; CentOS Stream
# and Fedora are newer. Override with --with gui / --without gui.
%if 0%{?rhel} && !0%{?centos}
%bcond_with gui
%else
%bcond_without gui
%endif

Name:           secure-eye
Version:        %{pkg_version}
Release:        1%{?rel_suffix}%{?dist}
Summary:        SecureEye face authentication for Linux
License:        GPL-2.0-only AND MIT
URL:            https://github.com/vhrabar/secureEye
Source0:        %{name}-%{version}.tar.gz
Source1:        secure-eye.sysusers

BuildRequires:  meson >= 0.64
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconf-pkg-config
BuildRequires:  pam-devel
BuildRequires:  libevdev-devel
# Provides INIReader
BuildRequires:  inih-devel
BuildRequires:  python3-devel
BuildRequires:  systemd-rpm-macros
%if %{with gui}
BuildRequires:  qt6-qtbase-devel
BuildRequires:  qt6-qtdeclarative-devel
BuildRequires:  desktop-file-utils
BuildRequires:  appstream
%endif

Requires:       python3 >= 3.12
Requires:       python3-numpy
Requires:       python3-opencv
Requires:       python3-matplotlib
Requires:       python3-cffi
# Recognition backends, from copr:vhrabar/python-extras. mediapipe is the
# default backend and is built for x86_64 and aarch64; dlib is the
# alternative and the only backend on other architectures.
%ifarch x86_64 aarch64
Requires:       python3-mediapipe
%endif
Requires:       python3-dlib
Requires:       v4l-utils
# Optional code paths: the ffmpeg recording plugin and the hotkey rubberstamp
# import these lazily and degrade gracefully when they are absent.
Suggests:       python3-sounddevice
Suggests:       python3-ffmpeg-python
Suggests:       python3-keyboard
%{?sysusers_requires_compat}
%{?systemd_requires}

# Merged from the former split packages.
Provides:       libpam-secureeye = %{version}-%{release}
Provides:       secureeye-authd = %{version}-%{release}
Obsoletes:      libpam-secureeye < %{version}-%{release}
Obsoletes:      secureeye-authd < %{version}-%{release}

%description
SecureEye authenticates Linux users with their face. This package ships the
complete stack: the C/C++ PAM module, the secureeye-authd authentication
daemon it talks to over a UNIX socket, the Python recognition runtime and the
secureEye command line tool.

The recognition backend is selected with detector_backend in
/etc/secureEye/config.ini: mediapipe (the default, x86_64 and aarch64) or dlib. The
daemon runs on the system Python interpreter, so there is nothing to rebuild
after a Python upgrade.

Unlike Debian/Ubuntu there is no pam-auth-update on Fedora; enable the module
manually or via an authselect custom profile (see README.Fedora.md).

%if %{with gui}
%package gui
Summary:        SecureEye face authentication for Linux - management app
Requires:       %{name}%{?_isa} = %{version}-%{release}
Requires:       kf6-kirigami
Requires:       qt6-qtdeclarative%{?_isa}
Recommends:     kf6-qqc2-desktop-style
Recommends:     breeze-icon-theme
# pkexec, for saving the configuration and switching face login
Recommends:     polkit

%description gui
A Qt/Kirigami app for SecureEye: enroll face models with a live camera
preview, test recognition against the certainty threshold, switch face login
on and off, edit the configuration and control the secureeye-authd service.

The camera and the face models are handled by secureeye-authd; the app talks
to it over its UNIX socket and never opens the camera itself.
%endif

%prep
%autosetup -n %{name}-%{version}

%build
export CFLAGS="%{optflags}%{?march: -march=%{march}}"
export CXXFLAGS="%{optflags}%{?march: -march=%{march}}"

meson setup %{_vpath_builddir} . \
    --wrap-mode=nodownload \
    --buildtype=plain \
    --prefix=%{_prefix} \
    --sysconfdir=%{_sysconfdir} \
    --localstatedir=%{_localstatedir} \
    --libdir=%{_lib} \
    -Dpython.bytecompile=-1 \
    -Dinstall_pam_config=false \
    -Dpython_path=%{_bindir}/python3 \
    -Dconfig_dir=%{_sysconfdir}/secureEye \
    -Duser_models_dir=%{_sysconfdir}/secureEye/models \
    -Dwith_polkit=true \
    -Dinstall_gui=%{?with_gui:true}%{!?with_gui:false}
meson compile -C %{_vpath_builddir}

%install
DESTDIR=%{buildroot} meson install -C %{_vpath_builddir}

rm -rf %{buildroot}%{_datadir}/dlib-data

# User models directory (user_models_dir).
install -d -m 0700 %{buildroot}%{_sysconfdir}/secureEye/models

# sysusers fragment.
install -D -m 0644 %{SOURCE1} %{buildroot}%{_sysusersdir}/secure-eye.conf

%check
%if %{with gui}
desktop-file-validate %{buildroot}%{_datadir}/applications/io.github.vhrabar.SecureEye.desktop
appstreamcli validate --no-net %{buildroot}%{_metainfodir}/io.github.vhrabar.SecureEye.metainfo.xml
%endif

%pre
%sysusers_create_compat %{SOURCE1}

%post
%tmpfiles_create secure-eye.conf
%systemd_post secureeye-authd.service

%preun
%systemd_preun secureeye-authd.service

%postun
%systemd_postun_with_restart secureeye-authd.service

%files
%license LICENSE licenses/MIT.txt
%doc NOTICE README.md secureEye/rpm/README.Fedora.md
%{_bindir}/secureEye
%{_libdir}/security/pam_secureEye.so
%{_libdir}/secureEye/
%{_unitdir}/secureeye-authd.service
%{_tmpfilesdir}/secure-eye.conf
%{_sysusersdir}/secure-eye.conf
%{_datadir}/bash-completion/completions/secureEye
%{_datadir}/polkit-1/actions/com.github.vhrabar.secureeye.policy
%{_mandir}/man1/SecureEye.1*
%dir %{_sysconfdir}/secureEye
%config(noreplace) %{_sysconfdir}/secureEye/config.ini
%dir %attr(0700,secureeye,secureeye) %{_sysconfdir}/secureEye/models

%if %{with gui}
%files gui
%license LICENSE
%{_bindir}/secureeye-gui
%{_datadir}/applications/io.github.vhrabar.SecureEye.desktop
%{_datadir}/icons/hicolor/scalable/apps/io.github.vhrabar.SecureEye.svg
%{_metainfodir}/io.github.vhrabar.SecureEye.metainfo.xml
%endif

%changelog
* Sun Nov 01 2026 Vedran Hrabar <vedran.hrabar@outlook.com> - 0.3.2-1
- Fixed: 0.3.1 never reached Ubuntu, Fedora or the AUR: its Debian changelog
  entry had the same date as 0.3.0's, which lintian rejects, so the release
  stopped before publishing. Releases dated the same day now get distinct
  times.

* Sun Nov 01 2026 Vedran Hrabar <vedran.hrabar@outlook.com> - 0.3.1-1
- Fixed: Ubuntu packages for resolute, stonking and tenacious failed to
  build on Launchpad: the Debian source package left out every directory
  named `tests`, including the app's own test sources, which the build
  needs.
- Fixed: Fedora COPR builds for RHEL 10 and AlmaLinux 10 failed, because
  their meson is too old for the app. Those two now get `secure-eye` without
  `secure-eye-gui`; Fedora and CentOS Stream still get both.

* Sun Nov 01 2026 Vedran Hrabar <vedran.hrabar@outlook.com> - 0.3.0-1
- Added: `secure-eye-gui`, the SecureEye app, as its own package on
  Debian/Ubuntu, Fedora and Arch, so headless installs of `secure-eye` pull
  in no Qt. It ships under the app ID `io.github.vhrabar.SecureEye`, with a
  desktop entry, an icon and AppStream metainfo. With it you can enroll face
  models with a live camera preview and remove them, run a recognition test
  that shows how close each frame comes to the `certainty` threshold, switch
  face login on and off, edit the configuration, and see and control the
  `secureeye-authd` service and the configured camera.
- Added: The app works through `secureeye-authd`: the daemon owns the camera
  and the face models, so the app never opens the camera itself and needs no
  administrator rights to manage your own models. A login always takes
  priority; an enrollment or test running in the app is stopped when a login
  needs the camera.
- Added: `secureEye re-enroll` replaces your face models after a change of
  recognizer, and keeps the models of the previous one so switching back
  still works.
- Added: `--json` output for `list`, `remove`, `clear`, `disable`, `set` and
  `version`, for scripts.
- Changed: Face models carry the recognizer that made them, and a login
  never compares models from different recognizers. If yours no longer match
  the configured one, the login says so and asks you to run `secureEye
  re-enroll`.
- Changed: Face model files are stored in a new format. Existing files keep
  working and are converted the first time they are changed; older releases
  cannot read converted files, so downgrading after that means enrolling
  again.
- Changed: Face models are owned by the `secureeye` daemon user and are no
  longer readable by other users.
- Changed: The daemon's socket is open to all users, and each request is
  checked against the user who sent it: you can only log in as, or manage
  the models of, yourself (root can do both for anyone). Screen lockers that
  run PAM as the logged-in user can now reach the daemon.
- Changed: The daemon handles several requests at once, so a client that
  stalls no longer holds up everyone else.
- Fixed: Face login failed every time on systems with NumPy 2 (`only
  0-dimensional arrays can be converted to Python scalars`).

* Wed Aug 19 2026 Vedran Hrabar <vedran.hrabar@outlook.com> - 0.2.1-1
- Fixed: COPR builds failed in the source stage, before any chroot was
  built: `.copr/Makefile` resolved the release version with `git describe`
  while make parsed the file, which happens before the recipe installs git.
  The version came out empty and `set-package-version.sh` aborted. It is now
  resolved inside the recipe, after git is installed, and a clone with no
  reachable tag fails with a message that says so rather than with a blank
  version.

* Tue Aug 18 2026 Vedran Hrabar <vedran.hrabar@outlook.com> - 0.2.0-1
- Changed: SecureEye now ships as a single `secure-eye` package on Debian,
  RPM and Arch, replacing `libpam-secureeye`, `secureeye-authd` and the
  transitional metapackage. Existing installs are swapped automatically on
  upgrade.
- Changed: The recognition backends are ordinary distribution packages
  instead of a bundled virtualenv: `python3-mediapipe` (amd64/x86_64 only)
  and `python3-dlib`, from `ppa:vhrabar/tools` on Ubuntu and
  `copr:vhrabar/python-extras` on Fedora. Select one with `detector_backend`
  in `/etc/secureEye/config.ini`.
- Changed: The daemon and the `secureEye` launcher run on the system Python
  interpreter, so nothing has to be rebuilt after a Python upgrade. The
  systemd unit and the launcher now use the interpreter meson was configured
  with rather than a hardcoded virtualenv path.
- Changed: Releases no longer carry `.deb` or `.rpm` attachments. Install
  from the PPA, COPR or the AUR instead.
- Added: Arch Linux packaging is published to the AUR as `secure-eye`.
- Added: `CHANGELOG.md` is the single source of truth for release notes.
  `scripts/set-package-version.sh` renders a release's section into the
  Debian and RPM changelogs, and `scripts/changelog-section.sh` extracts it
  for the GitHub release body.
- Added: A single release workflow that runs the tests, verifies the deb,
  RPM and Arch packages build and install, and only then publishes to the
  Launchpad PPA, COPR and the AUR. COPR builds are pinned to the released
  tag.
- Added: A Prepare release workflow that sets the version, tags it and
  drafts the release from the changelog.
- Removed: The install-time virtualenv, the vendored Python wheels and the
  dpkg trigger that rebuilt the virtualenv whenever python3 was upgraded.
- Fixed: Launchpad PPA uploads carry the real changelog entries; every
  upload previously read "New upstream release".
- Fixed: Fedora and RHEL install instructions: the package ships no systemd
  preset, so `secureeye-authd.service` has to be enabled manually. The
  README claimed installation enabled it.
- Fixed: The CLI reference lists the `set` command.

* Mon Aug 17 2026 Vedran Hrabar <vedran.hrabar@outlook.com> - 0.1.2-1
- Merge libpam-secureeye and secureeye-authd into a single secure-eye package
  and drop the transitional metapackage
- Take the recognition backends from copr:vhrabar/python-extras
  (python3-mediapipe on x86_64, python3-dlib) instead of bundling wheels
- Drop the install-time virtualenv; the daemon runs on the system python3

* Thu Jul 02 2026 Vedran Hrabar <vedran.hrabar@outlook.com> - 0.1.1-1
- Initial RPM packaging
