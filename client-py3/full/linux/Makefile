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
	tar czvf ../udsclient3-$(VERSION).tar.gz -C $(DESTDIR) .
endif

ifeq ($(DISTRO),rh)
endif

uninstall:
	rm -rf $(LIBDIR)
	# rm -f $(BINDIR)/udsclient
	#  rm -rf $(CFGDIR)

build-appimage:
ifeq ($(DISTRO),x86_64)
	cat udsclient-appimage-x86_64.recipe | sed -e s/"version: 0.0.0"/"version: $(VERSION)"/g > appimage.recipe
endif
ifeq ($(DISTRO),armf)
	cat udsclient-appimage-x86_64.recipe | sed -e s/"version: 0.0.0"/"version: $(VERSION)"/g | sed -e s/amd64\\\|x86_64/armhf/g > appimage.recipe
endif
ifeq ($(DISTRO),i686)
	cat udsclient-appimage-x86_64.recipe | sed -e s/"version: 0.0.0"/"version: $(VERSION)"/g | sed -e s/amd64/i386/g | sed -e s/x86_64/i686/g > appimage.recipe
endif
# In case of error, continue
	-rm -rf appimage appimage-builder-cache /tmp/UDSClientDir

	appimage-builder --recipe appimage.recipe
# Now create dist and move appimage
	rm -rf $(DESTDIR)
	mkdir -p $(DESTDIR)
	cp UDSClient-$(VERSION)-$(DISTRO).AppImage $(DESTDIR)
# Generate the .desktop fixed for new path
	cat desktop/UDSClient.desktop | sed -e s/".usr.lib.UDSClient.UDSClient.py"/"\/usr\/bin\/UDSClient-$(VERSION)-$(DISTRO).AppImage"/g > $(DESTDIR)/UDSClient.desktop
# And also, generater installer
	cat installer-appimage-template.sh | sed -e s/"0.0.0"/"$(VERSION)"/g | sed -e s/x86_64/$(DISTRO)/g > $(DESTDIR)/installer.sh
	chmod 755 $(DESTDIR)/installer.sh
	tar czvf ../udsclient3-$(DISTRO)-$(VERSION).tar.gz -C $(DESTDIR) .
