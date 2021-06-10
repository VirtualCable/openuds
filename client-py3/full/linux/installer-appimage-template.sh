#!/bin/sh

echo "Installing UDSClient..."

cp UDSClient-0.0.0-x86_64.AppImage /usr/bin
cp UDSClient.desktop /usr/share/applications
update-desktop-database

echo "Installation process done."
