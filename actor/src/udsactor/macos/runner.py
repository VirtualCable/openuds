# -*- coding: utf-8 -*-
#
# Copyright (c) 2022 Virtual Cable S.L.U.
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
import sys
import typing

from .. import rest
from .. import platform
from ..log import logger
from .service import UDSActorSvc

def usage() -> typing.NoReturn:
    sys.stderr.write('usage: udsactor start|login "username"|logout "username"\n')
    sys.exit(2)

def run() -> None:
    logger.setLevel(20000)

    if len(sys.argv) == 3 and sys.argv[1] in ('login', 'logout'):
        logger.debug('Running client udsactor')
        try:
            client: rest.UDSClientApi = rest.UDSClientApi()
            if sys.argv[1] == 'login':
                r = client.login(sys.argv[2], platform.operations.getSessionType())
                print('{},{},{},{}\n'.format(r.ip, r.hostname, r.max_idle, r.dead_line or ''))
            elif sys.argv[1] == 'logout':
                client.logout(sys.argv[2], platform.operations.getSessionType())
        except Exception as e:
            logger.exception()
            logger.error('Got exception while processing command: %s', e)
        sys.exit(0)
    elif len(sys.argv) != 2:
        usage()

    daemonSvr = UDSActorSvc()
    if len(sys.argv) == 2:
        # Daemon mode...
        if sys.argv[1] in ('start', 'start-foreground'):
            daemonSvr.run()  # execute in foreground
        else:
            usage()
        sys.exit(0)
    else:
        usage()
