#!/bin/bash

VERSION=`cat ../../../VERSION`
RELEASE=1
# Debian based
dpkg-buildpackage -b

# Now rpm based
top=`pwd`

cat udsclient-template.spec | 
  sed -e s/"version 0.0.0"/"version ${VERSION}"/g |
  sed -e s/"release 1"/"release ${RELEASE}"/g > udsclient-$VERSION.spec
  
# Now fix dependencies for opensuse
cat udsclient-template.spec | 
  sed -e s/"version 0.0.0"/"version ${VERSION}"/g |
  sed -e s/"name udsclient"/"name udsclient-opensuse"/g |
  sed -e s/"PyQt4"/"python-qt4"/g |
  sed -e s/"libXScrnSaver"/"libXss1"/g > udsclient-opensuse-$VERSION.spec


# Right now, udsactor-xrdp-.spec is not needed
for pkg in udsclient-$VERSION.spec udsclient-opensuse-$VERSION.spec; do
    
    rm -rf rpm
    for folder in SOURCES BUILD RPMS SPECS SRPMS; do
        mkdir -p rpm/$folder
    done
    
    rpmbuild -v -bb --clean --buildroot=$top/rpm/BUILD/$pkg-root --target noarch $pkg 2>&1
done

#rm udsclient-$VERSION

make DESTDIR=targz DISTRO=targz VERSION=${VERSION} install
