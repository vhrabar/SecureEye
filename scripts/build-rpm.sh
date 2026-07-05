#!/usr/bin/env bash
set -euxo pipefail

: "${PKG_VERSION:?PKG_VERSION is required}"
VENDOR_MEDIAPIPE="${VENDOR_MEDIAPIPE:-true}"

dnf install -y --setopt=install_weak_deps=False \
    rpm-build rpmdevtools rpmlint git-core tar gzip \
    meson ninja-build gcc-c++ pkgconf-pkg-config \
    pam-devel libevdev-devel inih-devel \
    python3-devel python3-pip python3-setuptools python3-wheel systemd-rpm-macros \
    cmake make openblas-devel libjpeg-turbo-devel libpng-devel

git config --global --add safe.directory "$PWD"
rpmdev-setuptree

# Source0: git archive of the tree
git archive --format=tar.gz \
    --prefix="secure-eye-${PKG_VERSION}/" \
    -o "$HOME/rpmbuild/SOURCES/secure-eye-${PKG_VERSION}.tar.gz" HEAD

# Source1: vendored wheels
rm -rf wheels && mkdir -p wheels
if [ "$VENDOR_MEDIAPIPE" = "true" ]; then
    python3 -m pip download \
        --only-binary=:all: --no-cache-dir --no-deps \
        --platform manylinux_2_28_x86_64 \
        --platform manylinux_2_17_x86_64 \
        --platform manylinux2014_x86_64 \
        --dest wheels \
        -r requirements-vendor.txt
else
    grep -iv '^[[:space:]]*mediapipe' requirements-vendor.txt > /tmp/reqs.txt
    python3 -m pip download \
        --only-binary=:all: --no-cache-dir --no-deps \
        --dest wheels \
        -r /tmp/reqs.txt

    if ls wheels-cache/dlib-*.whl >/dev/null 2>&1; then
        echo "Reusing cached dlib wheel from wheels-cache/"
        cp wheels-cache/dlib-*.whl wheels/
    else
        # Keep the version in sync with dlib_version in secure-eye.spec.
        python3 -m pip wheel --no-deps --no-cache-dir --wheel-dir wheels "dlib==20.0.1"
    fi
fi
ls -la wheels
tar -cf "$HOME/rpmbuild/SOURCES/secureeye-wheels.tar" wheels

# Source2: sysusers fragment
cp secureEye/rpm/secureeye-authd.sysusers "$HOME/rpmbuild/SOURCES/"

#  Build
rpmbuild -bb secureEye/rpm/secure-eye.spec \
    --define "pkg_version ${PKG_VERSION}" \
    ${REL_SUFFIX:+--define "rel_suffix ${REL_SUFFIX}"} \
    ${MARCH:+--define "march ${MARCH}"}

mkdir -p dist
cp "$HOME"/rpmbuild/RPMS/*/*.rpm dist/
ls -la dist

# report on err
rpmlint dist/*.rpm || true
