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
import asyncio
import typing
import logging
import socket

import aiohttp

from . import consts, config, stats, tunnel_client


logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from . import proxy


# Protocol
class TunnelProtocol(asyncio.Protocol):
    # owner Proxy class
    owner: 'proxy.Proxy'

    # Transport and client
    transport: 'asyncio.transports.Transport'
    client: typing.Optional['tunnel_client.TunnelClientProtocol']

    # Current state, could be:
    # - do_command: Waiting for command
    # - do_proxy: Proxying data
    runner: typing.Any  # In fact, typing.Callable[[bytes], None], but mypy complains on checking variables that are callables on classes
    # Command buffer
    cmd: bytes

    # Ticket
    notify_ticket: bytes  # Only exists when we have created the client connection

    # source of connection
    source: typing.Tuple[str, int]
    # and destination
    destination: typing.Tuple[str, int]
    # tls version used
    tls_version: str
    # cipher used
    tls_cipher: str

    # Counters & stats related
    stats_manager: stats.StatsManager

    # If there is a timeout task running
    timeout_task: typing.Optional[asyncio.Task] = None

    def __init__(self, owner: 'proxy.Proxy') -> None:
        # If no other side is given, we are the server part
        super().__init__()
        # transport is undefined until connection_made is called
        self.cmd = b''
        self.notify_ticket = b''
        self.owner = owner
        self.source = ('', 0)
        self.destination = ('', 0)
        self.tls_version = ''
        self.tls_cipher = ''

        # If other_side is given, we are the client part (that is, the tunnel from us to remote machine)
        # In this case, only do_proxy is used
        self.client = None
        self.stats_manager = stats.StatsManager(owner.ns)
        # We start processing command
        # After command, we can process stats or do_proxy, that is the "normal" operation
        self.runner = self.do_command

    def process_open(self) -> None:
        # Open Command has the ticket behind it

        if len(self.cmd) < consts.TICKET_LENGTH + consts.COMMAND_LENGTH:
            return  # Wait for more data to complete OPEN command

        # Clean timeout now, we have received all data
        self.clean_timeout()

        # Ticket received, now process it with UDS
        ticket = self.cmd[consts.COMMAND_LENGTH :]

        # Stop reading from this side until open is done
        self.transport.pause_reading()

        # clean up the command
        self.cmd = b''

        loop = asyncio.get_running_loop()

        async def open_client() -> None:
            try:
                result = await TunnelProtocol.get_ticket_from_uds(self.owner.cfg, ticket, self.source)
            except Exception as e:
                logger.error('ERROR %s', e.args[0] if e.args else e)
                self.transport.write(consts.RESPONSE_ERROR_TICKET)
                self.transport.close()  # And force close
                return

            # store for future use
            self.destination = (result['host'], int(result['port']))
            self.notify_ticket = result['notify'].encode()

            logger.info(
                'OPEN TUNNEL FROM %s to %s',
                self.pretty_source(),
                self.pretty_destination(),
            )

            try:
                family = (
                    socket.AF_INET6
                    if ':' in self.destination[0] or (self.owner.cfg.ipv6 and '.' not in self.destination[0])
                    else socket.AF_INET
                )
                (_, self.client) = await loop.create_connection(
                    lambda: tunnel_client.TunnelClientProtocol(self),
                    self.destination[0],
                    self.destination[1],
                    family=family,
                )

                # Resume reading
                self.transport.resume_reading()
                # send OK to client
                self.transport.write(b'OK')
                self.stats_manager.increment_connections()  # Increment connections counters
            except Exception as e:
                logger.error('CONNECTION FAILED: %s', e)
                self.close_connection()

        # add open other side to the loop
        loop.create_task(open_client())
        # From now, proxy connection
        self.runner = self.do_proxy

    def process_stats(self, full: bool) -> None:  # pylint: disable=unused-argument
        # if pasword is not already received, wait for it
        if len(self.cmd) < consts.PASSWORD_LENGTH + consts.COMMAND_LENGTH:
            return

        # Clean timeout now, we have received all data
        self.clean_timeout()
        logger.info('COMMAND: %s', self.cmd[: consts.COMMAND_LENGTH].decode())

        # Check valid source ip
        if self.transport.get_extra_info('peername')[0] not in self.owner.cfg.allow:
            # Invalid source
            self.transport.write(consts.RESPONSE_FORBIDDEN)
            return

        # Check password, max length is consts.PASSWORD_LENGTH
        passwd = self.cmd[consts.COMMAND_LENGTH : consts.PASSWORD_LENGTH + consts.COMMAND_LENGTH]

        # Clean up the command, only keep base part
        self.cmd = self.cmd[:4]

        if passwd.decode(errors='ignore') != self.owner.cfg.secret:
            # Invalid password
            self.transport.write(consts.RESPONSE_FORBIDDEN)
            return

        data = stats.GlobalStats.get_stats(self.owner.ns)

        for v in data:
            logger.debug('SENDING %s', v)
            self.transport.write(v.encode() + b'\n')

    async def timeout(self, wait: float) -> None:
        """Timeout can only occur while waiting for a command (or OPEN command ticket)."""
        try:
            await asyncio.sleep(wait)
            logger.error('TIMEOUT FROM %s', self.pretty_source())
            try:
                self.transport.write(consts.RESPONSE_ERROR_TIMEOUT)
            except Exception:  # nosec: Transport not available, ignore
                pass
            self.close_connection()
        except asyncio.CancelledError:
            pass

    def set_timeout(self, wait: float) -> None:
        """Set a timeout for this connection.
        If reached, the connection will be closed.

        Args:
            wait (int): Timeout in seconds

        """
        if self.timeout_task:
            self.timeout_task.cancel()
        self.timeout_task = asyncio.create_task(self.timeout(wait))

    def clean_timeout(self) -> None:
        """Clean the timeout task if any."""
        if self.timeout_task:
            self.timeout_task.cancel()
            self.timeout_task = None

    def do_command(self, data: bytes) -> None:
        if self.cmd == b'':
            logger.info('CONNECT FROM %s (%s/%s)', self.pretty_source(), self.tls_version, self.tls_cipher)

        # We have at most self.owner.cfg.command_timeout seconds to receive the command and the ticket if needed
        self.cmd += data

        if len(self.cmd) >= consts.COMMAND_LENGTH:
            command = self.cmd[: consts.COMMAND_LENGTH]
            try:
                if command == consts.COMMAND_OPEN:
                    self.process_open()
                    return
                if command == consts.COMMAND_TEST:
                    self.clean_timeout()  # Stop timeout
                    logger.info('COMMAND: TEST')
                    self.transport.write(consts.RESPONSE_OK)
                    self.close_connection()
                    return
                if command in (consts.COMMAND_STAT, consts.COMMAND_INFO):
                    # This is an stats requests
                    try:
                        self.process_stats(full=command == consts.COMMAND_STAT)
                    except Exception as e:
                        logger.error('ERROR processing stats: %s', e.args[0] if e.args else e)
                    self.close_connection()
                    return
                raise Exception('Invalid command')
            except Exception:
                logger.error('ERROR from %s', self.pretty_source())
                self.transport.write(consts.RESPONSE_ERROR_COMMAND)
                self.close_connection()
                return

        # if not enough data to process command, wait for more

    def do_proxy(self, data: bytes) -> None:
        self.stats_manager.as_sent_counter.add(len(data))
        # do_proxy will only be called if other_side is set to the other side of the tunnel, no None is possible
        typing.cast('tunnel_client.TunnelClientProtocol', self.client).send(data)

    def send(self, data: bytes) -> None:
        self.stats_manager.as_recv_counter.add(len(data))
        self.transport.write(data)

    def close_connection(self):
        try:
            self.clean_timeout()  # If a timeout is set, clean it
            if not self.transport.is_closing():  # Attribute may alreade not be set
                self.transport.close()
        except AttributeError:  # not initialized transport, fine...
            pass
        except Exception as e:   # nosec: best effort
            logger.error('ERROR closing connection: %s', e)

    def notify_end(self):
        if self.notify_ticket:
            logger.info(
                'TERMINATED %s to %s, s:%s, r:%s, t:%s',
                self.pretty_source(),
                self.pretty_destination(),
                self.stats_manager.sent,
                self.stats_manager.recv,
                int(self.stats_manager.current_time - self.stats_manager.start_time),
            )
            # Notify end to uds, using a task becase we are not an async function
            asyncio.get_event_loop().create_task(
                TunnelProtocol.notify_end_to_uds(self.owner.cfg, self.notify_ticket, self.stats_manager)
            )
            self.notify_ticket = b''  # Clean up so no more notifications
        else:
            logger.info('TERMINATED %s', self.pretty_source())

        self.stats_manager.close()
        self.owner.finished.set()

    def connection_made(self, transport: 'asyncio.transports.BaseTransport') -> None:
        # We know for sure that the transport is a Transport.

        # Set starting timeout task, se we dont get hunged on connections without data (or insufficient data)
        self.set_timeout(self.owner.cfg.command_timeout)

        self.transport = typing.cast('asyncio.transports.Transport', transport)
        # Get source
        self.source = self.transport.get_extra_info('peername')
        logger.debug('Connection made: %s', self.source)

        # Try to get the cipher used to show it in the logs
        try:
            self.tls_cipher, self.tls_version = transport.get_extra_info('cipher')[:2]
        except Exception:  # nosec, ingore if not TLS (but should not happen)
            self.tls_cipher, self.tls_version = 'None', 'None'

        self.cmd = b''

    def data_received(self, data: bytes):
        self.runner(data)  # send data to current runner (command or proxy)

    def connection_lost(self, exc: typing.Optional[Exception]) -> None:
        # Ensure close other side if not server_side
        if self.client:
            self.client.close_connection()

        self.notify_end()

    # *****************
    # *    Helpers    *
    # *****************
    @staticmethod
    def pretty_address(address: typing.Tuple[str, int]) -> str:
        if ':' in address[0]:
            return '[' + address[0] + ']:' + str(address[1])
        return address[0] + ':' + str(address[1])

    # source address, pretty format
    def pretty_source(self) -> str:
        return TunnelProtocol.pretty_address(self.source)

    def pretty_destination(self) -> str:
        return TunnelProtocol.pretty_address(self.destination)

    @staticmethod
    async def _read_from_uds(
        cfg: config.ConfigurationType,
        ticket: bytes,
        msg: str,
        queryParams: typing.Optional[typing.Mapping[str, str]] = None,
    ) -> typing.MutableMapping[str, typing.Any]:
        try:
            url = cfg.uds_server + '/' + ticket.decode() + '/' + msg + '/' + cfg.uds_token
            if queryParams:
                url += '?' + '&'.join([f'{key}={value}' for key, value in queryParams.items()])
            # Set options
            options: typing.Dict[str, typing.Any] = {'timeout': cfg.uds_timeout}
            if cfg.uds_verify_ssl is False:
                options['ssl'] = False
            # Requests url with aiohttp

            async with aiohttp.ClientSession(headers={'User-Agent': consts.USER_AGENT}) as session:
                async with session.get(url, **options) as r:
                    if not r.ok:
                        raise Exception(await r.text())
                    return await r.json()
        except Exception as e:
            raise Exception(f'TICKET COMMS ERROR: {ticket.decode()} {msg} {e!s}') from e

    @staticmethod
    async def get_ticket_from_uds(
        cfg: config.ConfigurationType, ticket: bytes, address: typing.Tuple[str, int]
    ) -> typing.MutableMapping[str, typing.Any]:
        # Check ticket using re
        if consts.TICKET_REGEX.match(ticket.decode(errors='replace')) is None:
            raise ValueError(f'TICKET INVALID ({ticket.decode(errors="replace")})')

        return await TunnelProtocol._read_from_uds(cfg, ticket, address[0])

    @staticmethod
    async def notify_end_to_uds(
        cfg: config.ConfigurationType, ticket: bytes, stats_mngr: stats.StatsManager
    ) -> None:
        await TunnelProtocol._read_from_uds(
            cfg,
            ticket,
            'stop',
            {'sent': str(stats_mngr.sent), 'recv': str(stats_mngr.recv)},
        )
