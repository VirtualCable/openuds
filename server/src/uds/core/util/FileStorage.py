# -*- coding: utf-8 -*-

#
# Copyright (c) 2016 Virtual Cable S.L.
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
# pylint: disable=no-name-in-module,import-error, maybe-no-member
from __future__ import unicode_literals

from django.core.cache import caches
from django.core.files import File
from django.core.files.storage import Storage
from django.conf import settings
from six.moves.urllib import parse as urlparse  # @UnresolvedImport

from uds.models.DBFile import DBFile
from .tools import DictAsObj

import six
import os
import logging

logger = logging.getLogger(__name__)


class FileStorage(Storage):
    def __init__(self, *args, **kwargs):
        self._base_url = getattr(settings, 'FILE_STORAGE', '/files')
        if self._base_url[-1] != '/':
            self._base_url += '/'

        cacheName = getattr(settings, 'FILE_CACHE', 'memory')

        try:
            cache = caches[cacheName]
        except:
            cache = None

        self.cache = cache

        Storage.__init__(self, *args, **kwargs)


    def get_valid_name(self, name):
        return name.replace('\\', os.path.sep)

    def _getKey(self, name):
        '''
            We have only a few files on db, an we are running on a 64 bits system
            memcached does not allow keys bigger than 250 chars, so we are going to use hash() to
            get a key for this
        '''
        return 'fstor' + six.text_type(hash(self.get_valid_name(name)))

    def _dbFileForReadOnly(self, name):
        # If we have a cache, & the cache contains the object
        if self.cache is not None:
            dbf = self.cache.get(self._getKey(name))
            if dbf is not None:
                return dbf

        return self._dbFileForReadWrite(name)

    def _dbFileForReadWrite(self, name):
        f = DBFile.objects.get(name=self.get_valid_name(name))
        self._storeInCache(f)
        return f

    def _storeInCache(self, f):
        if self.cache is None:
            return

        dbf = DictAsObj({
            'name': f.name,
            'uuid': f.uuid,
            'size': f.size,
            'data': f.data,
            'created': f.created,
            'modified': f.modified
        })

        self.cache.set(self._getKey(f.name), dbf, 3600)  # Cache defaults to one hour

    def _removeFromCache(self, name):
        if self.cache is None:
            return
        self.cache.delete(self._getKey(name))


    def _open(self, name, mode='rb'):
        f = six.BytesIO(self._dbFileForReadOnly(name).data)
        f.name = name
        f.mode = mode
        return File(f)

    def _save(self, name, content):
        name = self.get_valid_name(name)
        try:
            f = self._dbFileForReadWrite(name)
        except DBFile.DoesNotExist:
            f = DBFile.objects.create(name=name)

        f.data = content.read()
        f.save()

        # Store on cache also
        self._storeInCache(f)

        return name

    def accessed_time(self, name):
        raise NotImplementedError

    def created_time(self, name):
        return self._dbFileForReadOnly(name).created

    def modified_time(self, name):
        return self._dbFileForReadOnly(name).modified

    def size(self, name):
        return self._dbFileForReadOnly(name).size

    def delete(self, name):
        self._dbFileForReadWrite(name).delete()
        self._removeFromCache(name)

    def exists(self, name):
        try:
            self._dbFileForReadOnly(name)
            return True
        except DBFile.DoesNotExist:
            return False

    def url(self, name):
        uuid = self._dbFileForReadWrite(name).uuid
        return urlparse.urljoin(self._base_url, uuid)
