#!/bin/sh

python setup.py py2app --optimize 2 --plist Info.plist
rm udsclient.dmg 
hdiutil create -srcfolder dist/udsclient.app udsclient.dmg
