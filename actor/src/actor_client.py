#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2019 Virtual Cable S.L.
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
import sys
import os

import PyQt5  # pylint: disable=unused-import
from PyQt5.QtCore import QTimer

from udsactor.log import logger, INFO
from udsactor.client import UDSClientQApp
from udsactor.platform import operations

if __name__ == "__main__":
    logger.setLevel(INFO)

    # Ensure idle operations is initialized on start
    operations.initIdleDuration(0)

    if 'linux' in sys.platform:
        os.environ['QT_X11_NO_MITSHM'] = '1'

    UDSClientQApp.setQuitOnLastWindowClosed(False)

    qApp = UDSClientQApp(sys.argv)

    qApp.init()

    # Crate a timer, so we can check signals from time to time by executing python interpreter
    # Note: Signals are only checked on python code execution, so we create a timer to force call back to python
    timer = QTimer(qApp)
    timer.start(1000)
    timer.timeout.connect(lambda *a: None)

    qApp.exec_()

    # On windows, this point will never be reached :)
    qApp.end()

    logger.debug('Exiting...')
