#!/usr/bin/env python3
# -*- coding=utf-8 -*-

import sys
import asyncio
import logging
import typing

if typing.TYPE_CHECKING:
    from asyncio.streams import StreamReader, StreamWriter


async def tcp_echo_client(message):
    reader, writer = await asyncio.open_connection('127.0.0.1', 7777)

    print(f'Send: {message!r}')
    writer.write(message.encode())
    await writer.drain()

    data = await reader.read(100)
    print(f'Received: {data.decode()!r}')

    print('Close the connection')
    writer.close()
    await writer.wait_closed()


asyncio.run(tcp_echo_client('Hello World!'))
