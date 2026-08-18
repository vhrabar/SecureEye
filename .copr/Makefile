VERSION := $(shell git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//; s/-/~/g' | grep .)
SPEC := secureEye/rpm/secure-eye.spec
outdir ?= $(CURDIR)
topdir := $(CURDIR)/.copr-rpmbuild

.PHONY: srpm
srpm:
	dnf -y install git rpm-build
	git config --global --add safe.directory $(CURDIR)
	scripts/set-package-version.sh "$(VERSION)"
	git -c user.name=copr -c user.email=copr@localhost \
	    commit -qam "generated packaging for $(VERSION)" --allow-empty
	mkdir -p "$(topdir)/SOURCES" "$(outdir)"
	git archive --format=tar.gz \
	    --prefix="secure-eye-$(VERSION)/" \
	    -o "$(topdir)/SOURCES/secure-eye-$(VERSION).tar.gz" HEAD
	cp secureEye/rpm/secure-eye.sysusers "$(topdir)/SOURCES/"
	rpmbuild -bs $(SPEC) \
	    --define "_topdir $(topdir)" \
	    --define "pkg_version $(VERSION)" \
	    --define "_srcrpmdir $(outdir)"
