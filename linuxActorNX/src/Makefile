BINDIR = $(DESTDIR)/usr/bin

clean:
	echo "Clean"
install:
	mkdir -p $(BINDIR)
	cp udsnxstart.sh $(BINDIR)/udsnxstart
	cp udsnxstop.sh $(BINDIR)/udsnxstop
	
	chmod 0755 $(BINDIR)/udsnxstart
	chmod 0755 $(BINDIR)/udsnxstop
uninstall:
	echo "Uninstall"
