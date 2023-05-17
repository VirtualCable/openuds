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
import json
import typing

import requests
from udsactor import tools, types
from udsactor.log import logger

# For avoid proxy on localhost connections
NO_PROXY: typing.Dict[str, str] = {
    'http': '',
    'https': '',
}


class UDSActorClientPool(metaclass=tools.Singleton):
    _clients: typing.List[types.ClientInfo]

    def __init__(self) -> None:
        self._clients = []

    def _post(
        self,
        session_id: typing.Optional[str],
        method: str,
        data: typing.MutableMapping[str, str],
        timeout: int = 2,
    ) -> typing.List[
        typing.Tuple[types.ClientInfo, typing.Optional[requests.Response]]
    ]:
        result: typing.List[
            typing.Tuple[types.ClientInfo, typing.Optional[requests.Response]]
        ] = []
        for client in self._clients:
            # Skip if session id is provided but does not match
            if session_id and client.session_id != session_id:
                continue
            clientUrl = client.url
            try:
                result.append(
                    (
                        client,
                        requests.post(
                            clientUrl + '/' + method,
                            data=json.dumps(data),
                            verify=False,
                            timeout=timeout,
                            proxies=NO_PROXY,  # type: ignore
                        ),
                    )
                )
            except Exception as e:
                logger.info(
                    'Could not connect with client %s: %s. ',
                    e,
                    clientUrl,
                )
                result.append((client, None))

        return result

    @property
    def clients(self) -> typing.List[types.ClientInfo]:
        return self._clients

    def register(self, client_url: str) -> None:
        # Remove first if exists, to avoid duplicates
        self.unregister(client_url)
        # And add it again
        self._clients.append(types.ClientInfo(client_url, ''))

    def set_session_id(self, client_url: str, session_id: typing.Optional[str]) -> None:
        """Set the session id for a client

        Args:
            clientUrl (str): _description_
            session_id (str): _description_
        """
        for client in self._clients:
            if client.url == client_url:
                # remove existing client from list, create a new one and insert it
                self._clients.remove(client)
                self._clients.append(types.ClientInfo(client_url, session_id or ''))
                break

    def unregister(self, client_url: str) -> None:
        # remove client url from array if found
        for i, client in enumerate(self._clients):
            if client.url == client_url:
                self._clients.pop(i)
                return

    def executeScript(self, session_id: typing.Optional[str], script: str) -> None:
        self._post(session_id, 'script', {'script': script}, timeout=30)

    def logout(self, session_id: typing.Optional[str]) -> None:
        self._post(session_id, 'logout', {})

    def message(self, session_id: typing.Optional[str], message: str) -> None:
        self._post(session_id, 'message', {'message': message})

    def lost_clients(
        self,
        session_id: typing.Optional[str] = None,
    ) -> typing.Iterable[types.ClientInfo]:  # returns the list of "lost" clients
        # Port ping to every client
        for i in self._post(session_id, 'ping', {}, timeout=1):
            if i[1] is None:
                yield i[0]

    def screenshot(
        self, session_id: typing.Optional[str]
    ) -> typing.Optional[str]:  # Screenshot are returned as base64
        for client, r in self._post(session_id, 'screenshot', {}, timeout=3):
            if not r:
                continue  # Missing client, so we ignore it
            try:
                return r.json()['result']
            except Exception:
                pass
        return None
