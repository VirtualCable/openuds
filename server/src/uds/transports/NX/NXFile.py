# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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


'''
Created on Jul 29, 2011

@author: Adolfo Gómez, dkmaster at dkmon dot com

'''
from __future__ import unicode_literals

from .NXPassword import NXPassword

import six

EMPTY_PASSWORD = "EMPTY_PASSWORD"

NXTEMPLATE = (
    "<!DOCTYPE NXClientSettings>\n"
    "<NXClientSettings application=\"nxclient\" version=\"1.3\" >\n"
    "  <group name=\"Advanced\" >\n"
    "    <option key=\"Cache size\" value=\"{CACHEMEM}\" />\n"
    "    <option key=\"Cache size on disk\" value=\"{CACHEDISK}\" />\n"
    "    <option key=\"Current keyboard\" value=\"true\" />\n"
    "    <option key=\"Custom keyboard layout\" value=\"{KEYLAYOUT}\" />\n"
    "    <option key=\"Disable ZLIB stream compression\" value=\"false\" />\n"
    "    <option key=\"Disable TCP no-delay\" value=\"false\" />\n" +
    "    <option key=\"Disable deferred updates\" value=\"false\" />\n"
    "    <option key=\"Enable HTTP proxy\" value=\"false\" />\n"
    "    <option key=\"Enable SSL encryption\" value=\"true\" />\n"
    "    <option key=\"Enable response time optimisations\" value=\"true\" />\n"
    "    <option key=\"Grab keyboard\" value=\"false\" />\n"
    "    <option key=\"HTTP proxy host\" value=\"\" />\n"
    "    <option key=\"HTTP proxy port\" value=\"8080\" />\n"
    "    <option key=\"HTTP proxy username\" value=\"\" />\n"
    "    <option key=\"Remember HTTP proxy password\" value=\"false\" />\n"
    "    <option key=\"Restore cache\" value=\"true\" />\n"
    "    <option key=\"StreamCompression\" value=\"\" />\n"
    "  </group>\n"
    "  <group name=\"Environment\" >\n"
    "    <option key=\"Font server host\" value=\"\" />\n"
    "    <option key=\"Font server port\" value=\"7100\" />\n"
    "    <option key=\"Use font server\" value=\"false\" />\n"
    "  </group>\n"
    "  <group name=\"General\" >\n"
    "    <option key=\"Automatic reconnect\" value=\"true\" />\n"
    "    <option key=\"Disable SHM\" value=\"false\" />\n"
    "    <option key=\"Disable emulate shared pixmaps\" value=\"false\" />\n"
    "    <option key=\"Link speed\" value=\"{LINKSPEED}\" />\n"
    "    <option key=\"Remember password\" value=\"{REMEMBERPASS}\" />\n"
    "    <option key=\"Resolution\" value=\"{RESOLUTION}\" />\n"
    "    <option key=\"Resolution width\" value=\"{WIDTH}\" />\n"
    "    <option key=\"Resolution height\" value=\"{HEIGHT}\" />\n"
    "    <option key=\"Server host\" value=\"{HOST}\" />\n"
    "    <option key=\"Server port\" value=\"{PORT}\" />\n"
    "    <option key=\"Session\" value=\"unix\" />\n"
    "    <option key=\"Desktop\" value=\"{DESKTOP}\" />\n"
    "    <option key=\"Use default image encoding\" value=\"1\" />\n"
    "    <option key=\"Use render\" value=\"false\" />\n"
    "    <option key=\"Use taint\" value=\"true\" />\n"
    "    <option key=\"Virtual desktop\" value=\"false\" />\n"
    "    <option key=\"XAgent encoding\" value=\"true\" />\n"
    "    <option key=\"displaySaveOnExit\" value=\"true\" />\n"
    "    <option key=\"xdm broadcast port\" value=\"177\" />\n"
    "    <option key=\"xdm list host\" value=\"localhost\" />\n"
    "    <option key=\"xdm list port\" value=\"177\" />\n"
    "    <option key=\"xdm mode\" value=\"server decide\" />\n"
    "    <option key=\"xdm query host\" value=\"localhost\" />\n"
    "    <option key=\"xdm query port\" value=\"177\" />\n"
    "  </group>\n"
    "  <group name=\"Images\" >\n"
    "    <option key=\"Disable JPEG Compression\" value=\"0\" />\n"
    "    <option key=\"Disable all image optimisations\" value=\"false\" />\n"
    "    <option key=\"Disable backingstore\" value=\"false\" />\n"
    "    <option key=\"Disable composite\" value=\"false\" />\n"
    "    <option key=\"Image Compression Type\" value=\"3\" />\n"
    "    <option key=\"Image Encoding Type\" value=\"0\" />\n"
    "    <option key=\"Image JPEG Encoding\" value=\"false\" />\n"
    "    <option key=\"JPEG Quality\" value=\"6\" />\n"
    "    <option key=\"RDP Image Encoding\" value=\"3\" />\n"
    "    <option key=\"RDP JPEG Quality\" value=\"6\" />\n"
    "    <option key=\"RDP optimization for low-bandwidth link\" value=\"false\" />\n"
    "    <option key=\"Reduce colors to\" value=\"\" />\n"
    "    <option key=\"Use PNG Compression\" value=\"true\" />\n"
    "    <option key=\"VNC JPEG Quality\" value=\"6\" />\n"
    "    <option key=\"VNC images compression\" value=\"3\" />\n"
    "  </group>\n"
    "  <group name=\"Login\" >\n"
    "    <option key=\"User\" value=\"{USERNAME}\" />\n"
    "    <option key=\"Auth\" value=\"{PASSWORD}\" />\n"
    "    <option key=\"Guest Mode\" value=\"false\" />\n"
    "    <option key=\"Guest password\" value=\"\" />\n"
    "    <option key=\"Guest username\" value=\"\" />\n"
    "    <option key=\"Login Method\" value=\"nx\" />\n"
    "    <option key=\"Public Key\" value=\"-----BEGIN DSA PRIVATE KEY-----\n"
    "MIIBuwIBAAKBgQCXv9AzQXjxvXWC1qu3CdEqskX9YomTfyG865gb4D02ZwWuRU/9\n"
    "C3I9/bEWLdaWgJYXIcFJsMCIkmWjjeSZyTmeoypI1iLifTHUxn3b7WNWi8AzKcVF\n"
    "aBsBGiljsop9NiD1mEpA0G+nHHrhvTXz7pUvYrsrXcdMyM6rxqn77nbbnwIVALCi\n"
    "xFdHZADw5KAVZI7r6QatEkqLAoGBAI4L1TQGFkq5xQ/nIIciW8setAAIyrcWdK/z\n"
    "5/ZPeELdq70KDJxoLf81NL/8uIc4PoNyTRJjtT3R4f8Az1TsZWeh2+ReCEJxDWgG\n"
    "fbk2YhRqoQTtXPFsI4qvzBWct42WonWqyyb1bPBHk+JmXFscJu5yFQ+JUVNsENpY\n"
    "+Gkz3HqTAoGANlgcCuA4wrC+3Cic9CFkqiwO/Rn1vk8dvGuEQqFJ6f6LVfPfRTfa\n"
    "QU7TGVLk2CzY4dasrwxJ1f6FsT8DHTNGnxELPKRuLstGrFY/PR7KeafeFZDf+fJ3\n"
    "mbX5nxrld3wi5titTnX+8s4IKv29HJguPvOK/SI7cjzA+SqNfD7qEo8CFDIm1xRf\n"
    "8xAPsSKs6yZ6j1FNklfu\n"
    "-----END DSA PRIVATE KEY-----\n"
    "\" />\n"
    "  </group>\n"
    "  <group name=\"Services\" >\n"
    "    <option key=\"Audio\" value=\"true\" />\n"
    "    <option key=\"IPPPort\" value=\"631\" />\n"
    "    <option key=\"IPPPrinting\" value=\"false\" />\n"
    "    <option key=\"Shares\" value=\"false\" />\n"
    "  </group>\n"
    "  <group name=\"VNC Session\" >\n"
    "    <option key=\"Display\" value=\"0\" />\n"
    "    <option key=\"Remember\" value=\"false\" />\n"
    "    <option key=\"Server\" value=\"\" />\n"
    "  </group>\n"
    "  <group name=\"Windows Session\" >\n"
    "    <option key=\"Application\" value=\"\" />\n"
    "    <option key=\"Authentication\" value=\"2\" />\n"
    "    <option key=\"Color Depth\" value=\"16\" />\n"
    "    <option key=\"Domain\" value=\"\" />\n"
    "    <option key=\"Image Cache\" value=\"true\" />\n"
    "    <option key=\"Password\" value=\"EMPTY_PASSWORD\" />\n"
    "    <option key=\"Remember\" value=\"true\" />\n"
    "    <option key=\"Run application\" value=\"false\" />\n"
    "    <option key=\"Server\" value=\"\" />\n"
    "    <option key=\"User\" value=\"\" />\n"
    "  </group>\n"
    "  <group name=\"share chosen\" >\n"
    "    <option key=\"Share number\" value=\"0\" />\n"
    "  </group>\n"
    "</NXClientSettings>"
)


class NXFile(object):
    fullScreen = False
    width = '800'
    height = '600'
    cachemem = '4'
    cachedisk = '32'
    keyboardLayout = ''
    linkSpeed = 'wan'
    host = ''
    port = ''
    username = ''
    password = ''
    desktop = 'gnome'

    def __init__(self, username='', password='', width=1024, height=768):
        self.fullScreen = width == -1 or height == -1
        self.width = int(width)
        self.height = int(height)
        self.username = username
        self.password = password

    @property
    def as_file(self):
        return self.get()

    @property
    def as_file_for_format(self):
        return self.get(True)

    def get(self, processPassword=False):
        rememberPass = 'true'
        password = NXPassword.scrambleString(self.password)
        if processPassword:
            password = password.replace('{', '{{')
            password = password.replace('}', '}}')

        if password == '':
            rememberPass = "false"
            password = EMPTY_PASSWORD

        resolution = '{}x{}'.format(self.width, self.height)
        if self.fullScreen:
            resolution = "fullscreen"

        return NXTEMPLATE.format(
            CACHEMEM=self.cachemem,
            CACHEDISK=self.cachedisk,
            KEYLAYOUT=self.keyboardLayout,
            LINKSPEED=self.linkSpeed,
            REMEMBERPASS=rememberPass,
            RESOLUTION=resolution,
            WIDTH=self.width,
            HEIGHT=self.height,
            HOST=self.host,
            PORT=self.port,
            DESKTOP=self.desktop,
            USERNAME=self.username,
            PASSWORD=password
        )
