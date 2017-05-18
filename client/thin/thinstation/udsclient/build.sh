#!/bin/bash
pip install paramiko requests six
rm -rf lib
mkdir -p lib/python2.7/site-packages
for a in requests paramiko pyasn1 cryptography packaging idna asn1crypto six enum ipaddress cffi ; do cp -r /usr/lib/python2.7/site-packages/$a* lib/python2.7/site-packages/; done
