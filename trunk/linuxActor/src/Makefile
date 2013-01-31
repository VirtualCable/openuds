LIBDIR = $(DESTDIR)/usr/share/pyshared/udsactor
BINDIR = $(DESTDIR)/usr/bin
CFGDIR = $(DESTDIR)/etc/udsactor
clean:
	rm -f *.py[co] */*.py[co]
install:
	mkdir -p $(LIBDIR)
	mkdir -p $(BINDIR)
	mkdir -p $(CFGDIR)
	
	mkdir -p $(LIBDIR)/uds/actor/renamer
	
	cp actor.py $(LIBDIR)/
	cp uds/*.py $(LIBDIR)/uds
	cp uds/actor/*.py $(LIBDIR)/uds/actor
	cp uds/actor/renamer/*.py $(LIBDIR)/uds/actor/renamer
	
	cp runActor.sh $(BINDIR)/udsactor
	
	cp udsactor.cfg $(CFGDIR)
	
	chmod 0755 $(BINDIR)/udsactor
uninstall:
	rm -rf $(LIBDIR)
	rm -f $(BINDIR)/udsactor
	rm -rf $(CFGDIR)