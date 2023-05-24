# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2021 Virtual Cable S.L.U.
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
import logging
import os
import os.path
import platform
import sys
import tempfile

# First, try to use PyQt6, available on arm64, x86_64, i386, ...
try:
    from PyQt6 import QtCore   # Just to test if it's available
    QT='PyQt6'
except ImportError:  # If not found, it is using PyQt5
    QT='PyQt5'


LOGLEVEL = logging.INFO
DEBUG = False

# Update debug level if uds-debug-on exists
if 'linux' in sys.platform or 'darwin' in sys.platform:
    logFile = os.path.expanduser('~/udsclient.log')
    if os.path.isfile(os.path.expanduser('~/uds-debug-on')):
        LOGLEVEL = logging.DEBUG
        DEBUG = True
else:
    logFile = os.path.join(tempfile.gettempdir(), 'udsclient.log')
    if os.path.isfile(os.path.join(tempfile.gettempdir(), 'uds-debug-on')):
        LOGLEVEL = logging.DEBUG
        DEBUG = True

try:
    logging.basicConfig(
        filename=logFile,
        filemode='a',
        format='%(levelname)s %(asctime)s %(message)s',
        level=LOGLEVEL,
    )
except Exception:
    logging.basicConfig(format='%(levelname)s %(asctime)s %(message)s', level=LOGLEVEL)

logger = logging.getLogger('udsclient')

if DEBUG:
    # Include as much as platform info as possible
    logger.debug('Platform info:')
    logger.debug('  Platform: %s', platform.platform())
    logger.debug('  Node: %s', platform.node())
    logger.debug('  System: %s', platform.system())
    logger.debug('  Release: %s', platform.release())
    logger.debug('  Version: %s', platform.version())
    logger.debug('  Machine: %s', platform.machine())
    logger.debug('  Processor: %s', platform.processor())
    logger.debug('  Architecture: %s', platform.architecture())
    logger.debug('  Python version: %s', platform.python_version())
    logger.debug('  Python implementation: %s', platform.python_implementation())
    logger.debug('  Python compiler: %s', platform.python_compiler())
    logger.debug('  Python build: %s', platform.python_build())
    # Also environment variables and any useful info
    logger.debug('Qt framework: %s', QT)
    logger.debug('Log level set to DEBUG')
    logger.debug('Environment variables:')
    for k, v in os.environ.items():
        logger.debug('  %s=%s', k, v)

    # usefull info for debugging
    logger.debug('Python path: %s', sys.path)
    logger.debug('Python executable: %s', sys.executable)
    logger.debug('Python version: %s', sys.version)
    logger.debug('Python version info: %s', sys.version_info)
    logger.debug('Python prefix: %s', sys.prefix)
    logger.debug('Python base prefix: %s', sys.base_prefix)
    logger.debug('Python executable: %s', sys.executable)
    logger.debug('Python argv: %s', sys.argv)
    logger.debug('Python modules path: %s', sys.path)
    logger.debug('Python modules path (site): %s', sys.path_importer_cache)
    logger.debug('Python modules path (site): %s', sys.path_hooks)
    