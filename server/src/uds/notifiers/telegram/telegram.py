#
# Copyright (c) 2024-2025 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice,
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distributiopenStack.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permissiopenStack.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import dataclasses
import typing
import collections.abc
import logging

import requests

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class Chat:
    id: int
    type: str
    first_name: str


@dataclasses.dataclass
class From:
    id: int
    is_bot: bool
    first_name: str
    last_name: typing.Optional[str]
    username: str


@dataclasses.dataclass
class Message:
    chat: Chat
    src: From
    date: int
    text: str

    @staticmethod
    def from_dict(data: collections.abc.Mapping[str, typing.Any]) -> 'Message':
        return Message(
            chat=Chat(
                id=data['chat']['id'],
                type=data['chat']['type'],
                first_name=data['chat']['first_name'],
            ),
            src=From(
                id=data['from']['id'],
                is_bot=data['from']['is_bot'],
                first_name=data['from']['first_name'],
                last_name=data['from'].get('last_name'),
                username=data['from']['username'],
            ),
            date=data['date'],
            text=data['text'],
        )


class Telegram:
    token: str
    req_timeout: int
    last_offset: int

    def __init__(self, token: str, last_offset: int = 0) -> None:
        self.token = token
        self.req_timeout = 3 * 2 + 1
        self.last_offset = last_offset

    def request(
        self,
        method: str,
        params: typing.Optional[dict[str, typing.Any]] = None,
        *,
        stream: bool = False,
    ) -> dict[str, typing.Any]:
        params = params or {}
        params['token'] = self.token
        kwargs: dict[str, typing.Any] = {'params': params}
        if stream:
            kwargs['stream'] = True
        # If params has a timeout, use the max of that and our own timeout
        timeout = max(params.get('timeout', 0), self.req_timeout)
        response = requests.get(
            f'https://api.telegram.org/bot{self.token}/{method}',
            timeout=timeout,
            **kwargs,
        )
        return response.json()

    def send_message(self, chat_id: int, text: str) -> dict[str, typing.Any]:
        return self.request('sendMessage', {'chat_id': chat_id, 'text': text})

    def get_updates(self, offset: int = 0, timeout: int = 0) -> collections.abc.Iterable[Message]:
        self.last_offset = offset or self.last_offset
        res = self.request('getUpdates', {'offset': self.last_offset, 'timeout': timeout}, stream=True)
        if res['ok'] and res['result']:  # if ok and there are results
            # Update the offset
            self.last_offset = res['result'][-1]['update_id'] + 1
            update: dict[str, typing.Any]
            for update in res['result']:
                message = update.get('message', update.get('edited_message', None))
                if message:
                    try:
                        yield Message.from_dict(message)
                    except Exception as e:
                        logger.warning('Skiped unknown telegram message: %s', e)
