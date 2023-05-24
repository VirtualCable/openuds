#!/bin/sh

cp -r usr/lib/UDSClient /usr/lib/UDSClient
cp -r usr/share/applications /usr/share/applications -R
update-desktop-database

echo "Installation process done."
echo "Remember that the following packages must be installed on system:"
echo "* Python3 paramiko"
echo "* Python3 PyQt6 or PyQt5"
echo "* Python3 six"
echo "* Python3 requests"
echo "* Python3 cryptography"
echo "Theese packages (as their names), are dependent on your platform, so you must locate and install them"
echo "Also, ensure that a /media folder exists on your machine, that will be redirected on RDP connections"
