#!/bin/bash


top=`pwd`
#rm -rf rpm
for folder in SOURCES BUILD RPMS SPECS SRPMS; do
    mkdir -p rpm/$folder
done
rpmbuild -v -bb --clean --target noarch 'udsactor-1.7.0.spec' 2>&1
