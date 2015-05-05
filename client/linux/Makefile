#!/usr/bin/make -f
# -*- makefile -*-

# Version
# VERSION := 1.7.5

# Directories
SOURCEDIR := ../src
LIBDIR := $(DESTDIR)/usr/lib/UDSClient
BINDIR := $(DESTDIR)/usr/bin
SBINDIR = $(DESTDIR)/usr/sbin
APPSDIR := $(DESTDIR)/usr/share/applications

PYC := $(shell find $(SOURCEDIR) -name '*.py[co]')
CACHES := $(shell find $(SOURCEDIR) -name '__pycache__')

clean:
	rm -rf $(PYC) $(CACHES) $(DESTDIR)
install:
	rm -rf $(DESTDIR)
	mkdir -p $(LIBDIR)
	#mkdir -p $(BINDIR)
	#mkdir -p $(SBINDIR)
	mkdir -p $(APPSDIR)
	
	mkdir $(LIBDIR)/uds
	
	# Cleans up .pyc and cache folders
	rm -f $(PYC) $(CACHES)
	
	cp $(SOURCEDIR)/uds/*.py $(LIBDIR)/uds

	cp $(SOURCEDIR)/UDS*.py $(LIBDIR)
	
	
	# URL Catchers elements for gnome/kde
	cp desktop/UDSClient.desktop $(APPSDIR)
	
	chmod 755 $(LIBDIR)/UDSClient.py

ifeq ($(DISTRO),targz)
	cp installer.sh $(DESTDIR)/install.sh
	tar czvf ../udsclient-$(VERSION).tar.gz -C $(DESTDIR) .
endif

	
	# chmod 0755 $(BINDIR)/udsclient
uninstall:
	rm -rf $(LIBDIR)
	# rm -f $(BINDIR)/udsclient
	#  rm -rf $(CFGDIR)
