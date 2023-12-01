# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
# All rights reserved.
#
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
import os.path
import typing
import sys

from django.utils.translation import gettext_noop as _
from uds.core import osmanagers
from uds.core import managers
from uds.core.consts.system import VERSION

from .windows import WindowsOsManager
from .windows_domain import WinDomainOsManager
from .windows_random import WinRandomPassManager

managers.downloadsManager().registerDownloadable(
    f'UDSActorSetup-{VERSION}.exe',
    _('UDS Actor for windows machines'),
    os.path.dirname(typing.cast(str, sys.modules[__package__].__file__))
    + f'/files/UDSActorSetup-{VERSION}.exe',
    'application/vnd.microsoft.portable-executable',
)

managers.downloadsManager().registerDownloadable(
    f'UDSActorUnmanagedSetup-{VERSION}.exe',
    _('UDS Actor for Unmanaged windows machines. Used ONLY for static machines.'),
    os.path.dirname(typing.cast(str, sys.modules[__package__].__file__))
    + f'/files/UDSActorUnmanagedSetup-{VERSION}.exe',
    'application/vnd.microsoft.portable-executable',
)
