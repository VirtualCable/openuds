#!/bin/bash

VERSION=`cat ../../VERSION`
RELEASE=1

top=`pwd`

# Debian based
dpkg-buildpackage -b

cat udsactor-template.spec | 
  sed -e s/"version 0.0.0"/"version ${VERSION}"/g |
  sed -e s/"release 1"/"release ${RELEASE}"/g > udsactor-$VERSION.spec
cat udsactor-unmanaged-template.spec | 
  sed -e s/"version 0.0.0"/"version ${VERSION}"/g |
  sed -e s/"release 1"/"release ${RELEASE}"/g > udsactor-unmanaged-$VERSION.spec
  
# Now fix dependencies for opensuse
# Note that, although on opensuse the library is "libXss1" on newer,
# the LibXscrnSaver is a "capability" and gets libXss1 installed
# So right now, we only need 1 uds actor for both platforms.
# cat udsactor-template.spec | 
#   sed -e s/"version 0.0.0"/"version ${VERSION}"/g |
#   sed -e s/"name udsactor"/"name udsactor-opensuse"/g |
#   sed -e s/"libXScrnSaver"/"libXss1"/g > udsactor-opensuse-$VERSION.spec

#for pkg in udsactor-$VERSION.spec udsactor-opensuse-$VERSION.spec; do
for pkg in udsactor-*$VERSION.spec; do
    
    rm -rf rpm
    for folder in SOURCES BUILD RPMS SPECS SRPMS; do
        mkdir -p rpm/$folder
    done
    
    rpmbuild -v -bb --clean --buildroot=$top/rpm/BUILD/$pkg-root --target noarch $pkg 2>&1
done

rpm --addsign ../*rpm
#rm udsactor-$VERSION
