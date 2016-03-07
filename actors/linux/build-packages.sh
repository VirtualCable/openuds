#!/bin/bash

VERSION=`cat ../../VERSION`
RELEASE=1

top=`pwd`

# Debian based
dpkg-buildpackage -b

cat udsactor-template.spec | 
  sed -e s/"version 0.0.0"/"version ${VERSION}"/g |
  sed -e s/"release 1"/"release ${RELEASE}"/g > udsactor-$VERSION.spec
  
# Now fix dependencies for opensuse
cat udsactor-template.spec | 
  sed -e s/"version 0.0.0"/"version ${VERSION}"/g |
  sed -e s/"name udsactor"/"name udsactor-opensuse"/g |
  sed -e s/"PyQt4"/"python-qt4"/g |
  sed -e s/"libXScrnSaver"/"libXss1"/g > udsactor-opensuse-$VERSION.spec


# Right now, udsactor-xrdp-1.7.0.spec is not needed
for pkg in udsactor-$VERSION.spec udsactor-opensuse-$VERSION.spec; do
    
    rm -rf rpm
    for folder in SOURCES BUILD RPMS SPECS SRPMS; do
        mkdir -p rpm/$folder
    done
    
    rpmbuild -v -bb --clean --buildroot=$top/rpm/BUILD/$pkg-root --target noarch $pkg 2>&1
done

#rm udsactor-$VERSION
