#!/usr/bin/env python3
# -*- coding=utf-8 -*-

from functools import WRAPPER_ASSIGNMENTS
import ssl
import asyncio
import logging
import typing

import certifi # In order to get valid ca certificates

if typing.TYPE_CHECKING:
    from asyncio.streams import StreamReader, StreamWriter


async def tcp_echo_client():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(certifi.where())

    reader, writer = await asyncio.open_connection('fake.udsenterprise.com', 7777, ssl=context)

    writer.write(b'\x5AMGB\xA5\x01\x00')
    await writer.drain()
    writer.write(b'OPEN' + b'1'*63 + b'\xA0')
    await writer.drain()

    writer.write(b'GET / HTTP/1.0\r\n\r\n')

    while True:
        data = await reader.read(1024)
        if not data:
            break
        print(f'Received: {data!r}')

    print('Close the connection')

    writer.close()
    await writer.wait_closed()


asyncio.run(tcp_echo_client())
