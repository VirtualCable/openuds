#!/usr/bin/make -f
# -*- makefile -*-

.PHONY: install-udsactor install-udsactor-unmanaged

# Directories
SOURCEDIR := ../src
LIBDIR := $(DESTDIR)/usr/share/UDSActor
BINDIR := $(DESTDIR)/usr/bin
SBINDIR = $(DESTDIR)/usr/sbin
APPSDIR := $(DESTDIR)/usr/share/applications
CFGDIR := $(DESTDIR)/etc/udsactor
SYSTEMDIR := $(DESTDIR)/etc/systemd/system
POLKITDIR := $(DESTDIR)/usr/share/polkit-1/actions/
XDGAUTOSTARTDIR := $(DESTDIR)/etc/xdg/autostart
KDEAUTOSTARTDIR := $(DESTDIR)/usr/share/autostart

PYC := $(shell find $(SOURCEDIR) -name '*.py[co]')
CACHES := $(shell find $(SOURCEDIR) -name '__pycache__' -o -name '.mypy_cache')

clean:
	rm -rf $(PYC) $(CACHES) $(DESTDIR)

install-udsactor: udsactor

install-udsactor-unmanaged: udsactor udsactor-unmanaged

udsactor-unmanaged:
	# Overwrite udsactor config is what to be done
	cp scripts/UDSActorConfig-unmanaged $(SBINDIR)/UDSActorConfig

udsactor:
	rm -rf $(DESTDIR)
	mkdir -p $(LIBDIR)
	mkdir -p $(BINDIR)
	mkdir -p $(SBINDIR)
	mkdir -p $(APPSDIR)
	mkdir -p $(CFGDIR)
	mkdir -p $(POLKITDIR)
	mkdir -p $(XDGAUTOSTARTDIR)
	mkdir -p $(KDEAUTOSTARTDIR)

	mkdir $(LIBDIR)/img

	# Cleans up .pyc and cache folders
	rm -f $(PYC) $(CACHES)
	
	cp -r $(SOURCEDIR)/udsactor $(LIBDIR)/udsactor
	cp $(SOURCEDIR)/img/uds-icon.png $(LIBDIR)/img

	cp $(SOURCEDIR)/actor_*.py $(LIBDIR)
	# QT Dialogs & resources
	cp -r $(SOURCEDIR)/ui $(LIBDIR)/ui
	
	# Menu GUI app
	cp desktop/UDS_Actor_Configuration.desktop $(APPSDIR)
	
	# Autostart elements for gnome/kde
	cp desktop/UDSActorTool.desktop $(XDGAUTOSTARTDIR)
	cp desktop/UDSActorTool.desktop $(KDEAUTOSTARTDIR)
	
	# scripts
	cp scripts/udsactor $(BINDIR)
	cp scripts/UDSActorConfig $(SBINDIR)
	cp scripts/UDSActorConfig-pkexec $(SBINDIR)
	cp scripts/UDSActorTool $(BINDIR)
	cp scripts/UDSActorTool-startup $(BINDIR)
	cp scripts/udsvapp ${BINDIR}
	
	# Policy to run as administrator
	cp policy/org.openuds.pkexec.UDSActorConfig.policy $(POLKITDIR)

	# Fix permissions
	chmod 755 $(BINDIR)/udsactor
	chmod 755 $(BINDIR)/udsvapp
	chmod 755 $(BINDIR)/UDSActorTool-startup
	chmod 755 $(SBINDIR)/UDSActor*
	chmod 755 $(LIBDIR)/actor_*.py
	chmod 644 $(POLKITDIR)/org.openuds.pkexec.UDSActorConfig.policy

	# If for red hat based, copy init.d
ifeq ($(DISTRO),rh)
	mkdir -p $(SYSTEMDIR)
	cp debian/udsactor.service $(SYSTEMDIR)/
endif

	# chmod 0755 $(BINDIR)/udsactor
uninstall:
	rm -rf $(LIBDIR)
	# rm -f $(BINDIR)/udsactor
	rm -rf $(CFGDIR)
