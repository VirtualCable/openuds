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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import base64
import contextlib
import datetime
import logging
import os
import sys
import typing
import collections.abc
import unicodedata

import django.template.defaultfilters as filters
from django.utils import formats
from django.utils.translation import gettext

logger = logging.getLogger(__name__)


class CaseInsensitiveDict(dict):
    @classmethod
    def _k(cls, key: str) -> str:
        return key.lower() if isinstance(key, str) else key

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._convert_keys()

    def __getitem__(self, key: str) -> typing.Any:
        return super().__getitem__(self.__class__._k(key.lower()))

    def __setitem__(self, key: str, value: typing.Any) -> None:
        super().__setitem__(self.__class__._k(key.lower()), value)

    def __delitem__(self, key: str) -> None:
        return super().__delitem__(self.__class__._k(key.lower()))

    def __contains__(self, key: typing.Any) -> bool:
        if not isinstance(key, str):
            return False
        return super().__contains__(key.lower())

    def pop(self, key: str, *args, **kwargs) -> typing.Any:
        return super().pop(self.__class__._k(key.lower()), *args, **kwargs)  # pylint: disable=protected-access

    def get(self, key: str, *args, **kwargs) -> typing.Any:
        return super().get(self.__class__._k(key.lower()), *args, **kwargs)  # pylint: disable=protected-access

    def setdefault(self, key: str, *args, **kwargs) -> typing.Any:
        return super().setdefault(
            self.__class__._k(key.lower()), *args, **kwargs
        )  # pylint: disable=protected-access

    def update(self, other_dct=None, **kwargs):
        super().update(self.__class__(other_dct or {}, **kwargs))

    def _convert_keys(self) -> None:
        for k in list(self.keys()):  # List is to make a copy of keys, because we are going to change it
            v = super().pop(k)  # Remove old key-value
            self.__setitem__(k, v)  # Set new key-value, with lower case key


def package_relative_file(moduleName: str, fileName: str) -> str:
    """
    Helper to get image path from relative to a module.
    This allows to keep images alongside report
    """
    mod = sys.modules[moduleName]
    if mod and hasattr(mod, '__file__') and mod.__file__:
        pkgpath = os.path.dirname(mod.__file__)
        return os.path.join(pkgpath, fileName)
    # Not found, return fileName
    return fileName


def timestampAsStr(stamp, format_='SHORT_DATETIME_FORMAT'):
    """
    Converts a timestamp to date string using specified format (DJANGO format such us SHORT_DATETIME_FORMAT..)
    """
    format_ = formats.get_format(format_)
    return filters.date(datetime.datetime.fromtimestamp(stamp), format_)


def secondsToTimeString(seconds: int) -> str:
    seconds = int(seconds)
    minutes = seconds // 60
    seconds %= 60
    hours = minutes // 60
    minutes %= 60
    days = hours // 24
    hours %= 24
    return gettext('{} days {:d}:{:02d}:{:02d}').format(days, hours, minutes, seconds)


def removeControlCharacters(s: str) -> str:
    """
    Removes control characters from an unicode string

    Arguments:
        s {str} -- string to remove control characters from

    Returns:
        str -- string without control characters
    """
    return ''.join(ch for ch in s if unicodedata.category(ch)[0] != "C")


def loadIcon(iconFilename: str) -> bytes:
    """
    Loads an icon from icons directory
    """
    try:
        with open(iconFilename, 'rb') as f:
            data = f.read()
    except Exception as e:
        logger.error('Error reading icon file  %s: %s', iconFilename, e)
        # blank png bytes
        data = base64.b64decode(
            (
                b'iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAAY0lEQVR42u3QAREAAAQEMJKL'
                b'/nI4W4R1KlOPtQABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAg'
                b'AABAgQIECBAgAABAgQIECBAgAABAgQIEHDfAvLdn4FABR1mAAAAAElFTkSuQmCC'
            )
        )

    return data


def load_Icon_b64(iconFilename: str) -> str:
    """
    Loads an icon from icons directory
    """
    return base64.b64encode(loadIcon(iconFilename)).decode('ascii')


@contextlib.contextmanager
def ignoreExceptions():
    """
    Ignores exceptions
    """
    try:
        yield
    except Exception:  # nosec: want to catch all exceptions
        pass
