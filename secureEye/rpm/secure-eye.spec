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
# copr:vhrabar/python-extras (python3-mediapipe, x86_64 only; python3-dlib) and
# the rest come from Fedora. Add that COPR as an external repository of the
# SecureEye project so the builds and installs can resolve them.

%{!?pkg_version:%global pkg_version 0.1.4}


%undefine __brp_python_bytecompile

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

Requires:       python3 >= 3.12
Requires:       python3-numpy
Requires:       python3-opencv
Requires:       python3-matplotlib
Requires:       python3-cffi
# Recognition backends, from copr:vhrabar/python-extras. mediapipe is the
# default backend and is x86_64-only; dlib is the alternative and the only
# backend on other architectures.
%ifarch x86_64
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
/etc/secureEye/config.ini: mediapipe (the default, x86_64 only) or dlib. The
daemon runs on the system Python interpreter, so there is nothing to rebuild
after a Python upgrade.

Unlike Debian/Ubuntu there is no pam-auth-update on Fedora; enable the module
manually or via an authselect custom profile (see README.Fedora.md).

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
    -Duser_models_dir=%{_sysconfdir}/secureEye/models
meson compile -C %{_vpath_builddir}

%install
DESTDIR=%{buildroot} meson install -C %{_vpath_builddir}

rm -rf %{buildroot}%{_datadir}/dlib-data

# User models directory (user_models_dir).
install -d -m 0755 %{buildroot}%{_sysconfdir}/secureEye/models

# sysusers fragment.
install -D -m 0644 %{SOURCE1} %{buildroot}%{_sysusersdir}/secure-eye.conf

%pre
%sysusers_create_compat %{SOURCE1}

%post
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
%{_sysusersdir}/secure-eye.conf
%{_datadir}/bash-completion/completions/secureEye
%dir %{_datadir}/secureEye
%{_datadir}/secureEye/logo.png
%{_mandir}/man1/SecureEye.1*
%dir %{_sysconfdir}/secureEye
%config(noreplace) %{_sysconfdir}/secureEye/config.ini
%dir %{_sysconfdir}/secureEye/models

%changelog
* Tue Aug 18 2026 Vedran Hrabar <vedran.hrabar@outlook.com> - 0.1.4-1
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
