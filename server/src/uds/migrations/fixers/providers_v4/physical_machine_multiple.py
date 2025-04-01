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
import base64
import datetime
import logging
import typing
import pickle  # nosec: pickle is used for legacy data transition

from uds.core import services, types
from uds.core.ui import gui
from uds.core.util import auto_attributes, autoserializable

from . import _migrator

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    import uds.models

IP_SUBTYPE: typing.Final[str] = 'ip'


class OldIPSerialData(auto_attributes.AutoAttributes):
    _ip: str
    _reason: str
    _state: str

    def __init__(self) -> None:
        auto_attributes.AutoAttributes.__init__(self, ip=str, reason=str, state=str)
        self._ip = ''
        self._reason = ''
        self._state = types.states.TaskState.FINISHED


class NewIpSerialData(autoserializable.AutoSerializable):
    suggested_delay = 10

    _ip = autoserializable.StringField(default='')
    _mac = autoserializable.StringField(default='')
    _vmid = autoserializable.StringField(default='')
    _reason = autoserializable.StringField(default='')  # If != '', this is the error message and state is ERROR


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
                self.useRandomIp.value = gui.as_bool(values[6].decode())

    # Note that will be marshalled as new format, so we don't need to care about old format in code anymore :)
    def post_migrate(self, apps: typing.Any, record: typing.Any) -> None:
        from uds.core.util import fields

        FOREVER: typing.Final[datetime.timedelta] = datetime.timedelta(days=365 * 20)
        now = datetime.datetime.now()
        server_group = fields.get_server_group_from_field(self.server_group)

        for server in server_group.servers.all():

            try:
                locked = self.storage.read_pickled(server.ip)
            except Exception as e:
                logger.error('Error on postmigrate reading locked value for %s: %s', server.ip, e)
                locked = None

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
                continue  # Not locked, continue

            if not isinstance(locked, int):
                # print(f'Locking {server.ip} due to not being an int (very old data)')
                server.lock(FOREVER)
                continue

            if not bool(locked) or locked < now.timestamp() - self.maxSessionForMachine.value * 3600:
                # print(f'Not locking {server.ip} due to not being locked or lock expired')
                continue  # Server not locked or lock expired, no need to lock it

            # Lock for until locked time, where locked is a timestamp
            # print(f'Locking {server.ip} until {datetime.datetime.fromtimestamp(locked)}')
            server.lock(datetime.timedelta(seconds=locked - now.timestamp()))

        Service: 'type[uds.models.Service]' = apps.get_model('uds', 'Service')
        ServicePool: 'type[uds.models.ServicePool]' = apps.get_model('uds', 'ServicePool')

        assigned_servers: set[str] = set()
        for servicepool in ServicePool.objects.filter(service=Service.objects.get(uuid=record.uuid)):
            for userservice in servicepool.userServices.all():
                new_data = NewIpSerialData()
                try:
                    auto_data = OldIPSerialData()
                    auto_data.unmarshal(base64.b64decode(userservice.data))
                    # Fill own data from restored data
                    ip_mac = auto_data._ip.split('~')[0]
                    if ';' in ip_mac:
                        new_data._ip, new_data._mac = ip_mac.split(';', 2)[:2]
                    else:
                        new_data._ip = ip_mac
                        new_data._mac = ''
                    new_data._reason = auto_data._reason
                    state = auto_data._state
                    # Ensure error is set if _reason is set
                    if state == types.states.TaskState.ERROR and new_data._reason == '':
                        new_data._reason = 'Unknown error'

                    # Reget vmid if needed
                    if not new_data._reason and userservice.state == types.states.State.USABLE:
                        new_data._vmid = ''
                        for server in server_group.servers.all():
                            if (
                                server.ip == new_data._ip or server.hostname == new_data._ip
                            ) and server.uuid not in assigned_servers:
                                new_data._vmid = server.uuid
                                assigned_servers.add(server.uuid)
                                # Ensure locked, relock if needed
                                if not server.locked_until or server.locked_until < now:
                                    if self.maxSessionForMachine.value <= 0:
                                        server.lock(FOREVER)
                                    else:
                                        server.lock(datetime.timedelta(hours=self.maxSessionForMachine.value))
                                break
                        if not new_data._vmid:
                            new_data._reason = f'Migrated machine not found for {new_data._ip}'
                except Exception as e:  # Invalid serialized record, record new format with error
                    new_data._ip = ''
                    new_data._mac = ''
                    new_data._vmid = ''
                    new_data._reason = f'Error migrating: {e}'[:320]

                userservice.data = new_data.serialize()
                userservice.save(update_fields=['data'])


def migrate(apps: typing.Any, schema_editor: typing.Any) -> None:
    _migrator.migrate(
        apps, 'Service', IPMachinesService, IP_SUBTYPE, 'ipList', 'Physical Machines Server Group'
    )

    # Ensure locked servers continue locked


def rollback(apps: typing.Any, schema_editor: typing.Any) -> None:
    _migrator.rollback(apps, 'Service', IPMachinesService, IP_SUBTYPE, 'ipList')
