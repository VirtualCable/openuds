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
ifeq ($(DISTRO),armhf)
	cat udsclient-appimage-x86_64.recipe | sed -e s/"version: 0.0.0"/"version: $(VERSION)"/g | sed -e s/amd64/armhf/g | sed -e s/x86_64/armhf/g > appimage.recipe
endif
ifeq ($(DISTRO),i686)
	cat udsclient-appimage-x86_64.recipe | sed -e s/"version: 0.0.0"/"version: $(VERSION)"/g | sed -e s/amd64/i386/g | sed -e s/x86_64/i686/g > appimage.recipe
endif
# Ensure all working folders are "clean"
	-rm -rf appimage appimage-builder-cache /tmp/UDSClientDir appimage-build AppDir

	appimage-builder --recipe appimage.recipe --appdir /tmp/UDSClientDir
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

# cleanup
	-rm -rf appimage appimage-builder-cache /tmp/UDSClientDir appimage-build AppDir *.zsync

build-igel:
	rm -rf $(DESTDIR)
	mkdir -p $(DESTDIR)
# Calculate the size of the custom partition (15 megas more than the appimage size)
	@$(eval APPIMAGE_SIZE=$(shell du -sm UDSClient-$(VERSION)-x86_64.AppImage | cut -f1))
	@$(eval APPIMAGE_SIZE=$(shell expr $(APPIMAGE_SIZE) + 15))
	cat igel/UDSClient-Profile-template.xml | sed -e s/"_SIZE_"/"$(APPIMAGE_SIZE)M"/g > $(DESTDIR)/UDSClient-Profile.xml
	cat igel/UDSClient-template.inf | sed -e s/"_SIZE_"/"$(APPIMAGE_SIZE)M"/g > $(DESTDIR)/UDSClient.inf
	cp UDSClient-$(VERSION)-x86_64.AppImage $(DESTDIR)/UDSClient
	cp igel/UDSClient.desktop $(DESTDIR)/UDSClient.desktop
	cp igel/init.sh $(DESTDIR)/init.sh
	tar cjvf $(DESTDIR)/UDSClient.tar.bz2 -C $(DESTDIR) UDSClient UDSClient.desktop init.sh
	zip -j ../udsclient3-$(VERSION)-igel.zip $(DESTDIR)/UDSClient-Profile.xml $(DESTDIR)/UDSClient.inf $(DESTDIR)/UDSClient.tar.bz2
	cd ..
	rm -rf $(DESTDIR)

build-thinpro:
	rm -rf $(DESTDIR)
	mkdir -p $(DESTDIR)
	cp -r thinpro/* $(DESTDIR)
	cp UDSClient-$(VERSION)-x86_64.AppImage $(DESTDIR)/UDSClient
	tar czvf ../udsclient3-$(VERSION)-thinpro.tar.gz -C $(DESTDIR) .
	rm -rf $(DESTDIR)

