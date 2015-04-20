#!/bin/sh

cp -r usr/lib/UDSClient /usr/lib/UDSClient
cp -r usr/share/applications /usr/lib/applications -R
update-desktop-database

echo "Installation process done."
echo "Remembar that the following packages must be installed on system:"
echo "* Python paramiko"
echo "* Python pyqt4"
echo "Theese packages (as their names), are dependent on your platform, so you must locate and install them"
echo "You can install them directly on any platform with pip, using this simple command: "
echo "pip install PyQt4 paramiko"

