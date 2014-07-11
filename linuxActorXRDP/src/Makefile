BINDIR = $(DESTDIR)/usr/bin

clean:
	echo "Clean"
install:
	mkdir -p $(BINDIR)
	cp uds-sesman.sh $(BINDIR)/uds-sesman
	cp uds-wait-session.sh $(BINDIR)/uds-wait-session
	
	chmod 0755 $(BINDIR)/uds-sesman
	chmod 0755 $(BINDIR)/uds-wait-session
uninstall:
	echo "Uninstall"
