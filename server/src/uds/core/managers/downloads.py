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

import os
import logging

from wsgiref.util import FileWrapper
from django.http import HttpResponse, Http404, HttpRequest

from uds.core.managers.crypto import CryptoManager
from uds.core.util import singleton

logger = logging.getLogger(__name__)


class DownloadsManager(metaclass=singleton.Singleton):
    """
    Manager so connectors can register their own downloadables
    For registering, use at __init__.py of the conecto something like this:
        from uds.core.managers import DownloadsManager
        import os.path, sys
        downloadsManager().registerDownloadable('test.exe',
                                                        _('comments for test'),
                                                        os.path.join(os.path.dirname(sys.modules[__package__].__file__), 'files/test.exe'),
                                                        'application/x-msdos-program')
    """

    _downloadables: dict[str, dict[str, str]] = {}

    def __init__(self) -> None:
        super().__init__()
        self._downloadables = {}

    @staticmethod
    def manager() -> 'DownloadsManager':
        # Singleton pattern will return always the same instance
        return DownloadsManager()

    def register(self, name: str, comment: str, path: str, mime: str = 'application/octet-stream') -> None:
        """
        Registers a downloadable file.
        @param name: name shown
        @param path: path to file
        @params zip: If download as zip
        """
        _id = CryptoManager.manager().uuid(name)
        self._downloadables[_id] = {
            'name': name,
            'comment': comment,
            'path': path,
            'mime': mime,
        }

    def downloadables(self) -> dict[str, dict[str, str]]:
        return self._downloadables

    def send(self, request: 'HttpRequest', _id: str) -> HttpResponse:
        if _id not in self._downloadables:
            logger.error('Downloadable id %s not found in %s!!!', _id, self._downloadables)
            raise Http404
        return self._send_file(
            request,
            self._downloadables[_id]['name'],
            self._downloadables[_id]['path'],
            self._downloadables[_id]['mime'],
        )

    def _send_file(self, request: 'HttpRequest', name: str, filename: str, mime: str) -> HttpResponse:
        """
        Send a file through Django without loading the whole file into
        memory at once. The FileWrapper will turn the file object into an
        iterator for chunks of 8KB.
        """
        try:
            wrapper = FileWrapper(open(filename, 'rb'))  # pylint: disable=consider-using-with
            response = HttpResponse(wrapper, content_type=mime)
            response['Content-Length'] = os.path.getsize(filename)
            response['Content-Disposition'] = 'attachment; filename=' + name
            return response
        except Exception as e:
            logger.error('Error sending file %s: %s', filename, e)
            raise Http404
