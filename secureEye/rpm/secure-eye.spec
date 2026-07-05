# RPM packaging for SecureEye
#
# CI passes:
#   --define "pkg_version X.Y.Z"       (from the release tag)
#   --define "rel_suffix .v3"          (x86-64-v3 build only)
#   --define "march x86-64-v3"         (x86-64-v3 build only)
#
# Sources (created by scripts/build-rpm.sh):
#   Source0  git archive of the tree
#   Source1  tar of vendored wheels (wheels/*.whl)
#   Source2  sysusers fragment

%{!?pkg_version:%global pkg_version 0.1.1}


%undefine __brp_python_bytecompile

%global authd_home %{_prefix}/lib/secureeye-authd

# dlib recognition backend for non-x86_64 -> temp till python3-dlib is
# ported from ppa/vhrabar
%global dlib_version 20.0.1

Name:           secure-eye
Version:        %{pkg_version}
Release:        1%{?rel_suffix}%{?dist}
Summary:        Transitional metapackage for SecureEye split packages
License:        GPL-2.0-only AND MIT
URL:            https://github.com/vhrabar/secureEye
Source0:        %{name}-%{version}.tar.gz
Source1:        secureeye-wheels.tar
Source2:        secureeye-authd.sysusers

BuildRequires:  meson >= 0.64
BuildRequires:  ninja-build
BuildRequires:  gcc-c++
BuildRequires:  pkgconf-pkg-config
BuildRequires:  pam-devel
BuildRequires:  libevdev-devel
# Provides INIReade
BuildRequires:  inih-devel
BuildRequires:  python3-devel
BuildRequires:  systemd-rpm-macros

# Non-x86_64 compiles the dlib wheel from source in %%build (see below).
%ifnarch x86_64
BuildRequires:  cmake
BuildRequires:  make
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
BuildRequires:  openblas-devel
BuildRequires:  libjpeg-turbo-devel
BuildRequires:  libpng-devel
%endif

Requires:       libpam-secureeye = %{version}-%{release}
Requires:       secureeye-authd = %{version}-%{release}

%description
Transitional metapackage that depends on the split SecureEye components
(libpam-secureeye and secureeye-authd).

%package -n libpam-secureeye
Summary:        SecureEye PAM module

%description -n libpam-secureeye
C/C++ PAM module for SecureEye face-authentication integration.
This package contains only PAM-facing components.

Unlike Debian/Ubuntu there is no pam-auth-update on Fedora; enable the
module manually or via an authselect custom profile (see README.Fedora.md).

%package -n secureeye-authd
Summary:        SecureEye authentication daemon and Python runtime components
Requires:       python3 >= 3.12
# %post builds the recognition venv with `python3 -m venv` + pip; on minimal
# Fedora that tooling is not pulled in by python3 alone (deb needs python3-venv).
Requires:       python3-pip
Requires:       python3-numpy
Requires:       python3-opencv
Requires:       python3-matplotlib
Requires:       python3-cffi
Requires:       portaudio
Requires:       v4l-utils
Recommends:     libpam-secureeye
%{?sysusers_requires_compat}
%{?systemd_requires}
# Wheels vendored into the runtime venv (see requirements-vendor.txt):
Provides:       bundled(python3dist(mediapipe))
Provides:       bundled(python3dist(ffmpeg-python))
Provides:       bundled(python3dist(keyboard))

%description -n secureeye-authd
Helper daemon and Python runtime stack used by SecureEye face
authentication. Includes systemd service assets and CLI tooling.
The recognition virtualenv is built at install time (%%post) from
wheels bundled in %{authd_home}/wheels — no network access is needed.

%prep
%autosetup -n %{name}-%{version}
tar -xf %{SOURCE1}   # -> wheels/

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
    -Dconfig_dir=%{_sysconfdir}/secureEye \
    -Duser_models_dir=%{_sysconfdir}/secureEye/models
meson compile -C %{_vpath_builddir}

%ifnarch x86_64
# build the dlib wheel from source for non-x86_64 arches (aarch64).
if ! ls wheels/dlib-*.whl >/dev/null 2>&1; then
    python3 -m pip wheel --no-deps --no-build-isolation --no-cache-dir \
        --wheel-dir wheels "dlib==%{dlib_version}"
fi
%endif

%install
DESTDIR=%{buildroot} meson install -C %{_vpath_builddir}

rm -rf %{buildroot}%{_datadir}/dlib-data

# User models directory (user_models_dir).
install -d -m 0755 %{buildroot}%{_sysconfdir}/secureEye/models

# sysusers fragment.
install -D -m 0644 %{SOURCE2} %{buildroot}%{_sysusersdir}/secureeye-authd.conf

# Vendored wheels + venv requirements
install -d -m 0755 %{buildroot}%{authd_home}/wheels
%ifarch x86_64
install -m 0644 requirements-vendor.txt %{buildroot}%{authd_home}/requirements.txt
# skip the aarch64-only dlib wheel here.
for whl in wheels/*.whl; do
    case "$(basename "$whl")" in
        dlib-*) echo "Skipping $whl on %{_arch}" ;;
        *) cp "$whl" %{buildroot}%{authd_home}/wheels/ ;;
    esac
done
%else

grep -iv '^[[:space:]]*mediapipe' requirements-vendor.txt > reqs-filtered.txt
echo 'dlib' >> reqs-filtered.txt
install -m 0644 reqs-filtered.txt %{buildroot}%{authd_home}/requirements.txt
for whl in wheels/*.whl; do
    case "$(basename "$whl")" in
        mediapipe-*) echo "Skipping $whl on %{_arch}" ;;
        *) cp "$whl" %{buildroot}%{authd_home}/wheels/ ;;
    esac
done
sed -i 's/^detector_backend = mediapipe/detector_backend = dlib/' \
    %{buildroot}%{_sysconfdir}/secureEye/config.ini
%endif

%pre -n secureeye-authd
%sysusers_create_compat %{SOURCE2}

%post -n secureeye-authd
%systemd_post secureeye-authd.service
# Build (or rebuild on upgrade) the recognition venv from the bundled wheels.
rm -rf %{authd_home}/venv
python3 -m venv --system-site-packages %{authd_home}/venv
# --no-deps: install the vendored wheels as-is
%{authd_home}/venv/bin/pip install --no-index --no-deps --no-cache-dir \
    --find-links %{authd_home}/wheels \
    -r %{authd_home}/requirements.txt

%preun -n secureeye-authd
%systemd_preun secureeye-authd.service

%postun -n secureeye-authd
%systemd_postun_with_restart secureeye-authd.service
if [ "$1" -eq 0 ]; then
    rm -rf %{authd_home}/venv
fi

%files
# metapackage: no files

%files -n libpam-secureeye
%license LICENSE licenses/MIT.txt
%doc NOTICE secureEye/rpm/README.Fedora.md
%{_libdir}/security/pam_secureEye.so

%files -n secureeye-authd
%license LICENSE licenses/MIT.txt
%doc NOTICE README.md
%{_bindir}/secureEye
%{_libdir}/secureEye/
%dir %{authd_home}
%{authd_home}/wheels/
%{authd_home}/requirements.txt
%ghost %dir %{authd_home}/venv
%{_unitdir}/secureeye-authd.service
%{_sysusersdir}/secureeye-authd.conf
%{_datadir}/bash-completion/completions/secureEye
%dir %{_datadir}/secureEye
%{_datadir}/secureEye/logo.png
%{_mandir}/man1/SecureEye.1*
%dir %{_sysconfdir}/secureEye
%config(noreplace) %{_sysconfdir}/secureEye/config.ini
%dir %{_sysconfdir}/secureEye/models

%changelog
* Thu Jul 02 2026 Vedran Hrabar <vedran.hrabar@outlook.com> - 0.1.1-1
- Initial RPM packaging
