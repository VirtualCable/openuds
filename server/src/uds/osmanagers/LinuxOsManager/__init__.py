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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import os.path
import sys

from django.utils.translation import ugettext_noop as _
from uds.core.osmanagers.osmfactory import OSManagersFactory
from uds.core.managers import downloadsManager
from uds.core import VERSION

from .linux_osmanager import LinuxOsManager
from .linux_randompass_osmanager import LinuxRandomPassManager

OSManagersFactory.factory().insert(LinuxOsManager)
OSManagersFactory.factory().insert(LinuxRandomPassManager)

downloadsManager().registerDownloadable(
    'udsactor_{version}_all.deb'.format(version=VERSION),
    _('UDS Actor for Debian, Ubuntu, ... Linux machines <b>(Requires python >= 3.5)</b>'),
    os.path.dirname(sys.modules[__package__].__file__) + '/files/udsactor_{version}_all.deb'.format(version=VERSION),
    'application/x-debian-package'
)

downloadsManager().registerDownloadable(
    'udsactor-{version}-1.noarch.rpm'.format(version=VERSION),
    _('UDS Actor for Centos, Fedora, RH, ... Linux machines <b>(Requires python 2.7)</b>'),
    os.path.dirname(sys.modules[__package__].__file__) + '/files/udsactor-{version}-1.noarch.rpm'.format(version=VERSION),
    'application/x-redhat-package-manager'
)

downloadsManager().registerDownloadable(
    'udsactor-opensuse-{version}-1.noarch.rpm'.format(version=VERSION),
    _('UDS Actor for openSUSE, ... Linux machines <b>(Requires python 2.7)</b>'),
    os.path.dirname(sys.modules[__package__].__file__) + '/files/udsactor-opensuse-{version}-1.noarch.rpm'.format(version=VERSION),
    'application/x-redhat-package-manager'
)

downloadsManager().registerDownloadable(
    'udsactor_2.2.0_legacy.deb',
    _('<b>Legacy</b> UDS Actor for Debian, Ubuntu, ... Linux machines <b>(Requires python 2.7)</b>'),
    os.path.dirname(sys.modules[__package__].__file__) + '/files/udsactor_2.2.0_legacy.deb',
    'application/x-debian-package'
)

downloadsManager().registerDownloadable(
    'udsactor-unmanaged_{version}_all.deb'.format(version=VERSION),
    _('UDS Actor for Debian, Ubuntu, ... Linux machines <b>(Requires python >= 3.5)</b>'),
    os.path.dirname(sys.modules[__package__].__file__) + '/files/udsactor-unmanaged_{version}_all.deb'.format(version=VERSION),
    'application/x-debian-package'
)
