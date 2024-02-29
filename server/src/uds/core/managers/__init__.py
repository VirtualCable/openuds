# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2022 Virtual Cable S.L.U.
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
UDS managers (downloads, users publications, ...)

Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import typing

# Imports for type checking only (not on runtime), we have later to get rid of false "redefined outer names" for pylint
if typing.TYPE_CHECKING:
    from .task import TaskManager
    from .downloads import DownloadsManager
    from .log import LogManager
    from .publication import PublicationManager
    from .notifications import NotificationsManager


def task_manager() -> 'TaskManager':
    from .task import TaskManager

    return TaskManager()


def downloads_manager() -> 'DownloadsManager':
    from .downloads import DownloadsManager

    return DownloadsManager()


def log_manager() -> 'LogManager':
    from .log import LogManager

    return LogManager()


def publication_manager() -> 'PublicationManager':
    from .publication import PublicationManager

    return PublicationManager()


def notifications_manager() -> 'NotificationsManager':
    from .notifications import NotificationsManager

    return NotificationsManager()
