import typing
import logging

import requests

logger = logging.getLogger(__name__)


class Chat(typing.NamedTuple):
    id: int
    type: str
    first_name: str


class From(typing.NamedTuple):
    id: int
    is_bot: bool
    first_name: str
    last_name: typing.Optional[str]
    username: str


class Message(typing.NamedTuple):
    chat: Chat
    from_: From
    date: int
    text: str

    @staticmethod
    def fromDict(data: typing.Mapping[str, typing.Any]) -> 'Message':
        print(data)
        return Message(
            Chat(
                id=data['chat']['id'],
                type=data['chat']['type'],
                first_name=data['chat']['first_name'],
            ),
            From(
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
    reqTimeout: int
    lastOffset: int

    def __init__(self, token: str, last_offset: int = 0) -> None:
        self.token = token
        self.reqTimeout = 3 * 2 + 1
        self.lastOffset = last_offset

    def request(
        self,
        method,
        params: typing.Optional[typing.Dict[str, typing.Any]] = None,
        *,
        stream: bool = False,
    ) -> typing.Dict[str, typing.Any]:
        params = params or {}
        params['token'] = self.token
        kwargs: typing.Dict[str, typing.Any] = {'params': params}
        if stream:
            kwargs['stream'] = True
        # If params has a timeout, use the max of that and our own timeout
        timeout = max(params.get('timeout', 0), self.reqTimeout)
        response = requests.get(
            f'https://api.telegram.org/bot{self.token}/{method}',
            timeout=timeout,
            **kwargs,
        )
        return response.json()

    def sendMessage(self, chat_id: int, text: str) -> typing.Dict[str, typing.Any]:
        return self.request('sendMessage', {'chat_id': chat_id, 'text': text})

    def getUpdates(self, offset: int = 0, timeout: int = 0) -> typing.Iterable[Message]:
        self.lastOffset = offset or self.lastOffset
        res = self.request('getUpdates', {'offset': self.lastOffset, 'timeout': timeout}, stream=True)
        if res['ok'] and res['result']:  # if ok and there are results
            # Update the offset
            self.lastOffset = res['result'][-1]['update_id'] + 1
            for update in res['result']:
                yield Message.fromDict(update['message'])
