# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import os
import configparser
import base64
import pickle  # nosec

from .. import types

CONFIGFILE = '/etc/udsactor/udsactor.cfg'


def readConfig() -> types.ActorConfigurationType:
    try:
        cfg = configparser.ConfigParser()
        cfg.read(CONFIGFILE)
        uds: configparser.SectionProxy = cfg['uds']
        # Extract data:
        base64Config = uds.get('config', None)
        config = (
            pickle.loads(  # nosec: file is restricted
                base64.b64decode(base64Config.encode())
            )
            if base64Config
            else None
        )

        base64Data = uds.get('data', None)
        data = (
            pickle.loads(  # nosec: file is restricted
                base64.b64decode(base64Data.encode())
            )
            if base64Data
            else None
        )

        return types.ActorConfigurationType(
            actorType=uds.get('type', types.MANAGED),
            host=uds.get('host', ''),
            validateCertificate=uds.getboolean('validate', fallback=True),
            master_token=uds.get('master_token', None),
            own_token=uds.get('own_token', None),
            restrict_net=uds.get('restrict_net', None),
            pre_command=uds.get('pre_command', None),
            runonce_command=uds.get('runonce_command', None),
            post_command=uds.get('post_command', None),
            log_level=int(uds.get('log_level', '2')),
            config=config,
            data=data,
        )
    except Exception:
        return types.ActorConfigurationType('', False)


def writeConfig(config: types.ActorConfigurationType) -> None:
    cfg = configparser.ConfigParser()
    cfg.add_section('uds')
    uds: configparser.SectionProxy = cfg['uds']
    uds['host'] = config.host
    uds['validate'] = 'yes' if config.validateCertificate else 'no'

    def writeIfValue(val, name):
        if val:
            uds[name] = val

    writeIfValue(config.actorType, 'type')
    writeIfValue(config.master_token, 'master_token')
    writeIfValue(config.own_token, 'own_token')
    writeIfValue(config.restrict_net, 'restrict_net')
    writeIfValue(config.pre_command, 'pre_command')
    writeIfValue(config.post_command, 'post_command')
    writeIfValue(config.runonce_command, 'runonce_command')
    uds['log_level'] = str(config.log_level)
    if config.config:  # Special case, encoded & dumped
        uds['config'] = base64.b64encode(pickle.dumps(config.config)).decode()

    if config.data:  # Special case, encoded & dumped
        uds['data'] = base64.b64encode(pickle.dumps(config.data)).decode()

    # Ensures exists destination folder
    dirname = os.path.dirname(CONFIGFILE)
    if not os.path.exists(dirname):
        os.mkdir(
            dirname, mode=0o700
        )  # Will create only if route to path already exists, for example, /etc (that must... :-))

    with open(CONFIGFILE, 'w') as f:
        cfg.write(f)

    os.chmod(CONFIGFILE, 0o0600)  # Ensure only readable by root


def useOldJoinSystem() -> bool:
    return False


def invokeScriptOnLogin() -> str:
    return ''
