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

from udsactor.http import handler, clients_pool

if typing.TYPE_CHECKING:
    from udsactor.service import CommonService

class LocalProvider(handler.Handler):

    def post_login(self) -> typing.Any:
        result = self._service.login(self._params['username'], self._params['session_type'])
        # if callback_url is provided, record it in the clients pool
        if 'callback_url' in self._params and result.session_id:
            # If no session id is returned, then no login is acounted for
            clients_pool.UDSActorClientPool().set_session_id(self._params['callback_url'], result.session_id)
        return result._asdict()

    def post_logout(self) -> typing.Any:
        self._service.logout(self._params['username'], self._params['session_type'], self._params['session_id'])
        return 'ok'

    def post_ping(self) -> typing.Any:
        return 'pong'

    def post_register(self) -> typing.Any:
        self._service._clientsPool.register(self._params['callback_url'])  # pylint: disable=protected-access
        return 'ok'

    def post_unregister(self) -> typing.Any:
        self._service._clientsPool.unregister(self._params['callback_url'])  # pylint: disable=protected-access
