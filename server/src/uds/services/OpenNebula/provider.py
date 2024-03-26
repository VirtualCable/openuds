# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2019 Virtual Cable S.L.
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
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

'''
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import collections.abc
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds.core import consts, environment, types
from uds.core.services import ServiceProvider
from uds.core.ui import gui
from uds.core.util import fields, validators
from uds.core.util.decorators import cached

from . import on
from .service import OpenNebulaLiveService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class OpenNebulaProvider(ServiceProvider):  # pylint: disable=too-many-public-methods
    # : What kind of services we offer, this are classes inherited from Service
    offers = [OpenNebulaLiveService]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('OpenNebula Platform Provider')
    # : Type used internally to identify this provider
    type_type = 'openNebulaPlatform'
    # : Description shown at administration interface for this provider
    type_description = _('OpenNebula platform service provider')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    icon_file = 'provider.png'

    # now comes the form fields
    # There is always two fields that are requested to the admin, that are:
    # Service Name, that is a name that the admin uses to name this provider
    # Description, that is a short description that the admin gives to this provider
    # Now we are going to add a few fields that we need to use this provider
    # Remember that these are "dummy" fields, that in fact are not required
    # but used for sample purposes
    # If we don't indicate an order, the output order of fields will be
    # "random"
    host = gui.TextField(length=64, label=_('Host'), order=1, tooltip=_('OpenNebula Host'), required=True)
    port = gui.NumericField(
        length=5,
        label=_('Port'),
        default=2633,
        order=2,
        tooltip=_('OpenNebula Port (default is 2633 for non ssl connection)'),
        required=True,
    )
    ssl = gui.CheckBoxField(
        label=_('Use SSL'),
        order=3,
        tooltip=_(
            'If checked, the connection will be forced to be ssl (will not work if server is not providing ssl)'
        ),
    )
    username = gui.TextField(
        length=32,
        label=_('Username'),
        order=4,
        tooltip=_('User with valid privileges on OpenNebula'),
        required=True,
        default='oneadmin',
    )
    password = gui.PasswordField(
        length=32,
        label=_('Password'),
        order=5,
        tooltip=_('Password of the user of OpenNebula'),
        required=True,
    )
    concurrent_creation_limit = fields.concurrent_creation_limit_field()
    concurrent_removal_limit = fields.concurrent_removal_limit_field()
    timeout = fields.timeout_field(default=10)

    # Own variables
    _api: typing.Optional[on.client.OpenNebulaClient] = None

    def initialize(self, values: 'types.core.ValuesType') -> None:
        '''
        We will use the "autosave" feature for form fields
        '''

        # Just reset _api connection variable
        self._api = None

        if values:
            self.timeout.value = validators.validate_timeout(self.timeout.value)
            logger.debug('Endpoint: %s', self.endpoint)

    @property
    def endpoint(self) -> str:
        return 'http{}://{}:{}/RPC2'.format('s' if self.ssl.as_bool() else '', self.host.value, self.port.value)

    @property
    def api(self) -> on.client.OpenNebulaClient:
        if self._api is None:
            self._api = on.client.OpenNebulaClient(self.username.value, self.password.value, self.endpoint)

        return self._api

    def resetApi(self) -> None:
        self._api = None

    def sanitized_name(self, name: str) -> str:
        return on.sanitized_name(name)

    def test_connection(self) -> types.core.TestResult:
        '''
        Test that conection to OpenNebula server is fine

        Returns

            True if all went fine, false if id didn't
        '''

        try:
            if self.api.version[0] < '4':
                return types.core.TestResult(
                    False,
                    _('OpenNebula version is not supported (required version 4.1 or newer)'),
                )
        except Exception as e:
            return types.core.TestResult(False, _('Error connecting to OpenNebula: {}').format(e))

        return types.core.TestResult(True, _('Opennebula test connection passed'))

    def getDatastores(self, datastoreType: int = 0) -> collections.abc.Iterable[on.types.StorageType]:
        yield from on.storage.enumerateDatastores(self.api, datastoreType)

    def getTemplates(self, force: bool = False) -> collections.abc.Iterable[on.types.TemplateType]:
        yield from on.template.getTemplates(self.api, force)

    def make_template(self, from_template_id: str, name: str, dest_storage: str) -> str:
        return on.template.create(self.api, from_template_id, name, dest_storage)

    def check_template_published(self, templateId: str) -> bool:
        return on.template.check_published(self.api, templateId)

    def removeTemplate(self, templateId: str) -> None:
        on.template.remove(self.api, templateId)

    def deply_from_template(self, name: str, templateId: str) -> str:
        return on.template.deployFrom(self.api, templateId, name)

    def getMachineState(self, machineId: str) -> on.types.VmState:
        '''
        Returns the state of the machine
        This method do not uses cache at all (it always tries to get machine state from OpenNebula server)

        Args:
            machineId: Id of the machine to get state

        Returns:
            one of the on.VmState Values
        '''
        return on.vm.get_machine_state(self.api, machineId)

    def getMachineSubstate(self, machineId: str) -> int:
        '''
        Returns the  LCM_STATE of a machine (STATE must be ready or this will return -1)
        '''
        return on.vm.get_machine_substate(self.api, machineId)

    def startMachine(self, machineId: str) -> None:
        '''
        Tries to start a machine. No check is done, it is simply requested to OpenNebula.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.start_machine(self.api, machineId)

    def stopMachine(self, machineId: str) -> None:
        '''
        Tries to stop a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.stop_machine(self.api, machineId)

    def suspendMachine(self, machineId: str) -> None:
        '''
        Tries to suspend a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.suspend_machine(self.api, machineId)

    def shutdownMachine(self, machineId: str) -> None:
        '''
        Tries to shutdown "gracefully" a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.shutdown_machine(self.api, machineId)

    def resetMachine(self, machineId: str) -> None:
        '''
        Resets a machine (hard-reboot)
        '''
        on.vm.reset_machine(self.api, machineId)

    def removeMachine(self, machineId: str) -> None:
        '''
        Tries to delete a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.remove_machine(self.api, machineId)

    def getNetInfo(self, machineId: str, networkId: typing.Optional[str] = None) -> tuple[str, str]:
        '''
        Changes the mac address of first nic of the machine to the one specified
        '''
        return on.vm.get_network_info(self.api, machineId, networkId)

    def get_console_connection(self, vmid: str) -> typing.Optional[types.services.ConsoleConnectionInfo]:
        console_connection_info = on.vm.get_console_connection(self.api, vmid)

        if console_connection_info is None:
            raise Exception('Invalid console connection on OpenNebula!!!')
        
        return console_connection_info

    def desktop_login(self, vmid: str, username: str, password: str, domain: str) -> typing.Optional[types.services.ConsoleConnectionInfo]:
        '''
        Not provided by OpenNebula API right now
        '''
        return None

    @staticmethod
    def test(env: 'environment.Environment', data: 'types.core.ValuesType') -> 'types.core.TestResult':
        return OpenNebulaProvider(env, data).test_connection()

    @cached('reachable', consts.cache.SHORT_CACHE_TIMEOUT)
    def is_available(self) -> bool:
        """
        Check if aws provider is reachable
        """
        return self.test_connection().success
