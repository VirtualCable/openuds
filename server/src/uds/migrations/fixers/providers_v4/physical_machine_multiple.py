# Copy for migration
# -*- coding: utf-8 -*-
#
# Copyright (c) 2023 Virtual Cable S.L.U.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification
# are permitted provided that the following conditions are met:
#
#    * Redistributions of source code must retain the above copyright notice
#      this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright notice
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import datetime
import logging
import typing
import pickle  # nosec: pickle is used for legacy data transition

from uds.core import services
from uds.core.ui import gui

from . import _migrator

logger = logging.getLogger(__name__)

IP_SUBTYPE: typing.Final[str] = 'ip'


class IPMachinesService(services.Service):
    type_type = 'IPMachinesService'

    # Gui
    token = gui.TextField(label='', default='')
    ipList = gui.EditableListField(label='')
    port = gui.NumericField(label='', default=0)
    skipTimeOnFailure = gui.NumericField(label='', default=0)
    maxSessionForMachine = gui.NumericField(label='', default=0)
    lockByExternalAccess = gui.CheckBoxField(label='', default=False)
    useRandomIp = gui.CheckBoxField(label='', default=False)

    # This value is the new server group that contains the "ipList"
    server_group = gui.ChoiceField(label='')

    def unmarshal(self, data: bytes) -> None:
        values: typing.List[bytes] = data.split(b'\0')
        d = self.storage.read_from_db('ips')
        _ips: list[str] = []
        if isinstance(d, bytes):
            _ips = pickle.loads(d)
        elif isinstance(d, str):  # "legacy" saved elements
            _ips = pickle.loads(d.encode('utf8'))
        else:
            _ips = []

        if not isinstance(_ips, list):  # pyright: ignore  # This is for compatibility with old data
            _ips = []

        def _as_identifier(data: str) -> str:
            ip_mac, _order = (data.split('~') + [''])[:2]
            ip, mac = (ip_mac.split(';') + [''])[:2]
            if mac:
                return f'{ip};{mac}'
            return ip

        self.ipList.value = [_as_identifier(i) for i in _ips]

        if values[0] != b'v1':
            self._token = values[1].decode()
            if values[0] in (b'v3', b'v4', b'v5', b'v6', b'v7'):
                self.port.value = int(values[2].decode())
            if values[0] in (b'v4', b'v5', b'v6', b'v7'):
                self.skipTimeOnFailure.value = int(values[3].decode())
            if values[0] in (b'v5', b'v6', b'v7'):
                self.maxSessionForMachine.value = int(values[4].decode())
            if values[0] in (b'v6', b'v7'):
                self.lockByExternalAccess.value = gui.as_bool(values[5].decode())
            if values[0] in (b'v7',):
                self.useRandomIp = gui.as_bool(values[6].decode())

    # Note that will be marshalled as new format, so we don't need to care about old format in code anymore :)
    def post_migrate(self) -> None:
        from uds.core.util import fields

        FOREVER: typing.Final[datetime.timedelta] = datetime.timedelta(days=365 * 20)
        now = datetime.datetime.now()
        server_group = fields.get_server_group_from_field(self.server_group)
        for server in server_group.servers.all():
            
            locked = self.storage.read_pickled(server.ip)
            # print(f'Locked: {locked} for {server.ip}')
            if not locked:
                continue

            if (
                isinstance(locked, str) and not '.' in locked
            ):  # Convert to int and treat it as a "locked" element
                locked = int(locked)

            # If maxSessionForMachine is 0, we will lock the server
            # using locked as bool
            if self.maxSessionForMachine.value <= 0:
                if bool(locked):
                    # print(f'Locking {server.ip} forever due to maxSessionForMachine=0')
                    server.lock(FOREVER)  # Almost forever
                    server.save(update_fields=['locked_until'])
                continue  # Not locked, continue

            if not isinstance(locked, int):
                # print(f'Locking {server.ip} due to not being an int (very old data)')
                server.lock(FOREVER)
                server.save(update_fields=['locked_until'])
                continue

            if not bool(locked) or locked < now.timestamp() - self.maxSessionForMachine.value * 3600:
                # print(f'Not locking {server.ip} due to not being locked or lock expired')
                continue  # Server not locked or lock expired, no need to lock it

            # Lock for until locked time, where locked is a timestamp
            # print(f'Locking {server.ip} until {datetime.datetime.fromtimestamp(locked)}')
            server.lock(datetime.timedelta(seconds=locked - now.timestamp()))


def migrate(apps: typing.Any, schema_editor: typing.Any) -> None:
    _migrator.migrate(
        apps, 'Service', IPMachinesService, IP_SUBTYPE, 'ipList', 'Physical Machines Server Group'
    )

    # Ensure locked servers continue locked


def rollback(apps: typing.Any, schema_editor: typing.Any) -> None:
    _migrator.rollback(apps, 'Service', IPMachinesService, IP_SUBTYPE, 'ipList')
