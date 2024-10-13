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
import unicodedata

import django.template.defaultfilters as filters
from django.utils import formats
from django.utils.translation import gettext

logger = logging.getLogger(__name__)

VT = typing.TypeVar('VT')

class CaseInsensitiveDict(dict[str, VT]):
    @staticmethod
    def _k(key: str) -> str:
        return key.lower()

    def __init__(self, *args: typing.Any, **kwargs: VT):
        super().__init__(*args, **kwargs)
        self._convert_keys()

    def __getitem__(self, key: str) -> VT:
        return super().__getitem__(CaseInsensitiveDict._k(key))

    def __setitem__(self, key: str, value: VT) -> None:
        super().__setitem__(CaseInsensitiveDict._k(key), value)

    def __delitem__(self, key: str) -> None:
        return super().__delitem__(CaseInsensitiveDict._k(key))

    def __contains__(self, key: typing.Any) -> bool:
        if not isinstance(key, str):
            return False
        return super().__contains__(key.lower())

    def pop(self, key: str, *args: typing.Any, **kwargs: typing.Any) -> VT:
        return super().pop(CaseInsensitiveDict._k(key), *args, **kwargs)

    def get(self, key: str, *args: typing.Any, **kwargs: typing.Any) -> typing.Optional[VT]: # type: ignore
        return super().get(CaseInsensitiveDict._k(key), *args, **kwargs)

    def setdefault(self, key: str, *args: typing.Any, **kwargs: typing.Any) -> VT:
        return super().setdefault(
            CaseInsensitiveDict._k(key), *args, **kwargs
        )  # pylint: disable=protected-access

    def _convert_keys(self) -> None:
        for k in list(self.keys()):  # List is to make a copy of keys, because we are going to change it
            v = super().pop(k)  # Remove old key-value
            self.__setitem__(k, v)  # Set new key-value, with lower case key


def package_relative_file(module_name: str, file_name: str) -> str:
    """
    Helper to get image path from relative to a module.
    This allows to keep images alongside report
    """
    mod = sys.modules[module_name]
    if mod and hasattr(mod, '__file__') and mod.__file__:
        pkgpath = os.path.dirname(mod.__file__)
        return os.path.join(pkgpath, file_name)
    # Not found, return fileName
    return file_name


def timestamp_as_str(stamp: float, format_: typing.Optional[str] = None) -> str:
    """
    Converts a timestamp to date string using specified format (DJANGO format such us SHORT_DATETIME_FORMAT..)
    """
    format_ = formats.get_format(format_ or 'SHORT_DATETIME_FORMAT')
    return filters.date(datetime.datetime.fromtimestamp(stamp), format_)


def seconds_to_time_string(seconds: int) -> str:
    seconds = int(seconds)
    minutes = seconds // 60
    seconds %= 60
    hours = minutes // 60
    minutes %= 60
    days = hours // 24
    hours %= 24
    return gettext('{} days {:d}:{:02d}:{:02d}').format(days, hours, minutes, seconds)


def remove_control_chars(s: str) -> str:
    """
    Removes control characters from an unicode string

    Arguments:
        s {str} -- string to remove control characters from

    Returns:
        str -- string without control characters
    """
    return ''.join(ch for ch in s if unicodedata.category(ch)[0] != "C")


def load_icon(icon_filename: str) -> bytes:
    """
    Loads an icon from icons directory
    """
    try:
        with open(icon_filename, 'rb') as f:
            data = f.read()
    except Exception as e:
        logger.error('Error reading icon file  %s: %s', icon_filename, e)
        # blank png bytes
        data = base64.b64decode(
            (
                b'iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAAY0lEQVR42u3QAREAAAQEMJKL'
                b'/nI4W4R1KlOPtQABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAg'
                b'AABAgQIECBAgAABAgQIECBAgAABAgQIEHDfAvLdn4FABR1mAAAAAElFTkSuQmCC'
            )
        )

    return data


def load_icon_b64(iconFilename: str) -> str:
    """
    Loads an icon from icons directory
    """
    return base64.b64encode(load_icon(iconFilename)).decode('ascii')


@contextlib.contextmanager
def ignore_exceptions(log: bool = False) -> typing.Iterator[None]:
    """
    Ignores exceptions
    """
    try:
        yield
    except Exception as e:
        if log:
            logger.error('Ignoring exception: %s', e)
        pass

class ExecutionTimer:
    _start: datetime.datetime
    _end: datetime.datetime
    _running: bool
    
    _delay_threshold: float
    _max_delay_rate: float

    def __init__(self, delay_threshold: float, *, max_delay_rate: float = 4.0) -> None:
        """
        Creates a new ExecutionTimer
        
        Arguments:
            delay_threshold {float} -- Threshold for the delay rate, in seconds.
            max_delay_rate {float} -- Maximum delay rate, defaults to 4.0
            
        Note:
        - delay_threshold is the time in seconds that we consider an operation is taking too long
        - max_delay_rate is the maximum delay rate, if the operation is taking longer than the threshold, we will
          multiply the delay by the delay rate, but at most by the max delay rate
        - The delay will be calculated as the elapsed time divided by the threshold, at most the max delay rate
        - A value of <= 0.0 will not delay at all, a value of 1.0 will delay as much as the elapsed time, a value of 2.0
            will delay twice the elapsed time, and so on
        """
        self._start = datetime.datetime.now()
        self._end = self._start
        self._running = False
        
        self._delay_threshold = delay_threshold
        self._max_delay_rate = max_delay_rate

    def __enter__(self) -> 'ExecutionTimer':
        self._start = self._end = datetime.datetime.now()
        self._running = True
        return self

    def __exit__(self, exc_type: typing.Any, exc_value: typing.Any, traceback: typing.Any) -> None:
        self._running = False
        self._end = datetime.datetime.now()

    @property
    def elapsed(self) -> datetime.timedelta:
        if self._running:
            return datetime.datetime.now() - self._start
        return self._end - self._start

    @property
    def delay_rate(self) -> float:
        """
        Returns the delay rate based on the elapsed time
        Delay rate is a multiplier for the delay time based on the elapsed time
        I.e:
        - If the elapsed time is 0, the delay rate is 1.0
        - If the delay_threshold is lower or equal to 0, the delay rate is 1.0
        - If the elapsed time is greater than the threshold, the delay rate is the elapsed time divided by the threshold
          for example:
            * threshold = 2, elapsed = 4, delay rate = 2.0
            * threshold = 2, elapsed = 8, delay rate = 4.0
        - If the delay rate is greater than the max delay rate, the delay rate is the max delay rate
        
        This allows us to increase the delay for next check based on how long the operation is taking
        (the longer it takes, the longer we wait for the next check)
        """
        if self._delay_threshold > 0 and self.elapsed.total_seconds() > self._delay_threshold:
            # Ensure we do not delay too much, at most MAX_DELAY_RATE times
            return min(self.elapsed.total_seconds() / self._delay_threshold, self._max_delay_rate)
        return 1.0
