VERSION := $(shell git describe --tags --exact-match 2>/dev/null | sed 's/^v//' | grep . || echo 0.1.1)
SPEC := secureEye/rpm/secure-eye.spec
outdir ?= $(CURDIR)
topdir := $(CURDIR)/.copr-rpmbuild

.PHONY: srpm
srpm:
	dnf -y install git rpm-build
	git config --global --add safe.directory $(CURDIR)
	mkdir -p "$(topdir)/SOURCES" "$(outdir)"
	git archive --format=tar.gz \
	    --prefix="secure-eye-$(VERSION)/" \
	    -o "$(topdir)/SOURCES/secure-eye-$(VERSION).tar.gz" HEAD
	cp secureEye/rpm/secureeye-authd.sysusers "$(topdir)/SOURCES/"
	rpmbuild -bs $(SPEC) \
	    --define "_topdir $(topdir)" \
	    --define "pkg_version $(VERSION)" \
	    --define "_srcrpmdir $(outdir)"
