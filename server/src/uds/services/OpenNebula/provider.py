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
import logging
import typing
import collections.abc

from django.utils.translation import gettext_noop as _

from uds.core import types, consts
from uds.core.services import ServiceProvider
from uds.core.ui import gui
from uds.core.util import validators
from uds.core.util.cache import Cache
from uds.core.util.decorators import cached

from . import on
from .service import LiveService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.environment import Environment
    from uds.core.module import Module

logger = logging.getLogger(__name__)


class OpenNebulaProvider(ServiceProvider):  # pylint: disable=too-many-public-methods
    # : What kind of services we offer, this are classes inherited from Service
    offers = [LiveService]
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
    host = gui.TextField(
        length=64, label=_('Host'), order=1, tooltip=_('OpenNebula Host'), required=True
    )
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

    maxPreparingServices = gui.NumericField(
        length=3,
        label=_('Creation concurrency'),
        default=10,
        minValue=1,
        maxValue=65536,
        order=50,
        tooltip=_('Maximum number of concurrently creating VMs'),
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )
    maxRemovingServices = gui.NumericField(
        length=3,
        label=_('Removal concurrency'),
        default=5,
        minValue=1,
        maxValue=65536,
        order=51,
        tooltip=_('Maximum number of concurrently removing VMs'),
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )

    timeout = gui.NumericField(
        length=3,
        label=_('Timeout'),
        default=10,
        order=90,
        tooltip=_('Timeout in seconds of connection to OpenNebula'),
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )

    # Own variables
    _api: typing.Optional[on.client.OpenNebulaClient] = None

    def initialize(self, values: 'Module.ValuesType') -> None:
        '''
        We will use the "autosave" feature for form fields
        '''

        # Just reset _api connection variable
        self._api = None

        if values:
            self.timeout.value = validators.validateTimeout(self.timeout.value)
            logger.debug('Endpoint: %s', self.endpoint)

    @property
    def endpoint(self) -> str:
        return 'http{}://{}:{}/RPC2'.format(
            's' if self.ssl.isTrue() else '', self.host.value, self.port.value
        )

    @property
    def api(self) -> on.client.OpenNebulaClient:
        if self._api is None:
            self._api = on.client.OpenNebulaClient(
                self.username.value, self.password.value, self.endpoint
            )

        return self._api

    def resetApi(self) -> None:
        self._api = None

    def sanitizeVmName(self, name: str) -> str:
        return on.sanitizeName(name)

    def testConnection(self) -> list[typing.Any]:
        '''
        Test that conection to OpenNebula server is fine

        Returns

            True if all went fine, false if id didn't
        '''

        try:
            if self.api.version[0] < '4':
                return [
                    False,
                    'OpenNebula version is not supported (required version 4.1 or newer)',
                ]
        except Exception as e:
            return [False, '{}'.format(e)]

        return [True, _('Opennebula test connection passed')]

    def getDatastores(
        self, datastoreType: int = 0
    ) -> collections.abc.Iterable[on.types.StorageType]:
        yield from on.storage.enumerateDatastores(self.api, datastoreType)

    def getTemplates(
        self, force: bool = False
    ) -> collections.abc.Iterable[on.types.TemplateType]:
        yield from on.template.getTemplates(self.api, force)

    def makeTemplate(self, fromTemplateId: str, name, toDataStore: str) -> str:
        return on.template.create(self.api, fromTemplateId, name, toDataStore)

    def checkTemplatePublished(self, templateId: str) -> bool:
        return on.template.checkPublished(self.api, templateId)

    def removeTemplate(self, templateId: str) -> None:
        on.template.remove(self.api, templateId)

    def deployFromTemplate(self, name: str, templateId: str) -> str:
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
        return on.vm.getMachineState(self.api, machineId)

    def getMachineSubstate(self, machineId: str) -> int:
        '''
        Returns the  LCM_STATE of a machine (STATE must be ready or this will return -1)
        '''
        return on.vm.getMachineSubstate(self.api, machineId)

    def startMachine(self, machineId: str) -> None:
        '''
        Tries to start a machine. No check is done, it is simply requested to OpenNebula.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.startMachine(self.api, machineId)

    def stopMachine(self, machineId: str) -> None:
        '''
        Tries to stop a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.stopMachine(self.api, machineId)

    def suspendMachine(self, machineId: str) -> None:
        '''
        Tries to suspend a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.suspendMachine(self.api, machineId)

    def shutdownMachine(self, machineId: str) -> None:
        '''
        Tries to shutdown "gracefully" a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.shutdownMachine(self.api, machineId)

    def resetMachine(self, machineId: str) -> None:
        '''
        Resets a machine (hard-reboot)
        '''
        on.vm.resetMachine(self.api, machineId)

    def removeMachine(self, machineId: str) -> None:
        '''
        Tries to delete a machine. No check is done, it is simply requested to OpenNebula

        Args:
            machineId: Id of the machine

        Returns:
        '''
        on.vm.removeMachine(self.api, machineId)

    def getNetInfo(
        self, machineId: str, networkId: typing.Optional[str] = None
    ) -> tuple[str, str]:
        '''
        Changes the mac address of first nic of the machine to the one specified
        '''
        return on.vm.getNetInfo(self.api, machineId, networkId)

    def getConsoleConnection(self, machineId: str) -> dict[str, typing.Any]:
        display = on.vm.getDisplayConnection(self.api, machineId)

        if display is None:
            raise Exception('Invalid console connection on OpenNebula!!!')

        return {
            'type': display['type'],
            'address': display['host'],
            'port': display['port'],
            'secure_port': -1,
            'monitors': 1,
            'cert_subject': '',
            'ticket': {'value': display['passwd'], 'expiry': ''},
        }

    def desktopLogin(self, machineId: str, username: str, password: str, domain: str) -> dict[str, typing.Any]:
        '''
        Not provided by OpenNebula API right now
        '''
        return dict()

    @staticmethod
    def test(env: 'Environment', data: 'Module.ValuesType') -> list[typing.Any]:
        return OpenNebulaProvider(env, data).testConnection()

    @cached('reachable', consts.system.SHORT_CACHE_TIMEOUT)
    def isAvailable(self) -> bool:
        """
        Check if aws provider is reachable
        """
        return self.testConnection()[0]
