VERSION := $(shell git describe --tags --exact-match 2>/dev/null | sed 's/^v//' || echo 0.1.1)
SPEC := secureEye/rpm/secure-eye.spec
outdir ?= $(CURDIR)

.PHONY: srpm
srpm:
	dnf -y install git rpm-build rpmdevtools
	git config --global --add safe.directory $(CURDIR)
	rpmdev-setuptree
	git archive --format=tar.gz \
	    --prefix="secure-eye-$(VERSION)/" \
	    -o "$(HOME)/rpmbuild/SOURCES/secure-eye-$(VERSION).tar.gz" HEAD
	cp secureEye/rpm/secureeye-authd.sysusers "$(HOME)/rpmbuild/SOURCES/"
	rpmbuild -bs $(SPEC) \
	    --define "pkg_version $(VERSION)" \
	    --define "_srcrpmdir $(outdir)"
