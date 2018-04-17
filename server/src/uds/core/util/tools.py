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

from django.utils import formats
from django.utils.translation import ugettext
import django.template.defaultfilters as filters

import datetime

import sys
import os
import six

__updated__ = '2018-01-24'


class DictAsObj(object):
    """
    Returns a mix between a dict and an obj
    Can be accesses as .xxxx or ['xxx']
    """

    def __init__(self, dct=None, **kwargs):
        if dct is not None:
            self.__dict__.update(dct)
        self.__dict__.update(kwargs)

    def __getitem__(self, key):
        return self.__dict__[key]

    def __unicode__(self):
        return ', '.join(
            '{}={}'.format(v, self.__dict__[v]) for v in self.__dict__
        )


class CaseInsensitiveDict(dict):

    @classmethod
    def _k(cls, key):
        return key.lower() if isinstance(key, six.text_type) else key

    def __init__(self, *args, **kwargs):
        super(CaseInsensitiveDict, self).__init__(*args, **kwargs)
        self._convert_keys()

    def __getitem__(self, key):
        return super(CaseInsensitiveDict, self).__getitem__(self.__class__._k(key))

    def __setitem__(self, key, value):
        super(CaseInsensitiveDict, self).__setitem__(self.__class__._k(key), value)

    def __delitem__(self, key):
        return super(CaseInsensitiveDict, self).__delitem__(self.__class__._k(key))

    def __contains__(self, key):
        return super(CaseInsensitiveDict, self).__contains__(self.__class__._k(key))

    def has_key(self, key):
        return super(CaseInsensitiveDict, self).has_key(self.__class__._k(key))

    def pop(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).pop(self.__class__._k(key), *args, **kwargs)

    def get(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).get(self.__class__._k(key), *args, **kwargs)

    def setdefault(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).setdefault(self.__class__._k(key), *args, **kwargs)

    def update(self, E=None, **F):
        if E is None:
            E = {}
        super(CaseInsensitiveDict, self).update(self.__class__(E))
        super(CaseInsensitiveDict, self).update(self.__class__(**F))

    def _convert_keys(self):
        for k in list(self.keys()):
            v = super(CaseInsensitiveDict, self).pop(k)
            self.__setitem__(k, v)


def packageRelativeFile(moduleName, fileName):
    """
    Helper to get image path from relative to a module.
    This allows to keep images alongside report
    """
    pkgpath = os.path.dirname(sys.modules[moduleName].__file__)
    return os.path.join(pkgpath, fileName)


def timestampAsStr(stamp, format_='SHORT_DATETIME_FORMAT'):
    """
    Converts a timestamp to date string using specified format (DJANGO format such us SHORT_DATETIME_FORMAT..)
    """
    format_ = formats.get_format(format_)
    return filters.date(datetime.datetime.fromtimestamp(stamp), format_)


def secondsToString(seconds):
    seconds = int(seconds)
    minutes = seconds / 60
    seconds %= 60
    hours = minutes / 60
    minutes %= 60
    days = hours / 24
    hours %= 24
    res = []
    if days > 0:
        res.append(ugettext('{} days').format(days))
    if hours > 0:
        res.append(ugettext('{} hours').format(hours))
    if minutes > 0:
        res.append(ugettext('{} minutes').format(minutes))
    res.append(ugettext('{} seconds').format(seconds))

    return ', '.join(res)


def b2(s):
    """
    Returns a b'' string on python2, or str on python3
    """
    if six.PY2:
        return s.encode('utf8')
    return s


def u2(s):
    """
    returns an u'' string on python2, or str on python3
    """
    if six.PY2:
        return s.decode('utf8')
    return s
