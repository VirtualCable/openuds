# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
import typing

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
enable-usbredir={usb_auto_share}
delete-this-file={delete_file}
usb-filter=-1,-1,-1,-1,{new_usb_auto_share}
tls-ciphers=DEFAULT
host-subject={host_subject}
ca={ca}
toggle-fullscreen=shift+f11
release-cursor=shift+f12
secure-attention=ctrl+alt+end
{secure_channel}
'''


class RemoteViewerFile:
    connectionType: str = 'spice'
    host: str = ''
    port: typing.Optional[str] = None
    tls_port: typing.Optional[str] = None
    password: str
    fullscreen: bool = False
    title: str = 'UDS Enterprise'
    host_subject: str = ''
    ca: str = ''
    smartcard: bool = False
    usb_auto_share: bool = True
    new_usb_auto_share: bool = False
    delete_file: bool = True

    def __init__(
            self,
            host: str,
            port: str,
            tls_port: str,
            password: str,
            ca: str,
            host_subject: str,
            fullscreen: bool = False
        ):
        self.host = host
        self.port = port
        self.tls_port = tls_port
        self.password = password
        self.ca = ca
        self.host_subject = host_subject
        self.fullscreen = fullscreen

    @property
    def as_file(self) -> str:
        return self.get()

    @property
    def as_file_ns(self) -> str:
        return self.get('-1')

    def get(self, tls_port: typing.Optional[str] = None) -> str:
        if tls_port is None:
            tls_port = self.tls_port

        fullscreen = '01'[self.fullscreen]
        smartcard = '01'[self.smartcard]
        delete_file = '01'[self.delete_file]
        usb_auto_share = '01'[self.usb_auto_share]
        new_usb_auto_share = '01'[self.new_usb_auto_share]

        ca = self.ca.strip().replace('\n', '\\\\n')  # So we get '\\n' and script works fine after replacement

        return TEMPLATE.format(
            type=self.connectionType,
            host=self.host,
            port=self.port,
            tls_port=self.tls_port,
            password=self.password,
            fullscreen=fullscreen,
            title=self.title,
            smartcard=smartcard,
            usb_auto_share=usb_auto_share,
            new_usb_auto_share=new_usb_auto_share,
            delete_file=delete_file,
            host_subject=self.host_subject if tls_port != '-1' else '',
            ca=ca if tls_port != '-1' else '',
            secure_channel='secure-channels=main;inputs;cursor;playback;record;display;usbredir;smartcard' if tls_port != '-1' else ''
        )
