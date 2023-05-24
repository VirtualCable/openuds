# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
# First, try to use PyQt6, available on arm64, x86_64, i386, ...
try:
    from PyQt6 import QtCore, QtWidgets, QtGui  # type: ignore
    from PyQt6.QtCore import QSettings  # type: ignore

    from .qt6.UDSLauncherMac import Ui_MacLauncher
    from .qt6.UDSWindow import Ui_MainWindow
    from .qt6 import UDSResources_rc
    QT_VERSION = 6

except ImportError:  # If not found, try to use PyQt5 (not available on arm64)
    from PyQt5 import QtCore, QtWidgets, QtGui  # type: ignore
    from PyQt5.QtCore import QSettings  # type: ignore

    from .qt5.UDSLauncherMac import Ui_MacLauncher  # type: ignore
    from .qt5.UDSWindow import Ui_MainWindow  # type: ignore
    from .qt5 import UDSResources_rc  # type: ignore
    QT_VERSION = 5

__all__ = ['QtCore', 'QtWidgets', 'QtGui', 'Ui_MacLauncher', 'Ui_MainWindow', 'UDSResources_rc', 'QSettings', 'QT_VERSION']
