#!/usr/bin/make -f
# -*- makefile -*-

SOURCEDIR := ../src
LIBDIR := $(DESTDIR)/usr/share/pyshared/UDSActor
BINDIR := $(DESTDIR)/usr/bin
SBINDIR := $(DESTDIR)/usr/sbin
APPSDIR := $(DESTDIR)/usr/share/applications
CFGDIR := $(DESTDIR)/etc/udsactor
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
	
	mkdir -p $(LIBDIR)/
	rm -f $(PYC) $(CACHES)
	cp -r $(SOURCEDIR)/udsactor $(LIBDIR)/udsactor

	cp $(SOURCEDIR)/UDSActorConfig.py $(LIBDIR)
	cp $(SOURCEDIR)/UDSActorUser.py $(LIBDIR)
	cp $(SOURCEDIR)/setup_dialog_ui.py $(LIBDIR)
	
	cp UDS_Actor_Configuration.desktop $(APPSDIR)
	cp udsactor-daemon $(SBINDIR)
	chmod 755 $(SBINDIR)/udsactor-daemon
	
	# chmod 0755 $(BINDIR)/udsactor
uninstall:
	rm -rf $(LIBDIR)
	# rm -f $(BINDIR)/udsactor
	rm -rf $(CFGDIR)