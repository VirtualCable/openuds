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
# Note: Right now, opensuse & rh seems to have same dependencies, only 1 package needed
# cat udsclient-template.spec | 
#   sed -e s/"version 0.0.0"/"version ${VERSION}"/g |
#   sed -e s/"name udsclient3"/"name udsclient3-opensuse"/g > udsclient-opensuse-$VERSION.spec

# Right now, udsactor-xrdp-.spec is not needed
# for pkg in udsclient-$VERSION.spec udsclient-opensuse-$VERSION.spec; do
for pkg in udsclient-$VERSION.spec; do
    
    rm -rf rpm
    for folder in SOURCES BUILD RPMS SPECS SRPMS; do
        mkdir -p rpm/$folder
    done
    
    rpmbuild -v -bb --clean --buildroot=$top/rpm/BUILD/$pkg-root --target noarch $pkg 2>&1
done

#rm udsclient-$VERSION

# Make .tar.gz with source
make DESTDIR=targz DISTRO=targz VERSION=${VERSION} install

# And make FULL CLIENT .tar.gz for x86 and raspberry
make DESTDIR=appimage DISTRO=x86_64 VERSION=${VERSION} build-appimage
make DESTDIR=appimage DISTRO=armhf VERSION=${VERSION} build-appimage
make DESTDIR=appimage DISTRO=i686 VERSION=${VERSION} build-appimage

# Now create igel version
# we need first to create the Appimage for x86_64
make DESTDIR=igelimage DISTRO=x86_64 VERSION=${VERSION} build-igel

# Create the thinpro version
make DESTDIR=thinproimage DISTRO=x86_64 VERSION=${VERSION} build-thinpro

rpm --addsign ../*rpm
