# -*- coding: utf-8 -*-

#
# Copyright (c) 2011-2023 Virtual Cable S.L.U.
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
# SERVICES LOSS OF USE, DATA, OR PROFITS OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
Created on Jul 29, 2011

Author: Adolfo Gómez, dkmaster at dkmon dot com

"""
import urllib.parse
import shlex
import typing

from uds.core import types


class RDPFile:
    fullscreen: bool = False
    width: str = '800'
    height: str = '600'
    bpp: str = '32'
    address: str = ''
    username: str = ''
    domain: str = ''
    password: str = ''  # nosec: emtpy password is ok here
    redir_serials: bool = False
    redir_printers: bool = False
    redir_drives: str = "false"  # Can have "true", "false" or "dynamic"
    redir_home_dir: bool = False
    redir_smartcards: bool = False
    redir_audio: bool = True
    redir_webcam: bool = False
    redir_usb: str = 'false'  # Can have, false, true, or a GUID
    compression: bool = True
    multimedia: bool = True
    alsa: bool = True
    connection_bar: bool = True
    show_wallpaper: bool = False
    multimon: bool = False
    desktop_composition: bool = False
    smooth_fonts: bool = True
    printer_params: typing.Optional[str] = None
    smartcard_params: typing.Optional[str] = None
    enable_credssp_support: bool = False
    enable_clipboard: bool = False
    custom_parameters: typing.Optional[str] = None
    enforced_shares: typing.Optional[str] = None

    def __init__(
        self,
        fullscreen: bool,
        width: typing.Union[str, int],
        height: typing.Union[str, int],
        bpp: str,
        target: types.os.KnownOS = types.os.KnownOS.WINDOWS,
    ):
        self.width = str(width)
        self.height = str(height)
        self.bpp = str(bpp)
        self.fullscreen = fullscreen
        self.target = target

    def get(self) -> str:
        if self.target in (
            types.os.KnownOS.WINDOWS,
            types.os.KnownOS.LINUX,
            types.os.KnownOS.MAC_OS,
        ):
            return self.as_mstsc_file
        # Unknown target
        return ''

    @property
    def as_file(self) -> str:
        return self.get()

    @property
    def as_new_xfreerdp_params(self) -> typing.List[str]:
        """
        Parameters for xfreerdp >= 1.1.0 with self rdp description
        Note that server is not added
        """
        params = ['/t:UDS-Connection', '/cert:ignore']  # , '/sec:rdp']

        if self.enable_clipboard:
            params.append('/clipboard')

        if self.redir_smartcards:
            if self.smartcard_params not in (None, ''):
                params.append('/smartcard:{}'.format(self.smartcard_params))
            else:
                params.append('/smartcard')

        if self.redir_audio:
            if self.alsa and self.target != types.os.KnownOS.MAC_OS:
                params.append('/sound:sys:alsa,format:1,quality:high')
                params.append('/microphone:sys:alsa')
            else:
                params.append('/sound')  # Mac does not support alsa
                # And microphone seems to not work on mac
                # params.append('/microphone')

        if self.multimedia:
            params.append('/video')

        if self.redir_drives != 'false':
            if self.target in (types.os.KnownOS.LINUX, types.os.KnownOS.MAC_OS):
                params.append('/drive:home,$HOME')
            else:
                params.append('/drive:Users,/Users')
            # params.append('/home-drive')

        if self.redir_serials is True:
            params.append('/serial:/dev/ttyS0')

        if self.redir_printers:
            if self.printer_params not in (None, ''):
                params.append('/printer:{}'.format(self.printer_params))
            else:
                params.append('/printer')

        # if not self.compression:
        #    params.append('-compression')

        if self.show_wallpaper:
            params.append('+themes')
            params.append('+wallpaper')

        if self.multimon:
            params.append('/multimon')

        if self.fullscreen:
            if self.target != types.os.KnownOS.MAC_OS:
                params.append('/f')
            else:  # On mac, will fix this later...
                params.append('/w:#WIDTH#')
                params.append('/h:#HEIGHT#')
        else:
            params.append('/w:{}'.format(self.width))
            params.append('/h:{}'.format(self.height))

        params.append('/bpp:{}'.format(self.bpp))

        if self.smooth_fonts is True:
            params.append('+fonts')

        # RDP Security is A MUST if no username nor password is provided
        # NLA requires USERNAME&PASSWORD previously
        force_rdp_security = False
        if self.username != '':
            params.append('/u:{}'.format(self.username))
        else:
            force_rdp_security = True
        if self.password:
            params.append('/p:{}'.format(self.password))
        else:
            force_rdp_security = True
        if self.domain != '':
            params.append('/d:{}'.format(self.domain))

        if force_rdp_security:
            params.append('/sec:rdp')
            
        if self.connection_bar and '/floatbar' not in params:
            params.append('/floatbar:sticky:off')

        if self.custom_parameters and self.custom_parameters.strip() != '':
            params += shlex.split(self.custom_parameters.strip())

        # On MacOSX, /rfx /gfx:rfx are almost inprescindible, as it seems the only way to get a decent performance
        if self.target == types.os.KnownOS.MAC_OS:
            for i in ('/rfx', '/gfx:rfx'):
                if i not in params:
                    params.append(i)

        return params

    @property
    def as_mstsc_file(self) -> str:  # pylint: disable=too-many-statements
        password = '{password}'  # nosec: placeholder
        screen_mode = '2' if self.fullscreen else '1'
        audio_mode = '0' if self.redir_audio else '2'
        serials = '1' if self.redir_serials else '0'
        scards = '1' if self.redir_smartcards else '0'
        printers = '1' if self.redir_printers else '0'
        compression = '1' if self.compression else '0'
        connection_bar = '1' if self.connection_bar else '0'
        disable_wallpaper = '0' if self.show_wallpaper else '1'
        use_multimon = '1' if self.multimon else '0'
        enable_clipboard = '1' if self.enable_clipboard else '0'

        res = ''
        res += 'screen mode id:i:' + screen_mode + '\n'
        if self.width[0] != '-' and self.height[0] != '-':
            res += 'desktopwidth:i:' + self.width + '\n'
            res += 'desktopheight:i:' + self.height + '\n'
        res += 'session bpp:i:' + self.bpp + '\n'
        res += 'use multimon:i:' + use_multimon + '\n'
        res += 'auto connect:i:1' + '\n'
        res += 'full address:s:' + self.address + '\n'
        res += 'compression:i:' + compression + '\n'
        res += 'keyboardhook:i:2' + '\n'
        res += 'audiomode:i:' + audio_mode + '\n'
        res += 'redirectprinters:i:' + printers + '\n'
        res += 'redirectcomports:i:' + serials + '\n'
        res += 'redirectsmartcards:i:' + scards + '\n'
        res += 'redirectclipboard:i:' + enable_clipboard + '\n'
        res += 'displayconnectionbar:i:' + connection_bar + '\n'
        if self.username:
            res += 'username:s:' + self.username + '\n'
            res += 'domain:s:' + self.domain + '\n'
            if self.target == types.os.KnownOS.WINDOWS:
                res += 'password 51:b:' + password + '\n'

        res += 'alternate shell:s:' + '\n'
        res += 'shell working directory:s:' + '\n'
        res += 'disable wallpaper:i:' + disable_wallpaper + '\n'
        res += 'disable full window drag:i:1' + '\n'
        res += 'disable menu anims:i:' + disable_wallpaper + '\n'
        res += 'disable themes:i:' + disable_wallpaper + '\n'
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
        if self.smooth_fonts is True:
            res += 'allow font smoothing:i:1\n'
        if self.desktop_composition is True:
            res += 'allow desktop composition:i:1\n'

        if self.redir_audio is True:
            res += 'audiocapturemode:i:1\n'

        if self.redir_webcam:
            res += 'camerastoredirect:s:*\n'

        enforced_shares_str = (
            ';'.join(self.enforced_shares.replace(' ', '').upper().split(',')) + ';'
            if self.enforced_shares
            else ''
        )

        if self.redir_drives != 'false':
            if self.redir_drives == 'true':
                res += 'drivestoredirect:s:{}\n'.format(enforced_shares_str or '*')
            else:  # Dynamic
                res += 'drivestoredirect:s:{}DynamicDrives\n'.format(enforced_shares_str)
            res += 'devicestoredirect:s:*\n'

        if self.redir_usb != 'false':
            if self.redir_usb == 'true':
                res += 'usbdevicestoredirect:s:*\n'
            else:
                # add the USB device to the list of devices to redirect
                # escape { and } characters
                res += 'usbdevicestoredirect:s:{}\n'.format(
                    self.redir_usb.replace('{', '{{').replace('}', '}}')
                )

        res += 'enablecredsspsupport:i:{}\n'.format(0 if self.enable_credssp_support is False else 1)

        # DirectX?
        res += 'redirectdirectx:i:1\n'

        # Camera?
        # res += 'camerastoredirect:s:*\n'

        # If target is windows, add customParameters
        if self.target == types.os.KnownOS.WINDOWS:
            if self.custom_parameters and self.custom_parameters.strip() != '':
                res += self.custom_parameters.strip() + '\n'

        return res

    @property
    def as_rdp_url(self) -> str:
        # Some parameters
        screen_mode = '2' if self.fullscreen else '1'
        audio_mode = '0' if self.redir_audio else '2'
        use_multimon = '1' if self.multimon else '0'
        disable_wallpaper = '0' if self.show_wallpaper else '1'
        printers = '1' if self.redir_printers else '0'
        credsspsupport = '1' if self.enable_credssp_support else '0'

        parameters: list[tuple[str, str]] = [
            ('full address', f's:{self.address}'),
            ('audiomode', f'i:{audio_mode}'),
            ('screen mode id', f'i:{screen_mode}'),
            ('use multimon', f'i:{use_multimon}'),
            ('desktopwidth', f'i:{self.width}'),
            ('desktopheight', f':{self.height}'),
            ('session bpp', f'i:{self.bpp}'),
            ('disable menu anims', f'i:{disable_wallpaper}'),
            ('disable themes', f'i:{disable_wallpaper}'),
            ('disable wallpaper', f'i:{disable_wallpaper}'),
            ('redirectprinters', f'i:{printers}'),
            ('disable full window drag', 'i:1'),
            ('authentication level', f'i:0'),
            # Not listed, but maybe usable?
            ('enablecredsspsupport', f'i:{credsspsupport}'),
        ]
        if self.username:
            parameters.append(('username', f's:{urllib.parse.quote(self.username)}'))
            if self.domain:
                parameters.append(('domain', f's:{urllib.parse.quote(self.domain)}'))

        if self.desktop_composition:
            parameters.append(('allow desktop composition', 'i:1'))

        if self.smooth_fonts:
            parameters.append(('allow font smoothing', 'i:1'))

        if self.redir_drives != 'false':  # Only "all drives" is supported
            parameters.append(('drivestoredirect', 's:*'))

        return 'rdp://' + '&'.join((urllib.parse.quote(i[0]) + '=' + i[1] for i in parameters))
