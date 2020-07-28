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

import os.path
import pkgutil
import sys
import importlib
import logging
import typing

# Forces dispatchers to be already present
import uds.dispatchers  # pylint: disable=unused-import

logger = logging.getLogger(__name__)

patterns: typing.List = []


def loadModulesUrls():
    logger.debug('Looking for dispatching modules')
    if not patterns:
        logger.debug('Looking for patterns')
        try:
            modName = 'uds.dispatchers'
            pkgpath = os.path.dirname(sys.modules[modName].__file__)
            for _, name, _ in pkgutil.iter_modules([pkgpath]):
                fullModName = '{}.{}.urls'.format(modName, name)
                try:
                    # mod = __import__(fullModName, globals(), locals(), ['urlpatterns'], 0)
                    mod = importlib.import_module(fullModName)
                    logger.debug('Loaded mod %s, url %s', mod, mod.urlpatterns)
                    # Append patters from mod
                    for up in mod.urlpatterns:
                        patterns.append(up)
                except Exception:
                    logger.exception('Loading patterns')
        except Exception:
            logger.exception('Processing dispatchers loading')

    importlib.invalidate_caches()

    return patterns
