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
import hashlib
import multiprocessing
import configparser
import logging
import typing

from .consts import CONFIGFILE

logger = logging.getLogger(__name__)


class ConfigurationType(typing.NamedTuple):
    pidfile: str
    user: str

    log_level: str
    log_file: str
    log_size: int
    log_number: int

    listen_address: str
    listen_port: int
    listen_ipv6: bool

    workers: int

    ssl_certificate: str
    ssl_certificate_key: str
    ssl_ciphers: str
    ssl_dhparam: str

    uds_server: str
    uds_token: str
    uds_timeout: int
    uds_verify_ssl: bool

    secret: str
    allow: typing.Set[str]

    use_uvloop: bool


def read_config_file(
    cfg_file: typing.Optional[typing.Union[typing.TextIO, str]] = None
) -> str:
    if cfg_file is None:
        cfg_file = CONFIGFILE
    if isinstance(cfg_file, str):
        with open(cfg_file, 'r') as f:
            return '[uds]\n' + f.read()
    # path is in fact a file-like object
    return '[uds]\n' + cfg_file.read()


def read(
    cfg_file: typing.Optional[typing.Union[typing.TextIO, str]] = None
) -> ConfigurationType:
    config_str = read_config_file(cfg_file)

    cfg = configparser.ConfigParser()
    cfg.read_string(config_str)

    uds = cfg['uds']

    # Gets and create secret hash
    h = hashlib.sha256()
    h.update(uds.get('secret', '').encode())
    secret = h.hexdigest()

    # Now load and fix uds server url
    uds_server = uds['uds_server']
    if uds_server[:4] != 'http':
        raise Exception('Invalid url for uds server')
    if uds_server[-1] == '/':
        uds_server = uds_server[:-1]

    try:
        # log size
        logsize: str = uds.get('logsize', '32M')
        if logsize[-1] == 'M':
            logsize = logsize[:-1]
        return ConfigurationType(
            pidfile=uds.get('pidfile', ''),
            user=uds.get('user', ''),
            log_level=uds.get('loglevel', 'ERROR'),
            log_file=uds.get('logfile', ''),
            log_size=int(logsize) * 1024 * 1024,
            log_number=int(uds.get('lognumber', '3')),
            listen_address=uds.get('address', '0.0.0.0'),
            listen_port=int(uds.get('port', '443')),
            listen_ipv6=uds.get('ipv6', 'false').lower() == 'true',
            workers=int(uds.get('workers', '0')) or multiprocessing.cpu_count(),
            ssl_certificate=uds['ssl_certificate'],
            ssl_certificate_key=uds.get('ssl_certificate_key', ''),
            ssl_ciphers=uds.get('ssl_ciphers'),
            ssl_dhparam=uds.get('ssl_dhparam'),
            uds_server=uds_server,
            uds_token=uds.get('uds_token', 'unauthorized'),
            uds_timeout=int(uds.get('uds_timeout', '10')),
            uds_verify_ssl=uds.get('uds_verify_ssl', 'true').lower() == 'true',
            secret=secret,
            allow=set(uds.get('allow', '127.0.0.1').split(',')),
            use_uvloop=uds.get('use_uvloop', 'true').lower() == 'true',
        )
    except ValueError as e:
        raise Exception(
            f'Mandatory configuration file in incorrect format: {e.args[0]}. Please, revise {CONFIGFILE}'
        )
    except KeyError as e:
        raise Exception(
            f'Mandatory configuration parameter not found: {e.args[0]}. Please, revise {CONFIGFILE}'
        )
