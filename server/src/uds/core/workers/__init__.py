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
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

import logging

logger = logging.getLogger(__name__)


def initialize():
    """
    This imports all packages that are descendant of this package, and, after that,
    it register all subclases of service provider as
    """
    import os.path
    import pkgutil
    import sys
    from uds.core import jobs
    from uds.core.managers.TaskManager import TaskManager

    # Dinamycally import children of this package.
    pkgpath = os.path.dirname(sys.modules[__name__].__file__)
    for _, name, _ in pkgutil.iter_modules([pkgpath]):
        logger.debug('Importing {}'.format(name))
        __import__(name, globals(), locals(), [], 1)

    p = jobs.Job
    # This is marked as error in IDE, but it's not (__subclasses__)
    for cls in p.__subclasses__():
        logger.debug('Examining worker {}'.format(cls.__module__))
        # Limit to autoregister just workers jobs inside this module
        if cls.__module__[0:16] == 'uds.core.workers':
            logger.debug('Added worker {} to list'.format(cls.__module__))
            TaskManager.registerJob(cls)
