#!/bin/sh

# unlocks so we can write on TC
fsunlock
# Common part
cp UDSClient /bin/udsclient
chmod 755 /bin/udsclient
cp UDSClient.desktop /usr/share/applications/UDSClient.desktop
# RDP Script for UDSClient. Launchs udsclient using the "Template_UDS" profile
cp udsrdp /usr/bin

INSTALLED=0
# Installation for 7.1.x version
grep -q "7.1" /etc/issue
if [ $? -eq 0 ]; then
    echo "Installing for 7.1 version"
    # Allow UDS apps without asking
    cp firefox7.1/syspref.js /etc/firefox
    # Copy handlers.json for firefox
    mkdir -p /lib/UDSClient/firefox/ > /dev/null 2>&1
    cp firefox7.1/handlers.json /lib/UDSClient/firefox/
    # and runner
    cp firefox7.1/45-uds /etc/hptc-firefox-mgr/prestart
    INSTALLED=1
else
    echo "Installing for > 7.1 version"
    # Copy handlers for firefox
    mkdir -p /lib/UDSClient/firefox/ > /dev/null 2>&1
    # Copy handlers.json for firefox
    cp firefox/handlers.json /lib/UDSClient/firefox/
    cp firefox/45-uds /etc/hptc-firefox-mgr/prestart
    # copy uds handler for firefox
    cp firefox/uds /usr/share/hptc-firefox-mgr/handlers/uds
    chmod 755 /usr/share/hptc-firefox-mgr/handlers/uds
    INSTALLED=1
fi

# If not installed, show a message
if [ $INSTALLED -eq 0 ]; then
    echo "UDSClient is not installable for this version of ThinPro: "
    cat /etc/issue
fi

fslock
