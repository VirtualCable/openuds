#!/usr/bin/make -f
# -*- makefile -*-

SOURCEDIR := ../src
LIBDIR := $(DESTDIR)/usr/share/pyshared/UDSActor
BINDIR := $(DESTDIR)/usr/bin
SBINDIR = $(DESTDIR)/usr/sbin
APPSDIR := $(DESTDIR)/usr/share/applications
CFGDIR := $(DESTDIR)/etc/udsactor
POLKITDIR := $(DESTDIR)/usr/share/polkit-1/actions/
PYC := $(shell find $(SOURCEDIR) -name '*.py[co]')
CACHES := $(shell find $(SOURCEDIR) -name '__pycache__')

clean:
	rm -rf $(PYC) $(CACHES) $(DESTDIR)
install:
	mkdir -p $(LIBDIR)
	mkdir -p $(BINDIR)
	mkdir -p $(SBINDIR)
	mkdir -p $(APPSDIR)
	mkdir -p $(CFGDIR)
	mkdir -p $(POLKITDIR)
	
	mkdir $(LIBDIR)/img
	
	rm -f $(PYC) $(CACHES)
	cp -r $(SOURCEDIR)/udsactor $(LIBDIR)/udsactor
	cp $(SOURCEDIR)/img/uds.png $(LIBDIR)/img

	cp $(SOURCEDIR)/UDSActorConfig.py $(LIBDIR)
	cp $(SOURCEDIR)/UDSActorUser.py $(LIBDIR)
	cp $(SOURCEDIR)/setup_dialog_ui.py $(LIBDIR)
	
	# Menu GUI app
	cp UDS_Actor_Configuration.desktop $(APPSDIR)
	# binaries
	cp udsactor $(BINDIR)
	cp UDSActorConfig-pkexec $(SBINDIR)
	
	# Policy to run as administrator
	cp org.openuds.pkexec.UDSActorConfig.policy $(POLKITDIR)

	# Fix permissions
	chmod 755 $(BINDIR)/udsactor
	chmod 755 $(LIBDIR)/UDSActorConfig.py
	chmod 755 $(LIBDIR)/UDSActorUser.py
	chmod 644 $(POLKITDIR)/org.openuds.pkexec.UDSActorConfig.policy
	
	# chmod 0755 $(BINDIR)/udsactor
uninstall:
	rm -rf $(LIBDIR)
	# rm -f $(BINDIR)/udsactor
	rm -rf $(CFGDIR)