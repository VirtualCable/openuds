#!/bin/bash


top=`pwd`
rm -rf rpm
for folder in SOURCES BUILD RPMS SPECS SRPMS; do
    mkdir -p rpm/$folder
done

for pkg in udsactor-1.7.0.spec udsactor-xrdp-1.7.0.spec; do
    rpmbuild -v -bb --clean --target noarch $pkg 2>&1
done

