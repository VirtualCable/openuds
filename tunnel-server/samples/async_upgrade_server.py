#!/usr/bin/env python3

import asyncio
import ssl
import logging
import socket
import typing

if typing.TYPE_CHECKING:
    import asyncio.transports

logger = logging.getLogger(__name__)

BACKLOG = 100

STATE_UNINITIALIZED = 0
STATE_COMMAND = 1
STATE_PROXY = 2

COMMAND_LENGTH = 4
TICKET_LENGTH = 48

# Protocol
class TunnelProtocol(asyncio.Protocol):
    # future to mark eof
    finished: asyncio.Future
    transport: 'asyncio.transports.Transport'
    other_side: 'TunnelProtocol'
    state: int
    cmd: bytes

    def __init__(self, other_side: typing.Optional['TunnelProtocol'] = None) -> None:
        # If no other side is given, we are the server part
        super().__init__()
        self.state = STATE_UNINITIALIZED
        self.other_side = (
            other_side if other_side else self
        )  # No other side, self is just a placeholder
        # transport is undefined until conne
        self.finished = asyncio.Future()
        self.cmd = b''

    def connection_made(self, transport: 'asyncio.transports.BaseTransport') -> None:
        logger.debug('Connection made: %s', transport.get_extra_info('peername'))
        # Update state based on if we are the client or server
        self.state = STATE_COMMAND if self.other_side is self else STATE_PROXY

        # We know for sure that the transport is a Transport.
        self.transport = typing.cast('asyncio.transports.Transport', transport)
        self.cmd = b''

    def process_command(self, data: bytes) -> None:
        self.cmd += data
        if len(self.cmd) >= COMMAND_LENGTH:
            logger.debug('Command received: %s', self.cmd)
            if self.cmd[:4] == b'OPEN':
                # Open Command has the ticket behind it
                if len(self.cmd) < TICKET_LENGTH + COMMAND_LENGTH:
                    return  # Wait for more data
                # log the ticket
                logger.debug('Ticket received: %s', self.cmd[4:4+TICKET_LENGTH])
                loop = asyncio.get_event_loop()

                async def open_other_side() -> None:
                    try:
                        (transport, protocol) = await loop.create_connection(
                            lambda: TunnelProtocol(self), 'www.google.com', 80
                        )
                        self.other_side = typing.cast('TunnelProtocol', protocol)
                        self.other_side.transport.write(
                            b'GET / HTTP/1.0\r\nHost: www.google.com\r\n\r\n'
                        )
                    except Exception as e:
                        logger.error('Error opening connection: %s', e)
                        # Send error to client
                        self.transport.write(b'ERR')
                        self.transport.close()
                loop.create_task(open_other_side())
                self.state = STATE_PROXY

    def process_proxy(self, data: bytes) -> None:
        logger.debug('Processing proxy: %s', len(data))
        self.other_side.transport.write(data)

    def data_received(self, data: bytes):
        logger.debug('Data received: %s', len(data))
        if self.state == STATE_COMMAND:
            self.process_command(data)
        elif self.state == STATE_PROXY:
            self.process_proxy(data)
        else:
            logger.error('Invalid state reached!')

    def connection_lost(self, exc: typing.Optional[Exception]) -> None:
        logger.debug('Connection closed : %s', exc)
        self.finished.set_result(True)
        if self.other_side is not self:
            self.other_side.transport.close()


async def main():
    # Init logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain('tests/testing.pem', 'tests/testing.key')

    # Create a server

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(444.0)  # So we can check for stop from time to time

    sock.bind(('0.0.0.0', 7777))
    sock.listen(BACKLOG)

    loop = asyncio.get_running_loop()

    # Accepts connections
    client, addr = sock.accept()
    logger.debug('Accepted connection')
    data = client.recv(4)
    print(data)
    # Upgrade connection to SSL, and use asyncio to handle the rest
    transport: 'asyncio.transports.Transport'
    protocol: TunnelProtocol
    (transport, protocol) = await loop.connect_accepted_socket(  # type: ignore
        lambda: TunnelProtocol(), client, ssl=context
    )

    await protocol.finished


if __name__ == '__main__':
    asyncio.run(main())
