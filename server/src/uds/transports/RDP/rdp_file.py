# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2020 Virtual Cable S.L.U.
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
# SERVICES LOSS OF USE, DATA, OR PROFITS OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Created on Jul 29, 2011

@author: Adolfo Gómez, dkmaster at dkmon dot com

"""
import urllib.parse
import shlex
import typing

from uds.core.util import os_detector as OsDetector

class RDPFile:
    fullScreen = False
    width = '800'
    height = '600'
    bpp = '32'
    address = ''
    username = ''
    domain = ''
    password = ''
    redirectSerials = False
    redirectPrinters = False
    redirectDrives = "false"  # Can have "true", "false" or "dynamic"
    redirectHome = False
    redirectSmartcards = False
    redirectAudio = True
    redirectWebcam = False
    compression = True
    multimedia = True
    alsa = True
    displayConnectionBar = True
    showWallpaper = False
    multimon = False
    desktopComposition = False
    smoothFonts = True
    printerString = None
    smartcardString = None
    enablecredsspsupport = False
    enableClipboard = False
    linuxCustomParameters: typing.Optional[str] = None
    enforcedShares: typing.Optional[str] = None

    def __init__(
            self,
            fullScreen: bool,
            width: typing.Union[str, int],
            height: typing.Union[str, int],
            bpp: str,
            target: str = OsDetector.Windows
        ):
        self.width = str(width)
        self.height = str(height)
        self.bpp = str(bpp)
        self.fullScreen = fullScreen
        self.target = target

    def get(self):
        if self.target in (OsDetector.Windows, OsDetector.Linux, OsDetector.Macintosh):
            return self.getGeneric()
        # Unknown target
        return ''

    @property
    def as_file(self):
        return self.get()

    @property
    def as_new_xfreerdp_params(self):  # pylint: disable=too-many-statements,too-many-branches
        """
        Parameters for xfreerdp >= 1.1.0 with self rdp description
        Note that server is not added
        """
        params = ['/t:UDS-Connection', '/cert-ignore']  # , '/sec:rdp']

        if self.enableClipboard:
            params.append('/clipboard')

        if self.redirectSmartcards:
            if self.smartcardString not in (None, ''):
                params.append('/smartcard:{}'.format(self.smartcardString))
            else:
                params.append('/smartcard')

        if self.redirectAudio:
            if self.alsa and self.target != OsDetector.Macintosh:
                params.append('/sound:sys:alsa,format:1,quality:high')
                params.append('/microphone:sys:alsa')
            else:
                params.append('/sound')
                params.append('/microphone')

        if self.multimedia:
            params.append('/video')

        if self.redirectDrives != 'false':
            if self.target == OsDetector.Linux:
                params.append('/drive:media,/media')
            else:
                params.append('/drive:Users,/Users')
            # params.append('/home-drive')

        if self.redirectHome is True:
            params.append('/drive:home,/home')

        if self.redirectSerials is True:
            params.append('/serial:/dev/ttyS0')

        if self.redirectPrinters:
            if self.printerString not in (None, ''):
                params.append('/printer:{}'.format(self.printerString))
            else:
                params.append('/printer')

        # if not self.compression:
        #    params.append('-compression')

        if self.showWallpaper:
            params.append('+themes')
            params.append('+wallpaper')

        if self.multimon:
            params.append('/multimon')

        if self.fullScreen:
            if self.target != OsDetector.Macintosh:
                params.append('/f')
            else:  # On mac, will fix this later...
                params.append('/w:#WIDTH#')
                params.append('/h:#HEIGHT#')
        else:
            params.append('/w:{}'.format(self.width))
            params.append('/h:{}'.format(self.height))

        params.append('/bpp:{}'.format(self.bpp))

        if self.smoothFonts is True:
            params.append('+fonts')

        # RDP Security is A MUST if no username nor password is provided
        # NLA requires USERNAME&PASSWORD previously
        forceRDPSecurity = False
        if self.username != '':
            params.append('/u:{}'.format(self.username))
        else:
            forceRDPSecurity = True
        if self.password != '':
            params.append('/p:{}'.format(self.password))
        else:
            forceRDPSecurity = True
        if self.domain != '':
            params.append('/d:{}'.format(self.domain))

        if forceRDPSecurity:
            params.append('/sec:rdp')

        if self.linuxCustomParameters and self.linuxCustomParameters.strip() != '':
            params += shlex.split(self.linuxCustomParameters.strip())

        return params

    def getGeneric(self):  # pylint: disable=too-many-statements
        password = '{password}'
        screenMode = '2' if self.fullScreen else '1'
        audioMode =  '2' if self.redirectAudio else '0'
        serials = '1' if self.redirectSerials else '0'
        scards = '1' if self.redirectSmartcards else '0'
        printers = '1' if self.redirectPrinters else '0'
        compression = '1' if self.compression else '0'
        connectionBar = '1' if self.displayConnectionBar else '0'
        disableWallpaper = '1' if self.showWallpaper else '0'
        useMultimon = '1' if self.multimon else '0'
        enableClipboard = '1' if self.enableClipboard else '0'

        res = ''
        res += 'screen mode id:i:' + screenMode + '\n'
        if self.width[0] != '-' and self.height[0] != '-':
            res += 'desktopwidth:i:' + self.width + '\n'
            res += 'desktopheight:i:' + self.height + '\n'
        res += 'session bpp:i:' + self.bpp + '\n'
        res += 'use multimon:i:' + useMultimon + '\n'
        res += 'auto connect:i:1' + '\n'
        res += 'full address:s:' + self.address + '\n'
        res += 'compression:i:' + compression + '\n'
        res += 'keyboardhook:i:2' + '\n'
        res += 'audiomode:i:' + audioMode + '\n'
        res += 'redirectprinters:i:' + printers + '\n'
        res += 'redirectcomports:i:' + serials + '\n'
        res += 'redirectsmartcards:i:' + scards + '\n'
        res += 'redirectclipboard:i:' + enableClipboard + '\n'
        res += 'displayconnectionbar:i:' + connectionBar + '\n'
        if self.username:
            res += 'username:s:' + self.username + '\n'
            res += 'domain:s:' + self.domain + '\n'
            if self.target == OsDetector.Windows:
                res += 'password 51:b:' + password + '\n'

        res += 'alternate shell:s:' + '\n'
        res += 'shell working directory:s:' + '\n'
        res += 'disable wallpaper:i:' + disableWallpaper + '\n'
        res += 'disable full window drag:i:1' + '\n'
        res += 'disable menu anims:i:' + disableWallpaper + '\n'
        res += 'disable themes:i:' + disableWallpaper + '\n'
        res += 'bitmapcachepersistenable:i:1' + '\n'
        res += 'authentication level:i:0' + '\n'
        res += 'prompt for credentials:i:0' + '\n'
        res += 'negotiate security layer:i:1\n'
        res += 'bandwidthautodetect:i:1\n'

        # 3 lines changed by Tomás Lobo recommendation (Thanks Tomás ;-))
        # res += 'connection type:i:7\n'
        res += 'networkautodetect:i:0\n'
        res += 'connection type:i:6\n'

        res += 'videoplaybackmode:i:1\n'
        if self.smoothFonts is True:
            res += 'allow font smoothing:i:1\n'
        if self.desktopComposition is True:
            res += 'allow desktop composition:i:1\n'

        if self.redirectAudio is True:
            res += 'audiocapturemode:i:1\n'

        if self.redirectWebcam:
            res += 'camerastoredirect:s:*\n'

        enforcedSharesStr = ';'.join(self.enforcedShares.replace(' ', '').upper().split(',')) + ';' if self.enforcedShares else ''

        if self.redirectDrives != 'false':
            if self.redirectDrives == 'true':
                res += 'drivestoredirect:s:{}\n'.format(enforcedSharesStr or '*')
            else:  # Dynamic
                res += 'drivestoredirect:s:{}DynamicDrives\n'.format(enforcedSharesStr)
            res += 'devicestoredirect:s:*\n'

        res += 'enablecredsspsupport:i:{}\n'.format(0 if self.enablecredsspsupport is False else 1)

        # DirectX?
        res += 'redirectdirectx:i:1\n'

        # Camera?
        # res += 'camerastoredirect:s:*\n'

        return res

    @property
    def as_rdp_url(self) -> str:
        # Some parameters
        screenMode = '2' if self.fullScreen else '1'
        audioMode = self.redirectAudio and '0' or '2'
        useMultimon = self.multimon and '1' or '0'
        disableWallpaper = self.showWallpaper and '0' or '1'
        printers = self.redirectPrinters and '1' or '0'
        credsspsupport = '0' if self.enablecredsspsupport is False else '1'
        

        parameters = [
            ('full address', f's:{self.address}'),
            ('audiomode', f'i:{audioMode}'),
            ('screen mode id', f'i:{screenMode}'),
            ('use multimon', f'i:{useMultimon}'),
            ('desktopwidth', f'i:{self.width}'),
            ('desktopheight', f':{self.height}'),
            ('session bpp', f'i:{self.bpp}'),
            ('disable menu anims', f'i:{disableWallpaper}'),
            ('disable themes', f'i:{disableWallpaper}'),
            ('disable wallpaper', f'i:{disableWallpaper}'),
            ('redirectprinters', f'i:{printers}'),
            ('disable full window drag', 'i:1'),
            ('authentication level', f'i:0'),
            # Not listed, but maybe usable?
            ('enablecredsspsupport', f'i:{credsspsupport}')
        ]
        if self.username:
            parameters.append(('username', f's:{urllib.parse.quote(self.username)}'))
            if self.domain:
                parameters.append(('domain', f's:{urllib.parse.quote(self.domain)}'))

        if self.desktopComposition:
            parameters.append(('allow desktop composition', 'i:1'))

        if self.smoothFonts:
            parameters.append(('allow font smoothing', 'i:1'))

        if self.redirectDrives != 'false':  # Only "all drives" is supported
            parameters.append(('drivestoredirect', f's:*'))

        return 'rdp://' + '&'.join((urllib.parse.quote(i[0]) + '=' + i[1] for i in parameters))

