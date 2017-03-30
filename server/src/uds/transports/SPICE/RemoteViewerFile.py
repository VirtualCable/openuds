'''
Created on May 6, 2015

@author: dkmaster
'''
from __future__ import unicode_literals
import six
import os


__updated__ = '2017-03-30'


TEMPLATE = '''[virt-viewer]
type={type}
host={host}
port={port}
password={password}
tls-port={tls_port}
fullscreen={fullscreen}
title={title}:%d - Press SHIFT+F12 to Release Cursor
enable-smartcard={smartcard}
enable-usb-autoshare={usb_auto_share}
delete-this-file={delete_file}
usb-filter=-1,-1,-1,-1,0
tls-ciphers=DEFAULT
host-subject={host_subject}
ca={ca}
toggle-fullscreen=shift+f11
release-cursor=shift+f12
secure-attention=ctrl+alt+end
{secure_channel}
'''


class RemoteViewerFile(object):
    type = 'spice'
    host = None
    port = None
    tls_port = None
    password = None
    fullscreen = False
    title = 'UDS Enterprise'
    host_subject = ''
    ca = ''

    smartcard = False
    usb_auto_share = True

    delete_file = True

    def __init__(self, host, port, tls_port, password, ca, host_subject, fullscreen=False):
        self.host = host
        self.port = port
        self.tls_port = tls_port
        self.password = password
        self.ca = ca
        self.host_subject = host_subject
        self.fullscreen = fullscreen

    @property
    def as_file(self):
        return self.get()

    @property
    def as_file_ns(self):
        return self.get(tls_port=-1)

    def get(self, tls_port=None):
        if tls_port is None:
            tls_port = self.tls_port

        fullscreen = '01'[self.fullscreen]
        smartcard = '01'[self.smartcard]
        delete_file = '01'[self.delete_file]
        usb_auto_share = '01'[self.usb_auto_share]

        ca = self.ca.strip().replace('\n', '\\\\n')  # So we get '\\n' and script works fine after replacement

        return TEMPLATE.format(
            type=self.type,
            host=self.host,
            port=self.port,
            tls_port=self.tls_port,
            password=self.password,
            fullscreen=fullscreen,
            title=self.title,
            smartcard=smartcard,
            usb_auto_share=usb_auto_share,
            delete_file=delete_file,
            host_subject=self.host_subject if self.tls_port != -1 else '',
            ca=ca if tls_port != -1 else '',
            secure_channel='secure-channels=main;inputs;cursor;playback;record;display;usbredir;smartcard' if tls_port != -1 else ''
        )
