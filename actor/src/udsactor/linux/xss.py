# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
# pylint: disable=invalid-name
import ctypes
import ctypes.util
import subprocess  # nosec


from udsactor.log import logger


xlib = None
xss = None
display = None
xssInfo = None
initialized = False


class XScreenSaverInfo(ctypes.Structure):  # pylint: disable=too-few-public-methods
    _fields_ = [
        ('window', ctypes.c_long),
        ('state', ctypes.c_int),
        ('kind', ctypes.c_int),
        ('til_or_since', ctypes.c_ulong),
        ('idle', ctypes.c_ulong),
        ('eventMask', ctypes.c_ulong),
    ]


class c_ptr(ctypes.c_void_p):
    pass


def _ensureInitialized():
    global xlib, xss, xssInfo, display, initialized  # pylint: disable=global-statement

    if initialized:
        return

    initialized = True

    try:
        xlibPath = ctypes.util.find_library('X11')
        xssPath = ctypes.util.find_library('Xss')
        xlib = xss = None
        if not xlibPath or not xssPath:
            raise Exception('Library Not found!!')

        xlib = ctypes.cdll.LoadLibrary(xlibPath)
        xss = ctypes.cdll.LoadLibrary(xssPath)

        # Fix result type to XScreenSaverInfo Structure
        xss.XScreenSaverQueryExtension.restype = ctypes.c_int
        xss.XScreenSaverQueryExtension.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
        ]
        xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(
            XScreenSaverInfo
        )  # Result in a XScreenSaverInfo structure
        xss.XScreenSaverQueryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(XScreenSaverInfo),
        ]
        xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        xlib.XOpenDisplay.restype = c_ptr

        display = xlib.XOpenDisplay(None)

        if not display.value:
            raise Exception('Display not found!')  # Invalid display, not accesible

        xssInfo = xss.XScreenSaverAllocInfo()

        # Ensures screen saver extension is available
        event_base = ctypes.c_int()
        error_base = ctypes.c_int()

        available = xss.XScreenSaverQueryExtension(
            display, ctypes.byref(event_base), ctypes.byref(error_base)
        )

        if available != 1:
            raise Exception('ScreenSaver not available')

    except Exception:  # Libraries not accesible, not found or whatever..
        xlib = xss = display = xssInfo = None


def initIdleDuration(atLeastSeconds: int) -> None:
    _ensureInitialized()
    if atLeastSeconds:
        try:
            subprocess.call(['/usr/bin/xset', 's', '{}'.format(atLeastSeconds + 30)])  # nosec
            # And now reset it
            subprocess.call(['/usr/bin/xset', 's', 'reset'])  # nosec
        except Exception as e:
            logger.error('Error setting screensaver time: %s', e)


def getIdleDuration() -> float:
    '''
    Returns idle duration, in seconds
    '''
    if not initialized or not xlib or not xss or not xssInfo:
        return 0  # Libraries not available

    xss.XScreenSaverQueryInfo(display, xlib.XDefaultRootWindow(display), xssInfo)

    # States: 0 = off, 1 = On, 2 = Cycle, 3 = Disabled, ...?
    if (
        xssInfo.contents.state == 1
    ):  # state = 1 means "active", so idle is not a valid state
        return (
            3600 * 100 * 1000
        )  # If screen saver is active, return a high enough value

    return xssInfo.contents.idle / 1000.0
