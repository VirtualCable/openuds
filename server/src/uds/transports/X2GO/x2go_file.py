# -*- coding: utf-8 -*-

#
# Copyright (c) 2016-2021 Virtual Cable S.L.U.
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
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""

template = '''[General]
UDS=@ByteArray()

[20160101100758147]
speed={speed}
pack={pack}
quality={quality}
fstunnel=true
{export}
iconvto=UTF-8
iconvfrom=ISO8859-1
useiconv=false
fullscreen={fullscreen}
multidisp=false
display=1
maxdim=false
rdpclient=rdesktop
directrdpsettings=
width={width}
height={height}
dpi=96
setdpi=true
xinerama=false
clipboard=both
usekbd=true
type=auto
sound={sound}
soundsystem={soundSystem}
startsoundsystem=true
soundtunnel=true
defsndport=true
sndport=4713
print=true
name=UDS/connect
icon=:/img/icons/128x128/x2gosession.png
host={{ip}}
user={user}
key={{keyFile}}
rdpport=3389
sshport={{port}}
autologin=false
krblogin=false
krbdelegation=false
directrdp=false
rootless={rootless}
published=false
applications=WWWBROWSER, MAILCLIENT, OFFICE, TERMINAL
command={windowManager}
rdpoptions=
rdpserver=
xdmcpserver=localhost
usesshproxy=false
sshproxytype=SSH
sshproxyuser=
sshproxykeyfile=
sshproxyhost=
sshproxyport=22
sshproxysamepass=false
sshproxysameuser=false
sshproxyautologin=false
sshproxykrblogin=false
'''


def getTemplate(
    speed,
    pack,
    quality,
    sound,
    soundSystem,
    windowManager,
    exports,
    rootless,
    width,
    height,
    user,
):
    trueFalse = lambda x: 'true' if x else 'false'
    export = 'export="{export}"' if exports else ''
    if width == -1 or height == -1:
        width = 800
        height = 600
        fullscreen = 'true'
    else:
        fullscreen = 'false'
    return template.format(
        speed=speed,
        pack=pack,
        quality=quality,
        sound=trueFalse(sound),
        soundSystem=soundSystem,
        windowManager=windowManager,
        export=export,
        rootless=rootless and 'true' or 'false',
        width=width,
        height=height,
        fullscreen=fullscreen,
        user=user,
    )
