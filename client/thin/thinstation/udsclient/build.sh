#!/bin/sh
pip install paramiko requests six
rm -rf lib
mkdir -p lib/python2.7/site-packages
for a in requests paramiko pyasn1 cryptography packaging idna asn1crypto six enum ipaddress cffi ; do cp -r /usr/lib/python2.7/site-packages/$a* lib/python2.7/site-packages/; done
cp src/udsclient bin
chmod 755 bin/udsclient
mkdir lib/UDSClient
cp src/UDSClient.py lib/UDSClient
chmod 755 lib/UDSClient/UDSClient.py
cp -r src/uds lib/UDSClient
mkdir lib/applications
cp UDSClient.desktop lib/applications
