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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''

from uds.core.managers.UserPrefsManager import UserPrefsManager, CommonPrefs
from uds.core.managers.DownloadsManager import DownloadsManager
from uds.core.util.Config import Config
from .NXTransport import NXTransport
from .TSNXTransport import TSNXTransport
from django.utils.translation import ugettext_noop as _
import os.path

Config.section('NX').value('downloadUrl', 'http://sourceforge.net/projects/opennx/files/opennx/CI-win32/OpenNX-0.16.0.725-Setup.exe/download').get()
Config.section('NX').value('downloadUrlMACOS', 'http://opennx.net/download.html').get()


UserPrefsManager.manager().registerPrefs('nx', _('NX Protocol'), [CommonPrefs.screenSizePref])

# DownloadsManager.manager().registerDownloadable('udsactor-nx_1.0_all.deb',
#                                                _('UDS Actor connector for NX <b>(requires nomachine packages)</b>'),
#                                                os.path.dirname(sys.modules[__package__].__file__) + '/files/udsactor-nx_1.0_all.deb',
#                                                'application/x-debian-package')
