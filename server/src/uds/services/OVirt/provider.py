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

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing
import collections.abc

from django.utils.translation import gettext_noop as _

from uds.core import services, types, consts
from uds.core.ui import gui
from uds.core.util import validators
from uds.core.util.cache import Cache
from uds.core.util.decorators import cached

from . import client
from .service import OVirtLinkedService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.environment import Environment
    from uds.core.module import Module

logger = logging.getLogger(__name__)

CACHE_TIME_FOR_SERVER = 1800


class OVirtProvider(
    services.ServiceProvider
):  # pylint: disable=too-many-public-methods
    """
    This class represents the sample services provider

    In this class we provide:
       * The Provider functionality
       * The basic configuration parameters for the provider
       * The form fields needed by administrators to configure this provider

       :note: At class level, the translation must be simply marked as so
       using gettext_noop. This is so cause we will translate the string when
       sent to the administration client.

    For this class to get visible at administration client as a provider type,
    we MUST register it at package __init__.

    """

    # : What kind of services we offer, this are classes inherited from Service
    offers = [OVirtLinkedService]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('oVirt/RHEV Platform Provider')
    # : Type used internally to identify this provider
    type_type = 'oVirtPlatform'
    # : Description shown at administration interface for this provider
    type_description = _('oVirt platform service provider')
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
    ovirtVersion = gui.ChoiceField(
        order=1,
        label=_('oVirt Version'),
        tooltip=_('oVirt Server Version'),
        # In this case, the choice can have none value selected by default
        required=True,
        readonly=False,
        choices=[
            gui.choice_item('4', '4.x'),
        ],
        default='4',  # Default value is the ID of the choicefield
    )

    host = gui.TextField(
        length=64,
        label=_('Host'),
        order=2,
        tooltip=_('oVirt Server IP or Hostname'),
        required=True,
    )
    username = gui.TextField(
        length=32,
        label=_('Username'),
        order=3,
        tooltip=_('User with valid privileges on oVirt, (use "user@domain" form)'),
        required=True,
        default='admin@internal',
    )
    password = gui.PasswordField(
        length=32,
        label=_('Password'),
        order=4,
        tooltip=_('Password of the user of oVirt'),
        required=True,
    )

    max_preparing_services = gui.NumericField(
        length=3,
        label=_('Creation concurrency'),
        default=10,
        min_value=1,
        max_value=65536,
        order=50,
        tooltip=_('Maximum number of concurrently creating VMs'),
        required=True,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='maxPreparingServices',
    )
    max_removing_services = gui.NumericField(
        length=3,
        label=_('Removal concurrency'),
        default=5,
        min_value=1,
        max_value=65536,
        order=51,
        tooltip=_('Maximum number of concurrently removing VMs'),
        required=True,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='maxRemovingServices',
    )

    timeout = gui.NumericField(
        length=3,
        label=_('Timeout'),
        default=10,
        order=90,
        tooltip=_('Timeout in seconds of connection to oVirt'),
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )
    macsRange = gui.TextField(
        length=36,
        label=_('Macs range'),
        default='52:54:00:00:00:00-52:54:00:FF:FF:FF',
        order=91,
        readonly=True,
        tooltip=_('Range of valid macs for UDS managed machines'),
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )

    # Own variables
    _api: typing.Optional[client.Client] = None

    # oVirt engine, right now, only permits a connection to one server and only one per instance
    # If we want to connect to more than one server, we need keep locked access to api, change api server, etc..
    # We have implemented an "exclusive access" client that will only connect to one server at a time (using locks)
    # and this way all will be fine
    def __getApi(self) -> client.Client:
        """
        Returns the connection API object for oVirt (using ovirtsdk)
        """
        if self._api is None:
            self._api = client.Client(
                self.host.value,
                self.username.value,
                self.password.value,
                self.timeout.value,
                self.cache,
            )

        return self._api

    # There is more fields type, but not here the best place to cover it
    def initialize(self, values: 'Module.ValuesType') -> None:
        """
        We will use the "autosave" feature for form fields
        """

        # Just reset _api connection variable
        self._api = None

        if values is not None:
            self.macsRange.value = validators.validate_mac_range(self.macsRange.value)
            self.timeout.value = validators.validate_timeout(self.timeout.value)
            logger.debug(self.host.value)

    def testConnection(self) -> bool:
        """
        Test that conection to oVirt server is fine

        Returns

            True if all went fine, false if id didn't
        """

        return self.__getApi().test()

    def testValidVersion(self):
        """
        Checks that this version of ovirt if "fully functional" and does not needs "patchs'
        """
        return list(self.__getApi().isFullyFunctionalVersion())

    def getMachines(
        self, force: bool = False
    ) -> list[collections.abc.MutableMapping[str, typing.Any]]:
        """
        Obtains the list of machines inside oVirt.
        Machines starting with UDS are filtered out

        Args:
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns
            An array of dictionaries, containing:
                'name'
                'id'
                'cluster_id'
        """

        return self.__getApi().getVms(force)

    def getClusters(
        self, force: bool = False
    ) -> list[collections.abc.MutableMapping[str, typing.Any]]:
        """
        Obtains the list of clusters inside oVirt.

        Args:
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns
            Filters out clusters not attached to any datacenter
            An array of dictionaries, containing:
                'name'
                'id'
                'datacenter_id'
        """

        return self.__getApi().getClusters(force)

    def getClusterInfo(
        self, clusterId: str, force: bool = False
    ) -> collections.abc.MutableMapping[str, typing.Any]:
        """
        Obtains the cluster info

        Args:
            datacenterId: Id of the cluster to get information about it
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns

            A dictionary with following values
                'name'
                'id'
                'datacenter_id'
        """
        return self.__getApi().getClusterInfo(clusterId, force)

    def getDatacenterInfo(
        self, datacenterId: str, force: bool = False
    ) -> collections.abc.MutableMapping[str, typing.Any]:
        """
        Obtains the datacenter info

        Args:
            datacenterId: Id of the datacenter to get information about it
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns

            A dictionary with following values
                'name'
                'id'
                'storage_type' -> ('isisi', 'nfs', ....)
                'storage_format' -> ('v1', v2')
                'description'
                'storage' -> array of dictionaries, with:
                   'id' -> Storage id
                   'name' -> Storage name
                   'type' -> Storage type ('data', 'iso')
                   'available' -> Space available, in bytes
                   'used' -> Space used, in bytes
                   'active' -> True or False

        """
        return self.__getApi().getDatacenterInfo(datacenterId, force)

    def getStorageInfo(
        self, storageId: str, force: bool = False
    ) -> collections.abc.MutableMapping[str, typing.Any]:
        """
        Obtains the storage info

        Args:
            storageId: Id of the storage to get information about it
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns

            A dictionary with following values
               'id' -> Storage id
               'name' -> Storage name
               'type' -> Storage type ('data', 'iso')
               'available' -> Space available, in bytes
               'used' -> Space used, in bytes
               # 'active' -> True or False --> This is not provided by api?? (api.storagedomains.get)

        """
        return self.__getApi().getStorageInfo(storageId, force)

    def makeTemplate(
        self,
        name: str,
        comments: str,
        machineId: str,
        clusterId: str,
        storageId: str,
        displayType: str,
    ) -> str:
        """
        Publish the machine (makes a template from it so we can create COWs) and returns the template id of
        the creating machine

        Args:
            name: Name of the machine (care, only ascii characters and no spaces!!!)
            machineId: id of the machine to be published
            clusterId: id of the cluster that will hold the machine
            storageId: id of the storage tuat will contain the publication AND linked clones
            displayType: type of display (for oVirt admin interface only)

        Returns
            Raises an exception if operation could not be acomplished, or returns the id of the template being created.
        """
        return self.__getApi().makeTemplate(
            name, comments, machineId, clusterId, storageId, displayType
        )

    def getTemplateState(self, templateId: str) -> str:
        """
        Returns current template state.

        Returned values could be:
            ok
            locked
            removed

        (don't know if ovirt returns something more right now, will test what happens when template can't be published)
        """
        return self.__getApi().getTemplateState(templateId)

    def getMachineState(self, machineId: str) -> str:
        """
        Returns the state of the machine
        This method do not uses cache at all (it always tries to get machine state from oVirt server)

        Args:
            machineId: Id of the machine to get state

        Returns:
            one of this values:
             unassigned, down, up, powering_up, powered_down,
             paused, migrating_from, migrating_to, unknown, not_responding,
             wait_for_launch, reboot_in_progress, saving_state, restoring_state,
             suspended, image_illegal, image_locked or powering_down
             Also can return'unknown' if Machine is not known
        """
        return self.__getApi().getMachineState(machineId)

    def removeTemplate(self, templateId: str) -> None:
        """
        Removes a template from ovirt server

        Returns nothing, and raises an Exception if it fails
        """
        return self.__getApi().removeTemplate(templateId)

    def deployFromTemplate(
        self,
        name: str,
        comments: str,
        templateId: str,
        clusterId: str,
        displayType: str,
        usbType: str,
        memoryMB: int,
        guaranteedMB: int,
    ) -> str:
        """
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name: Name (sanitized) of the machine
            comments: Comments for machine
            templateId: Id of the template to deploy from
            clusterId: Id of the cluster to deploy to
            displayType: 'vnc' or 'spice'. Display to use ad oVirt admin interface
            memoryMB: Memory requested for machine, in MB
            guaranteedMB: Minimum memory guaranteed for this machine

        Returns:
            Id of the machine being created form template
        """
        return self.__getApi().deployFromTemplate(
            name,
            comments,
            templateId,
            clusterId,
            displayType,
            usbType,
            memoryMB,
            guaranteedMB,
        )

    def startMachine(self, machineId: str) -> None:
        """
        Tries to start a machine. No check is done, it is simply requested to oVirt.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        """
        self.__getApi().startMachine(machineId)

    def stopMachine(self, machineId: str) -> None:
        """
        Tries to start a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        """
        self.__getApi().stopMachine(machineId)

    def suspendMachine(self, machineId: str) -> None:
        """
        Tries to start a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        """
        self.__getApi().suspendMachine(machineId)

    def removeMachine(self, machineId: str) -> None:
        """
        Tries to delete a machine. No check is done, it is simply requested to oVirt

        Args:
            machineId: Id of the machine

        Returns:
        """
        self.__getApi().removeMachine(machineId)

    def updateMachineMac(self, machineId: str, macAddres: str) -> None:
        """
        Changes the mac address of first nic of the machine to the one specified
        """
        self.__getApi().updateMachineMac(machineId, macAddres)

    def fixUsb(self, machineId: str) -> None:
        self.__getApi().fixUsb(machineId)

    def getMacRange(self) -> str:
        return self.macsRange.value

    def getConsoleConnection(
        self, machineId: str
    ) -> typing.Optional[collections.abc.MutableMapping[str, typing.Any]]:
        return self.__getApi().getConsoleConnection(machineId)

    @cached('reachable', consts.cache.SHORT_CACHE_TIMEOUT)
    def isAvailable(self) -> bool:
        """
        Check if aws provider is reachable
        """
        return self.testConnection()

    @staticmethod
    def test(env: 'Environment', data: 'Module.ValuesType') -> list[typing.Any]:
        """
        Test ovirt Connectivity

        Args:
            env: environment passed for testing (temporal environment passed)

            data: data passed for testing (data obtained from the form
            definition)

        Returns:
            Array of two elements, first is True of False, depending on test
            (True is all right, false is error),
            second is an String with error, preferably internacionalizated..

        """
        # try:
        #    # We instantiate the provider, but this may fail...
        #    instance = Provider(env, data)
        #    logger.debug('Methuselah has {0} years and is {1} :-)'
        #                 .format(instance.methAge.value, instance.methAlive.value))
        # except exceptions.ValidationException as e:
        #    # If we say that meth is alive, instantiation will
        #    return [False, str(e)]
        # except Exception as e:
        #    logger.exception("Exception caugth!!!")
        #    return [False, str(e)]
        # return [True, _('Nothing tested, but all went fine..')]
        ov = OVirtProvider(env, data)
        if ov.testConnection() is True:
            return ov.testValidVersion()

        return [False, _("Connection failed. Check connection params")]
