#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2021 Virtual Cable S.L.U.
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
import os
import pwd
import sys
import argparse
import multiprocessing
import signal
import socket
import logging
import typing

import curio
import psutil
import setproctitle

from uds_tunnel import config
from uds_tunnel import proxy
from uds_tunnel import consts
from uds_tunnel import message
from uds_tunnel import stats

if typing.TYPE_CHECKING:
    from multiprocessing.connection import Connection
    from multiprocessing.managers import Namespace

BACKLOG = 100

logger = logging.getLogger(__name__)

do_stop = False


def stop_signal(signum, frame):
    global do_stop
    do_stop = True
    logger.debug('SIGNAL %s, frame: %s', signum, frame)


def setup_log(cfg: config.ConfigurationType) -> None:
    from logging.handlers import RotatingFileHandler

    # Update logging if needed
    if cfg.log_file:
        fileh = RotatingFileHandler(
            filename=cfg.log_file,
            mode='a',
            maxBytes=cfg.log_size,
            backupCount=cfg.log_number,
        )
        formatter = logging.Formatter(consts.LOGFORMAT)
        fileh.setFormatter(formatter)
        log = logging.getLogger()
        log.setLevel(cfg.log_level)
        # for hdlr in log.handlers[:]:
        #     log.removeHandler(hdlr)
        log.addHandler(fileh)
    else:
        # Setup basic logging
        log = logging.getLogger()
        log.setLevel(cfg.log_level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(cfg.log_level)
        formatter = logging.Formatter(
            '%(levelname)s - %(message)s'
        )  # Basic log format, nice for syslog
        handler.setFormatter(formatter)
        log.addHandler(handler)


async def tunnel_proc_async(
    pipe: 'Connection', cfg: config.ConfigurationType, ns: 'Namespace'
) -> None:
    def get_socket(pipe: 'Connection') -> typing.Tuple[typing.Optional[socket.SocketType], typing.Any]:
        try:
            while True:
                msg: message.Message = pipe.recv()
                if msg.command == message.Command.TUNNEL and msg.connection:
                    return msg.connection
                # Process other messages, and retry
        except Exception:
            logger.exception('Receiving data from parent process')
            return None, None

    async def run_server(
        pipe: 'Connection', cfg: config.ConfigurationType, group: curio.TaskGroup
    ) -> None:
        # Instantiate a proxy redirector for this process (we only need one per process!!)
        tunneler = proxy.Proxy(cfg, ns)

        # Generate SSL context
        context = curio.ssl.SSLContext(curio.ssl.PROTOCOL_TLS_SERVER)  # type: ignore
        context.load_cert_chain(cfg.ssl_certificate, cfg.ssl_certificate_key)

        if cfg.ssl_ciphers:
            context.set_ciphers(cfg.ssl_ciphers)

        if cfg.ssl_dhparam:
            context.load_dh_params(cfg.ssl_dhparam)

        while True:
            address = ('', '')
            try:
                sock, address = await curio.run_in_thread(get_socket, pipe)
                if not sock:
                    break
                logger.debug(
                    f'CONNECTION from {address!r} (pid: {os.getpid()})'
                )
                sock = await context.wrap_socket(
                    curio.io.Socket(sock), server_side=True  # type: ignore
                )
                await group.spawn(tunneler, sock, address)
                del sock
            except Exception:
                logger.error('NEGOTIATION ERROR from %s', address[0])

    async with curio.TaskGroup() as tg:
        await tg.spawn(run_server, pipe, cfg, tg)
        # Reap all of the children tasks as they complete
        async for task in tg:
            logger.debug(f'REMOVING async task {task!r}')
            task.joined = True
            del task


def tunnel_main():
    cfg = config.read()

    # Try to bind to port as running user
    # Wait for socket incoming connections and spread them
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(3.0)  # So we can check for stop from time to time
    # We will not reuse port, we only want a UDS tunnel server running on a port
    # but this may change on future...
    # try:
    #     sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, True)
    # except (AttributeError, OSError) as e:
    #     logger.warning('socket.REUSEPORT not available')
    try:
        sock.bind((cfg.listen_address, cfg.listen_port))
        sock.listen(BACKLOG)

        # If running as root, and requested drop privileges after port bind
        if os.getuid() == 0 and cfg.user:
            logger.debug('Changing to  user %s', cfg.user)
            pwu = pwd.getpwnam(cfg.user)
            # os.setgid(pwu.pw_gid)
            os.setuid(pwu.pw_uid)

        setup_log(cfg)

        logger.info('Starting tunnel server on %s:%s', cfg.listen_address, cfg.listen_port)
        setproctitle.setproctitle(f'UDSTunnel {cfg.listen_address}:{cfg.listen_port}')

        # Create pid file
        if cfg.pidfile:
            with open(cfg.pidfile, mode='w') as f:
                f.write(str(os.getpid()))

    except Exception as e:
        sys.stderr.write(f'Tunnel startup error: {e}\n')
        logger.error('MAIN: %s', e)
        return


    # Setup signal handlers
    signal.signal(signal.SIGINT, stop_signal)
    signal.signal(signal.SIGTERM, stop_signal)

    # Creates as many processes and pipes as required
    child: typing.List[
        typing.Tuple['Connection', multiprocessing.Process, psutil.Process]
    ] = []

    stats_collector = stats.GlobalStats()

    def add_child_pid():
        own_conn, child_conn = multiprocessing.Pipe()
        task = multiprocessing.Process(
            target=curio.run,
            args=(tunnel_proc_async, child_conn, cfg, stats_collector.ns),
        )
        task.start()
        logger.debug('ADD CHILD PID: %s', task.pid)
        child.append((own_conn, task, psutil.Process(task.pid)))

    for i in range(cfg.workers):
        add_child_pid()

    def best_child() -> 'Connection':
        best: typing.Tuple[float, 'Connection'] = (1000.0, child[0][0])
        missingProcesses = []
        for i, c in enumerate(child):
            try:
                if c[2].status() == 'zombie': # Bad kill!!
                    raise psutil.ZombieProcess(c[2].pid)
                percent = c[2].cpu_percent()
            except (psutil.ZombieProcess, psutil.NoSuchProcess) as e:
                # Process is missing...
                logger.warning('Missing process found: %s', e.pid)
                try:
                    c[0].close()  # Close pipe to missing process
                except Exception:
                    logger.debug('Could not close handle for %s', e.pid)
                try:
                    c[1].kill()
                    c[1].close()
                except Exception:
                    logger.debug('Could not close process %s', e.pid)

                missingProcesses.append(i)
                continue
                
            logger.debug('PID %s has %s', c[2].pid, percent)

            if percent < best[0]:
                best = (percent, c[0])

        if missingProcesses:
            logger.debug('Regenerating missing processes: %s', len(missingProcesses))
            # Regenerate childs and recreate new proceeses to process requests...
            tmpChilds = [child[i] for i in range(len(child)) if i not in missingProcesses]
            child[:] = tmpChilds
            # Now add new children
            for i in range(len(missingProcesses)):
                add_child_pid()

        return best[1]

    try:
        while not do_stop:
            try:
                client, addr = sock.accept()
                # Select BEST process for sending this new connection
                best_child().send(
                    message.Message(message.Command.TUNNEL, (client, addr))
                )
                del client  # Ensure socket is controlled on child process
            except socket.timeout:
                pass  # Continue and retry
            except Exception as e:
                logger.error('LOOP: %s', e)
    except Exception as e:
        sys.stderr.write(f'Error: {e}\n')
        logger.error('MAIN: %s', e)

    if sock:
        sock.close()

    # Try to stop running childs
    for i in child:
        try:
            i[2].kill()
        except Exception as e:
            logger.info('KILLING child %s: %s', i[2], e)

    try:
        if cfg.pidfile:
            os.unlink(cfg.pidfile)
    except Exception:
        pass

    logger.info('FINISHED')


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '-t', '--tunnel', help='Starts the tunnel server', action='store_true'
    )
    group.add_argument(
        '-s',
        '--stats',
        help='get current global stats from RUNNING tunnel',
        action='store_true',
    )
    group.add_argument(
        '-d',
        '--detailed-stats',
        help='get current detailed stats from RUNNING tunnel',
        action='store_true',
    )
    args = parser.parse_args()

    if args.tunnel:
        tunnel_main()
    elif args.detailed_stats:
        curio.run(stats.getServerStats, True)
    elif args.stats:
        curio.run(stats.getServerStats, False)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()