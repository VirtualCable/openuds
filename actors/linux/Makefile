#!/usr/bin/make -f
# -*- makefile -*-

# Directories
SOURCEDIR := ../src
LIBDIR := $(DESTDIR)/usr/share/UDSActor
BINDIR := $(DESTDIR)/usr/bin
SBINDIR = $(DESTDIR)/usr/sbin
APPSDIR := $(DESTDIR)/usr/share/applications
CFGDIR := $(DESTDIR)/etc/udsactor
INITDIR := $(DESTDIR)/etc/init.d
POLKITDIR := $(DESTDIR)/usr/share/polkit-1/actions/
XDGAUTOSTARTDIR := $(DESTDIR)/etc/xdg/autostart
KDEAUTOSTARTDIR := $(DESTDIR)/usr/share/autostart

PYC := $(shell find $(SOURCEDIR) -name '*.py[co]')
CACHES := $(shell find $(SOURCEDIR) -name '__pycache__')

clean:
	rm -rf $(PYC) $(CACHES) $(DESTDIR)
install-udsactor-xrdp:
	mkdir -p $(BINDIR)
	cp scripts/uds-sesman.sh $(BINDIR)/uds-sesman
	cp scripts/uds-wait-session.sh $(BINDIR)/uds-wait-session
	
	chmod 0755 $(BINDIR)/uds-sesman
	chmod 0755 $(BINDIR)/uds-wait-session

install-udsactor-nx:
	mkdir -p $(BINDIR)
	cp scripts/udsnxstart.sh $(BINDIR)/udsnxstart
	cp scripts/udsnxstop.sh $(BINDIR)/udsnxstop
	
	chmod 0755 $(BINDIR)/udsnxstart
	chmod 0755 $(BINDIR)/udsnxstop
install-udsactor:
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
	cp $(SOURCEDIR)/img/uds.png $(LIBDIR)/img

	cp $(SOURCEDIR)/UDSActorConfig.py $(LIBDIR)
	cp $(SOURCEDIR)/UDSActorUser.py $(LIBDIR)
	# QT Dialogs & resources
	cp $(SOURCEDIR)/*_ui.py $(LIBDIR)
	cp $(SOURCEDIR)/UDSActor_rc.py $(LIBDIR)
	
	# Menu GUI app
	cp desktop/UDS_Actor_Configuration.desktop $(APPSDIR)
	
	# Autostart elements for gnome/kde
	cp desktop/UDSActorTool.desktop $(XDGAUTOSTARTDIR)
	cp desktop/UDSActorTool.desktop $(KDEAUTOSTARTDIR)
	
	# scripts
	cp scripts/udsactor $(BINDIR)
	cp scripts/UDSActorConfig-pkexec $(SBINDIR)
	cp scripts/UDSActorTool-startup $(BINDIR)
	cp scripts/udsvapp ${BINDIR}
	
	# Policy to run as administrator
	cp policy/org.openuds.pkexec.UDSActorConfig.policy $(POLKITDIR)

	# Fix permissions
	chmod 755 $(BINDIR)/udsactor
	chmod 755 $(BINDIR)/udsvapp
	chmod 755 $(BINDIR)/UDSActorTool-startup
	chmod 755 $(SBINDIR)/UDSActorConfig-pkexec
	chmod 755 $(LIBDIR)/UDSActorConfig.py
	chmod 755 $(LIBDIR)/UDSActorUser.py
	chmod 644 $(POLKITDIR)/org.openuds.pkexec.UDSActorConfig.policy
	
	# If for red hat based, copy init.d
ifeq ($(DISTRO),rh)
	mkdir -p $(INITDIR)
	cp debian/udsactor.init $(INITDIR)/udsactor
	ln -s /usr/share/UDSActor/UDSActorConfig.py $(SBINDIR)/UDSActorConfig
	ln -s /usr/share/UDSActor/UDSActorUser.py $(BINDIR)/UDSActorTool
endif
	
	# chmod 0755 $(BINDIR)/udsactor
uninstall:
	rm -rf $(LIBDIR)
	# rm -f $(BINDIR)/udsactor
	rm -rf $(CFGDIR)
