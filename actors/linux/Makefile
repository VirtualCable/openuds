SRCDIR = ../src
LIBDIR = $(DESTDIR)/usr/share/pyshared/UDSActor
BINDIR = $(DESTDIR)/usr/bin
CFGDIR = $(DESTDIR)/etc/udsactor
clean:
	rm -rf $(DESTDIR)
install:
	mkdir -p $(LIBDIR)
	mkdir -p $(BINDIR)
	mkdir -p $(CFGDIR)
	
	mkdir -p $(LIBDIR)/
	cp -r $(SRCDIR)/udsactor $(LIBDIR)/udsactor
	rm -rf $(LIBDIR)/*.py[co]

	cp $(SRCDIR)/UDSActorConfig.py $(LIBDIR)
	cp $(SRCDIR)/UDSActorUser.py $(LIBDIR)
	cp $(SRCDIR)/setup_dialog_ui.py $(LIBDIR)
	
	# chmod 0755 $(BINDIR)/udsactor
uninstall:
	rm -rf $(LIBDIR)
	# rm -f $(BINDIR)/udsactor
	rm -rf $(CFGDIR)