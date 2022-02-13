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
UDS managers (downloads, users preferences, publications, ...)

.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing

# Imports for type checking only (not on runtime), we have later to get rid of false "redefined outer names" for pylint
if typing.TYPE_CHECKING:
    from .crypto import CryptoManager
    from .task import TaskManager
    from .downloads import DownloadsManager
    from .log import LogManager
    from .user_service import UserServiceManager
    from .publication import PublicationManager
    from .notifications import NotificationsManager


def cryptoManager() -> 'CryptoManager':
    from .crypto import CryptoManager

    return CryptoManager.manager()


def taskManager() -> 'TaskManager':
    from .task import TaskManager

    return TaskManager.manager()


def downloadsManager() -> 'DownloadsManager':
    from .downloads import DownloadsManager

    return DownloadsManager.manager()


def logManager() -> 'LogManager':
    from .log import LogManager

    return LogManager.manager()


def userServiceManager() -> 'UserServiceManager':
    from .user_service import UserServiceManager

    return UserServiceManager.manager()


def publicationManager() -> 'PublicationManager':
    from .publication import PublicationManager

    return PublicationManager.manager()

def notificationsManager() -> 'NotificationsManager':
    from .notifications import NotificationsManager

    return NotificationsManager.manager()
