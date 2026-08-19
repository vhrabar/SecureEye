SPEC := secureEye/rpm/secure-eye.spec
outdir ?= $(CURDIR)
topdir := $(CURDIR)/.copr-rpmbuild

.PHONY: srpm
srpm:
	dnf -y install git rpm-build
	git config --global --add safe.directory $(CURDIR)
	set -eu; \
	version="$$(git describe --tags --abbrev=0 2>/dev/null | sed 's/^v//; s/-/~/g')"; \
	if [ -z "$$version" ]; then \
	    echo "no tag to take the version from: submit the build with --commit <tag> so the clone is checked out at a tagged commit" >&2; \
	    exit 1; \
	fi; \
	echo "building secure-eye $$version"; \
	scripts/set-package-version.sh "$$version"; \
	git -c user.name=copr -c user.email=copr@localhost \
	    commit -qam "generated packaging for $$version" --allow-empty; \
	mkdir -p "$(topdir)/SOURCES" "$(outdir)"; \
	git archive --format=tar.gz \
	    --prefix="secure-eye-$$version/" \
	    -o "$(topdir)/SOURCES/secure-eye-$$version.tar.gz" HEAD; \
	cp secureEye/rpm/secure-eye.sysusers "$(topdir)/SOURCES/"; \
	rpmbuild -bs $(SPEC) \
	    --define "_topdir $(topdir)" \
	    --define "pkg_version $$version" \
	    --define "_srcrpmdir $(outdir)"
