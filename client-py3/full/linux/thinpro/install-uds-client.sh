#!/bin/sh

# Common part

# unlocks so we can write on TC
fsunlock

cp UDSClient /bin/udsclient
chmod 755 /bin/udsclient
# RDP Script for UDSClient. Launchs udsclient using the "Template_UDS" profile
cp udsrdp /usr/bin

INSTALLED=0
# Installation for 7.1.x version
grep -q "7.1" /etc/issue
if [ $? -eq 0 ]; then
    echo "Installing for thinpro version 7.1"
    # Allow UDS apps without asking
    cp firefox7.1/syspref.js /etc/firefox
    # Copy handlers.json for firefox
    mkdir -p /lib/UDSClient/firefox/ > /dev/null 2>&1
    cp firefox7.1/handlers.json /lib/UDSClient/firefox/
    # and runner
    cp firefox7.1/45-uds /etc/hptc-firefox-mgr/prestart
else
    echo "Installing for thinpro version 7.2 or later"
    # Copy handlers for firefox
    mkdir -p /lib/UDSClient/firefox/ > /dev/null 2>&1
    # Copy handlers.json for firefox
    cp firefox/handlers.json /lib/UDSClient/firefox/
    cp firefox/45-uds /etc/hptc-firefox-mgr/prestart
    # copy uds handler for firefox
    cp firefox/uds /usr/share/hptc-firefox-mgr/handlers/uds
    chmod 755 /usr/share/hptc-firefox-mgr/handlers/uds
fi

# Common part
fslock
