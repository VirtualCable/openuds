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
# SERVICES LOSS OF USE, DATA, OR PROFITS OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


'''
Created on Jul 29, 2011

@author: Adolfo Gómez, dkmaster at dkmon dot com

'''
from __future__ import unicode_literals

from uds.core.util import OsDetector
import six
import os

__updated__ = '2016-06-17'


class RDPFile(object):
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
    redirectDrives = False
    redirectSmartcards = False
    redirectAudio = True
    compression = True
    displayConnectionBar = True
    showWallpaper = False
    multimon = False
    desktopComposition = False
    enablecredsspsupport = True

    def __init__(self, fullScreen, width, height, bpp, target=OsDetector.Windows):
        self.width = six.text_type(width)
        self.height = six.text_type(height)
        self.bpp = six.text_type(bpp)
        self.fullScreen = fullScreen
        self.target = target

    def get(self):
        if self.target in (OsDetector.Windows, OsDetector.Linux):
            return self.getGeneric()
        elif self.target == OsDetector.Macintosh:
            return self.getMacOsX()
        # Unknown target
        return ''

    @property
    def as_file(self):
        return self.get()

    @property
    def as_new_xfreerdp_params(self):
        '''
        Parameters for xfreerdp >= 1.1.0 with self rdp description
        Note that server is not added
        '''
        params = ['/clipboard', '/t:UDS Connection', '/cert-ignore', '/sec:rdp']

        if self.redirectSmartcards:
            params.append('/smartcard')

        if self.redirectAudio:
            params.append('/sound:sys:alsa')
            params.append('/microphone:sys:alsa')
            params.append('/multimedia:sys:alsa')

        if self.redirectDrives is True:
            params.append('/drive:media,/media')
            params.append('/home-drive')

        if self.redirectSerials is True:
            params.append('/serial:/dev/ttyS0')

        if self.redirectPrinters:
            params.append('/printer')

        if self.compression:
            params.append('/compression:on')

        if self.showWallpaper:
            params.append('+themes')
            params.append('+wallpaper')

        if self.multimon:
            params.append('/multimon')

        if self.fullScreen:
            params.append('/f')
        else:
            params.append('/w:{}'.format(self.width))
            params.append('/h:{}'.format(self.height))

        params.append('/bpp:{}'.format(self.bpp))
        if self.username != '':
            params.append('/u:{}'.format(self.username))
        if self.password != '':
            params.append('/p:{}'.format(self.password))
        if self.domain != '':
            params.append('/d:{}'.format(self.domain))

        return params

    @property
    def as_rdesktop_params(self):
        '''
        Parameters for rdestop with self rdp description
        Note that server is not added
        '''

        params = ['-TUDS Connection', '-P', '-rclipboard:PRIMARYCLIPBOARD']

        if self.redirectSmartcards:
            params.append('-rsdcard')

        if self.redirectAudio:
            params.append('-rsound:local')
        else:
            params.append('-rsound:off')

        if self.redirectDrives is True:
            params.append('-rdisk:media=/media')

        if self.redirectSerials is True:
            params.append('-rcomport:COM1=/dev/ttyS0')

        if self.redirectPrinters:
            pass

        if self.compression:
            params.append('-z')

        if self.showWallpaper:
            params.append('-xl')
        else:
            params.append('-xb')

        if self.multimon:
            pass

        if self.fullScreen:
            params.append('-f')
        else:
            params.append('-g{}x{}'.format(self.width, self.height))

        params.append('-a{}'.format(self.bpp))
        if self.username != '':
            params.append('-u{}'.format(self.username))
        if self.password != '':
            params.append('-p-')
        if self.domain != '':
            params.append('-d{}'.format(self.domain))

        return params

    def getGeneric(self):
        password = "{password}"
        screenMode = self.fullScreen and "2" or "1"
        audioMode = self.redirectAudio and "0" or "2"
        serials = self.redirectSerials and "1" or "0"
        drives = self.redirectDrives and "1" or "0"
        scards = self.redirectSmartcards and "1" or "0"
        printers = self.redirectPrinters and "1" or "0"
        compression = self.compression and "1" or "0"
        bar = self.displayConnectionBar and "1" or "0"
        disableWallpaper = self.showWallpaper and "0" or "1"
        useMultimon = self.multimon and "1" or "0"

        res = ''
        res += 'screen mode id:i:' + screenMode + '\n'
        res += 'desktopwidth:i:' + self.width + '\n'
        res += 'desktopheight:i:' + self.height + '\n'
        res += 'session bpp:i:' + self.bpp + '\n'
        res += 'use multimon:i:' + useMultimon + '\n'
        res += 'auto connect:i:1' + '\n'
        res += 'full address:s:' + self.address + '\n'
        res += 'compression:i:' + compression + '\n'
        res += 'keyboardhook:i:2' + '\n'
        res += 'audiomode:i:' + audioMode + '\n'
        res += 'redirectdrives:i:' + drives + '\n'
        res += 'redirectprinters:i:' + printers + '\n'
        res += 'redirectcomports:i:' + serials + '\n'
        res += 'redirectsmartcards:i:' + scards + '\n'
        res += 'redirectclipboard:i:1' + '\n'
        res += 'displayconnectionbar:i:' + bar + '\n'
        if len(self.username) != 0:
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
        res += 'enablecredsspsupport:i:1' + '\n'
        res += 'prompt for credentials:i:0' + '\n'
        res += 'negotiate security layer:i:1' + '\n'
        if self.desktopComposition is True:
            res += 'allow desktop composition:i:1\n'

        if self.redirectAudio is True:
            res += 'audiocapturemode:i:1\n'

        res += 'enablecredsspsupport:i:{}\n'.format(0 if self.enablecredsspsupport is False else 1)

        return res

    def getMacOsX(self):
        if self.fullScreen:
            desktopSize = '    <string>DesktopFullScreen</string>'
        else:
            desktopSize = '''    <dict>
        <key>DesktopHeight</key>
        <integer>{}</integer>
        <key>DesktopWidth</key>
        <integer>{}</integer>
    </dict>'''.format(self.width, self.height)

        drives = self.redirectDrives and "1" or "0"
        audioMode = self.redirectAudio and "0" or "2"
        wallpaper = self.showWallpaper and 'true' or 'false'

        return '''
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>AddToKeychain</key>
    <true/>
    <key>ApplicationPath</key>
    <string></string>
    <key>AudioRedirectionMode</key>
    <integer>{audioMode}</integer>
    <key>AuthenticateLevel</key>
    <integer>0</integer>
    <key>AutoReconnect</key>
    <true/>
    <key>BitmapCaching</key>
    <true/>
    <key>ColorDepth</key>
    <integer>1</integer>
    <key>ConnectionString</key>
    <string>{host}</string>
    <key>DesktopSize</key>
    {desktopSize}
    <key>Display</key>
    <integer>0</integer>
    <key>Domain</key>
    <string>{domain}</string>
    <key>DontWarnOnChange</key>
    <true/>
    <key>DontWarnOnDriveMount</key>
    <true/>
    <key>DontWarnOnQuit</key>
    <true/>
    <key>DriveRedirectionMode</key>
    <integer>{drives}</integer>
    <key>FontSmoothing</key>
    <true/>
    <key>FullWindowDrag</key>
    <false/>
    <key>HideMacDock</key>
    <true/>
    <key>KeyMappingTable</key>
    <dict>
        <key>UI_ALPHANUMERIC_KEY</key>
        <dict>
            <key>MacKeyCode</key>
            <integer>102</integer>
            <key>MacModifier</key>
            <integer>0</integer>
            <key>On</key>
            <true/>
        </dict>
        <key>UI_ALT_KEY</key>
        <dict>
            <key>MacKeyCode</key>
            <integer>4294967295</integer>
            <key>MacModifier</key>
            <integer>2048</integer>
            <key>On</key>
            <true/>
        </dict>
        <key>UI_CONTEXT_MENU_KEY</key>
        <dict>
            <key>MacKeyCode</key>
            <integer>120</integer>
            <key>MacModifier</key>
            <integer>2048</integer>
            <key>On</key>
            <true/>
        </dict>
        <key>UI_CONVERSION_KEY</key>
        <dict>
            <key>MacKeyCode</key>
            <integer>4294967295</integer>
            <key>MacModifier</key>
            <integer>0</integer>
            <key>On</key>
            <false/>
        </dict>
        <key>UI_HALF_FULL_WIDTH_KEY</key>
        <dict>
            <key>MacKeyCode</key>
            <integer>49</integer>
            <key>MacModifier</key>
            <integer>256</integer>
            <key>On</key>
            <true/>
        </dict>
        <key>UI_HIRAGANA_KEY</key>
        <dict>
            <key>MacKeyCode</key>
            <integer>104</integer>
            <key>MacModifier</key>
            <integer>0</integer>
            <key>On</key>
            <true/>
        </dict>
        <key>UI_NON_CONVERSION_KEY</key>
        <dict>
            <key>MacKeyCode</key>
            <integer>4294967295</integer>
            <key>MacModifier</key>
            <integer>0</integer>
            <key>On</key>
            <false/>
        </dict>
        <key>UI_NUM_LOCK_KEY</key>
        <dict>
            <key>MacKeyCode</key>
            <integer>71</integer>
            <key>MacModifier</key>
            <integer>0</integer>
            <key>On</key>
            <true/>
        </dict>
        <key>UI_PAUSE_BREAK_KEY</key>
        <dict>
            <key>MacKeyCode</key>
            <integer>99</integer>
            <key>MacModifier</key>
            <integer>2048</integer>
            <key>On</key>
            <true/>
        </dict>
        <key>UI_PRINT_SCREEN_KEY</key>
        <dict>
            <key>MacKeyCode</key>
            <integer>118</integer>
            <key>MacModifier</key>
            <integer>2048</integer>
            <key>On</key>
            <true/>
        </dict>
        <key>UI_SCROLL_LOCK_KEY</key>
        <dict>
            <key>MacKeyCode</key>
            <integer>107</integer>
            <key>MacModifier</key>
            <integer>0</integer>
            <key>On</key>
            <true/>
        </dict>
        <key>UI_SECONDARY_MOUSE_BUTTON</key>
        <dict>
            <key>MacKeyCode</key>
            <integer>256</integer>
            <key>MacModifier</key>
            <integer>4608</integer>
            <key>On</key>
            <true/>
        </dict>
        <key>UI_WINDOWS_START_KEY</key>
        <dict>
            <key>MacKeyCode</key>
            <integer>122</integer>
            <key>MacModifier</key>
            <integer>2048</integer>
            <key>On</key>
            <true/>
        </dict>
    </dict>
    <key>MenuAnimations</key>
    <false/>
    <key>PrinterRedirection</key>
    <true/>
    <key>RedirectFolder</key>
    <string>/Users/admin</string>
    <key>RedirectPrinter</key>
    <string></string>
    <key>RemoteApplication</key>
    <false/>
    <key>Themes</key>
    <true/>
    <key>UserName</key>
    <string>{username}</string>
    <key>Wallpaper</key>
    <{wallpaper}/>
    <key>WorkingDirectory</key>
    <string></string>
</dict>
</plist>'''.format(
            desktopSize=desktopSize,
            drives=drives,
            audioMode=audioMode,
            host=self.address,
            domain=self.domain,
            username=self.username,
            wallpaper=wallpaper
        )
