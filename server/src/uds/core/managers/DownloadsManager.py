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

"""
@author: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

import os
import uuid
from django.http import HttpResponse, Http404
from wsgiref.util import FileWrapper

from uds.core.managers import cryptoManager

import six

import logging

logger = logging.getLogger(__name__)


class DownloadsManager(object):
    """
    Manager so connectors can register their own downloadables
    For registering, use at __init__.py of the conecto something like this:
        from uds.core.managers.DownloadsManager import DownloadsManager
        import os.path, sys
        DownloadsManager.manager().registerDownloadable('test.exe',
                                                        _('comments for test'),
                                                        os.path.join(os.path.dirname(sys.modules[__package__].__file__), 'files/test.exe'),
                                                        'application/x-msdos-program')
    """
    _manager = None

    def __init__(self):
        self._downloadables = {}

    @staticmethod
    def manager():
        if DownloadsManager._manager is None:
            DownloadsManager._manager = DownloadsManager()
        return DownloadsManager._manager

    def registerDownloadable(self, name, comment, path, mime='application/octet-stream'):
        """
        Registers a downloadable file.
        @param name: name shown
        @param path: path to file
        @params zip: If download as zip
        """
        _id = cryptoManager().uuid(name)
        self._downloadables[_id] = {'name': name, 'comment': comment, 'path': path, 'mime': mime}

    def getDownloadables(self):
        return self._downloadables

    def send(self, request, _id):
        if _id not in self._downloadables:
            logger.error('ID {0} not found in {1}!!!'.format(_id, self._downloadables))
            raise Http404
        return self._send_file(request, self._downloadables[_id]['name'], self._downloadables[_id]['path'], self._downloadables[_id]['mime'])

    def _send_file(self, _, name, filename, mime):
        """
        Send a file through Django without loading the whole file into
        memory at once. The FileWrapper will turn the file object into an
        iterator for chunks of 8KB.
        """
        wrapper = FileWrapper(open(filename, 'rb'))
        response = HttpResponse(wrapper, content_type=mime)
        response['Content-Length'] = os.path.getsize(filename)
        response['Content-Disposition'] = 'attachment; filename=' + name
        return response
