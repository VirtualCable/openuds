import asyncio
import typing
import logging


import requests

from . import consts
from . import config
from . import stats

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from . import proxy


# Protocol
class TunnelProtocol(asyncio.Protocol):
    # future to mark eof
    finished: asyncio.Future
    # Transport and other side of tunnel
    transport: 'asyncio.transports.Transport'
    other_side: 'TunnelProtocol'
    # Current state
    runner: typing.Any  # In fact, typing.Callable[[bytes], None], but mypy complains on its check
    # Command buffer
    cmd: bytes
    # Ticket
    notify_ticket: bytes
    # owner Proxy class
    owner: 'proxy.Proxy'
    # source of connection
    source: typing.Tuple[str, int]
    destination: typing.Tuple[str, int]
    # Counters & stats related
    stats_manager: stats.Stats
    # counter
    counter: stats.StatsSingleCounter

    def __init__(
        self, owner: 'proxy.Proxy', other_side: typing.Optional['TunnelProtocol'] = None
    ) -> None:
        # If no other side is given, we are the server part
        super().__init__()
        if other_side:
            self.other_side = other_side
            self.stats_manager = other_side.stats_manager
            self.counter = self.stats_manager.as_recv_counter()
            self.runner = self.do_proxy
        else:
            self.other_side = self
            self.stats_manager = stats.Stats(owner.ns)
            self.counter = self.stats_manager.as_sent_counter()
            self.runner = self.do_command

        # transport is undefined until connection_made is called
        self.finished = asyncio.Future()
        self.cmd = b''
        self.notify_ticket = b''
        self.owner = owner
        self.source = ('', 0)
        self.destination = ('', 0)

    def process_open(self):
        # Open Command has the ticket behind it
        
        if len(self.cmd) < consts.TICKET_LENGTH + consts.COMMAND_LENGTH:
            return  # Wait for more data to complete OPEN command

        # Ticket received, now process it with UDS
        ticket = self.cmd[consts.COMMAND_LENGTH :]

        # Stop reading from this side until open is done
        self.transport.pause_reading()

        # clean up the command
        self.cmd = b''

        loop = asyncio.get_event_loop()

        async def open_other_side() -> None:
            try:
                result = await TunnelProtocol.getFromUds(
                    self.owner.cfg, ticket, self.source
                )
            except Exception as e:
                logger.error('ERROR %s', e.args[0] if e.args else e)
                self.transport.write(b'ERROR_TICKET')
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
                (_, protocol) = await loop.create_connection(
                    lambda: TunnelProtocol(self.owner, self),
                    self.destination[0],
                    self.destination[1],
                )
                self.other_side = typing.cast('TunnelProtocol', protocol)

                # Resume reading
                self.transport.resume_reading()
                # send OK to client
                self.transport.write(b'OK')
            except Exception as e:
                logger.error('Error opening connection: %s', e)
                self.close_connection()

        loop.create_task(open_other_side())
        # From now, proxy connection
        self.runner = self.do_proxy

    def process_stats(self, full: bool) -> None:
        # if pasword is not already received, wait for it
        if len(self.cmd) < consts.PASSWORD_LENGTH + consts.COMMAND_LENGTH:
            return

        try:
            logger.info('COMMAND: %s', self.cmd[: consts.COMMAND_LENGTH].decode())

            # Check valid source ip
            if self.transport.get_extra_info('peername')[0] not in self.owner.cfg.allow:
                # Invalid source
                self.transport.write(b'FORBIDDEN')
                return

            # Check password
            passwd = self.cmd[consts.COMMAND_LENGTH :]

            # Clean up the command, only keep base part
            self.cmd = self.cmd[:4]

            if passwd.decode(errors='ignore') != self.owner.cfg.secret:
                # Invalid password
                self.transport.write(b'FORBIDDEN')
                return

            data = stats.GlobalStats.get_stats(self.owner.ns)

            for v in data:
                logger.debug('SENDING %s', v)
                self.transport.write(v.encode() + b'\n')

            logger.info('TERMINATED %s', self.pretty_source())
        finally:
            self.close_connection()

    def do_command(self, data: bytes) -> None:
        self.cmd += data
        if len(self.cmd) >= consts.COMMAND_LENGTH:
            logger.info('CONNECT FROM %s', self.pretty_source())

            command = self.cmd[: consts.COMMAND_LENGTH]
            try:
                if command == consts.COMMAND_OPEN:
                    self.process_open()
                elif command == consts.COMMAND_TEST:
                    logger.info('COMMAND: TEST')
                    self.transport.write(b'OK')
                    self.close_connection()
                    return
                elif command in (consts.COMMAND_STAT, consts.COMMAND_INFO):
                    # This is an stats requests
                    self.process_stats(full=command == consts.COMMAND_STAT)
                    return
                else:
                    raise Exception('Invalid command')
            except Exception:
                logger.error('ERROR from %s', self.pretty_source())
                self.transport.write(b'ERROR_COMMAND')
                self.close_connection()
                return

        # if not enough data to process command, wait for more

    def do_proxy(self, data: bytes) -> None:
        self.counter.add(len(data))
        logger.debug('Processing proxy: %s', len(data))
        self.other_side.transport.write(data)

    # inherited from asyncio.Protocol

    def connection_made(self, transport: 'asyncio.transports.BaseTransport') -> None:
        logger.debug('Connection made: %s', transport.get_extra_info('peername'))

        # We know for sure that the transport is a Transport.
        self.transport = typing.cast('asyncio.transports.Transport', transport)
        self.cmd = b''
        self.source = self.transport.get_extra_info('peername')

    def data_received(self, data: bytes):
        logger.debug('Data received: %s', len(data))
        self.runner(data)  # send data to current runner (command or proxy)

    def notifyEnd(self):
        if self.notify_ticket:
            asyncio.get_event_loop().create_task(
                TunnelProtocol.notifyEndToUds(
                    self.owner.cfg, self.notify_ticket, self.stats_manager
                )
            )
            self.notify_ticket = b''  # Clean up so no more notifications

    def connection_lost(self, exc: typing.Optional[Exception]) -> None:
        logger.debug('Connection closed : %s', exc)
        self.finished.set_result(True)
        if self.other_side is not self:
            self.other_side.transport.close()
        else:
            self.stats_manager.close()
        self.notifyEnd()

    # helpers
    # source address, pretty format
    def pretty_source(self) -> str:
        return self.source[0] + ':' + str(self.source[1])

    def pretty_destination(self) -> str:
        return self.destination[0] + ':' + str(self.destination[1])

    def close_connection(self):
        self.transport.close()
        # If destination is not set, it's a command processing (i.e. TEST or STAT)
        if self.destination[0] != '':
            logger.info(
                'TERMINATED %s to %s, s:%s, r:%s, t:%s',
                self.pretty_source(),
                self.pretty_destination(),
                self.stats_manager.sent,
                self.stats_manager.recv,
                int(self.stats_manager.end - self.stats_manager.start),
            )
            # Notify end to uds
            self.notifyEnd()
        else:
            logger.info('TERMINATED %s', self.pretty_source())

    @staticmethod
    def _getUdsUrl(
        cfg: config.ConfigurationType,
        ticket: bytes,
        msg: str,
        queryParams: typing.Optional[typing.Mapping[str, str]] = None,
    ) -> typing.MutableMapping[str, typing.Any]:
        try:
            url = (
                cfg.uds_server + '/' + ticket.decode() + '/' + msg + '/' + cfg.uds_token
            )
            if queryParams:
                url += '?' + '&'.join(
                    [f'{key}={value}' for key, value in queryParams.items()]
                )
            r = requests.get(
                url,
                headers={
                    'content-type': 'application/json',
                    'User-Agent': f'UDSTunnel/{consts.VERSION}',
                },
            )
            if not r.ok:
                raise Exception(r.content or 'Invalid Ticket (timed out)')

            return r.json()
        except Exception as e:
            raise Exception(f'TICKET COMMS ERROR: {ticket.decode()} {msg} {e!s}')

    @staticmethod
    async def getFromUds(
        cfg: config.ConfigurationType, ticket: bytes, address: typing.Tuple[str, int]
    ) -> typing.MutableMapping[str, typing.Any]:
        # Sanity checks
        if len(ticket) != consts.TICKET_LENGTH:
            raise Exception(f'TICKET INVALID (len={len(ticket)})')

        for n, i in enumerate(ticket.decode(errors='ignore')):
            if (
                (i >= 'a' and i <= 'z')
                or (i >= '0' and i <= '9')
                or (i >= 'A' and i <= 'Z')
            ):
                continue  # Correctus
            raise Exception(f'TICKET INVALID (char {i} at pos {n})')

        return await asyncio.get_event_loop().run_in_executor(
            None, TunnelProtocol._getUdsUrl, cfg, ticket, address[0]
        )

    @staticmethod
    async def notifyEndToUds(
        cfg: config.ConfigurationType, ticket: bytes, counter: stats.Stats
    ) -> None:
        await asyncio.get_event_loop().run_in_executor(
            None,
            TunnelProtocol._getUdsUrl,
            cfg,
            ticket,
            'stop',
            {'sent': str(counter.sent), 'recv': str(counter.recv)},
        )
