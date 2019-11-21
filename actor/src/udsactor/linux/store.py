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
import os
import configparser
import base64
import pickle

from .. import types

CONFIGFILE = '/etc/udsactor/udsactor.cfg'

def checkPermissions() -> bool:
    return os.getuid() == 0

def readConfig() -> types.ActorConfigurationType:
    try:
        cfg = configparser.ConfigParser()
        cfg.read(CONFIGFILE)
        uds: configparser.SectionProxy = cfg['uds']
        # Extract data:
        base64Data = uds.get('data', None)
        data = pickle.loads(base64.b64decode(base64Data.encode())) if base64Data else None

        return types.ActorConfigurationType(
            host=uds.get('host', ''),
            validateCertificate=uds.getboolean('validate', fallback=False),
            master_token=uds.get('master_token', None),
            own_token=uds.get('own_token', None),
            data=data
        )
    except Exception:
        return types.ActorConfigurationType('', False)


def writeConfig(config: types.ActorConfigurationType) -> None:
    cfg = configparser.ConfigParser()
    cfg.add_section('uds')
    uds: configparser.SectionProxy = cfg['uds']
    uds['host'] = config.host
    uds['validate'] = 'yes' if config.validateCertificate else 'no'
    if config.master_token:
        uds['master_token'] = config.master_token
    if config.own_token:
        uds['own_token'] = config.own_token
    if config.data:
        uds['data'] = base64.b64encode(pickle.dumps(config.data)).decode()

    # Ensures exists destination folder
    dirname = os.path.dirname(CONFIGFILE)
    if not os.path.exists(dirname):
        os.mkdir(dirname, mode=0o700)  # Will create only if route to path already exists, for example, /etc (that must... :-))

    with open(CONFIGFILE, 'w') as f:
        cfg.write(f)

    os.chmod(CONFIGFILE, 0o0600)  # Ensure only readable by root


def useOldJoinSystem():
    return False
