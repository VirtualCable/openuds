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
import typing

from .. import tools
from . import handler

from ..log import logger

if typing.TYPE_CHECKING:
    from ..service import CommonService


class PublicProvider(handler.Handler):
    def post_logout(self) -> typing.Any:
        logger.debug('Sending LOGOFF to clients')
        self._service._clientsPool.logout()  # pylint: disable=protected-access
        return 'ok'

    # Alias
    post_logoff = post_logout

    def post_message(self) -> typing.Any:
        logger.debug('Sending MESSAGE to clients')
        if 'message' not in self._params:
            raise Exception('Invalid message parameters')
        self._service._clientsPool.message(
            self._params['message']
        )  # pylint: disable=protected-access
        return 'ok'

    def post_script(self) -> typing.Any:
        logger.debug('Received script: {}'.format(self._params))
        if 'script' not in self._params:
            raise Exception('Invalid script parameters')
        if self._params.get('user', False):
            logger.debug('Sending SCRIPT to client')
            self._service._clientsPool.executeScript(
                self._params['script']
            )  # pylint: disable=protected-access
        else:
            # Execute script at server space, that is, here
            # as a parallel thread
            th = tools.ScriptExecutorThread(self._params['script'])
            th.start()
        return 'ok'

    def post_preConnect(self) -> typing.Any:
        logger.debug('Received Pre connection')
        if 'user' not in self._params or 'protocol' not in self._params:
            raise Exception('Invalid preConnect parameters')
        return self._service.preConnect(
            self._params['user'],
            self._params['protocol'],
            self._params.get('ip', 'unknown'),
            self._params.get('hostname', 'unknown'),
            self._params.get('udsuser', 'unknown'),
        )

    def get_information(self) -> typing.Any:
        # Return something useful? :)
        return 'UDS Actor Secure Server'

    def get_screenshot(self) -> typing.Any:
        return (
            self._service._clientsPool.screenshot()
        )  # pylint: disable=protected-access

    def get_uuid(self) -> typing.Any:
        if self._service.isManaged():
            return self._service._cfg.own_token  # pylint: disable=protected-access
        return ''
