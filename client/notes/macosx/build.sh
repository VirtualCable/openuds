#!/bin/sh

python setup.py py2app --optimize 2 --plist Info.plist
rm UDSClient.dmg 
hdiutil create -srcfolder dist/UDSClient.app UDSClient.dmg
