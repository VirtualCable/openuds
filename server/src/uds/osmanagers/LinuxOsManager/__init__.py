# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2023 Virtual Cable S.L.U.
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
@Author: Adolfo Gómez, dkmaster at dkmon dot com
@Author: Alexander Burmatov,  thatman at altlinux dot org
"""
# pyright: reportUnusedImport=false
import os.path
import typing
import sys

from django.utils.translation import gettext_noop as _
from uds.core.managers import downloads_manager
from uds.core.consts.system import VERSION

from .linux_osmanager import LinuxOsManager
from .linux_randompass_osmanager import LinuxRandomPassManager
from .linux_ad_osmanager import LinuxOsADManager

_mypath = os.path.dirname(__spec__.origin)  # type: ignore[name-defined]  # mypy incorrectly report __spec__ as not beind defined
# Old version, using spec is better, but we can use __package__ as well
#_mypath = os.path.dirname(typing.cast(str, sys.modules[__package__].__file__))  # pyright: ignore

downloads_manager().register(
    f'udsactor_{VERSION}_all.deb',
    _('UDS Actor for Debian, Ubuntu, ... Linux machines <b>(Requires python >= 3.9)</b>'),
    _mypath + f'/files/udsactor_{VERSION}_all.deb',
    'application/x-debian-package',
)

downloads_manager().register(
    f'udsactor-{VERSION}-1.noarch.rpm',
    _('UDS Actor for Centos, Fedora, RH, Suse, ... Linux machines <b>(Requires python >= 3.9)</b>'),
    _mypath + f'/files/udsactor-{VERSION}-1.noarch.rpm',
    'application/x-redhat-package-manager',
)

downloads_manager().register(
    f'udsactor-unmanaged_{VERSION}_all.deb',
    _(
        'UDS Actor for Debian based Linux machines. Used ONLY for static machines. <b>(Requires python >= 3.9)</b>'
    ),
    _mypath + f'/files/udsactor-unmanaged_{VERSION}_all.deb',
    'application/x-debian-package',
)

downloads_manager().register(
    f'udsactor-unmanaged-{VERSION}-1.noarch.rpm',
    _(
        'UDS Actor for Centos, Fedora, RH, Suse, ... Linux machines. Used ONLY for static machines. <b>(Requires python >= 3.9)</b>'
    ),
    _mypath + f'/files/udsactor-unmanaged-{VERSION}-1.noarch.rpm',
    'application/x-redhat-package-manager',
)

