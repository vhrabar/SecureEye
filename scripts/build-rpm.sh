#!/usr/bin/env bash
# Build SecureEye RPMs inside a Fedora container (GitHub release artifacts).
# Env: PKG_VERSION (required), MARCH, REL_SUFFIX. Output: dist/*.rpm.
# Nothing is vendored: the recognition backends are runtime Requires resolved
# from copr:vhrabar/python-extras at install time.
set -euxo pipefail

: "${PKG_VERSION:?PKG_VERSION is required}"
SPEC=secureEye/rpm/secure-eye.spec

dnf install -y --setopt=install_weak_deps=False \
    rpm-build rpmdevtools rpmlint git-core tar gzip dnf-plugins-core

git config --global --add safe.directory "$PWD"
dnf builddep -y --define "pkg_version ${PKG_VERSION}" "$SPEC"

rpmdev-setuptree
git archive --format=tar.gz \
    --prefix="secure-eye-${PKG_VERSION}/" \
    -o "$HOME/rpmbuild/SOURCES/secure-eye-${PKG_VERSION}.tar.gz" HEAD
cp secureEye/rpm/secure-eye.sysusers "$HOME/rpmbuild/SOURCES/"

rpmbuild -bb "$SPEC" \
    --define "pkg_version ${PKG_VERSION}" \
    ${REL_SUFFIX:+--define "rel_suffix ${REL_SUFFIX}"} \
    ${MARCH:+--define "march ${MARCH}"}

mkdir -p dist
cp "$HOME"/rpmbuild/RPMS/*/*.rpm dist/
ls -la dist

# Report only; the build script does not fail on lint findings yet.
rpmlint dist/*.rpm || true
