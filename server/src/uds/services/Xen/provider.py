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

from uds.core import types, consts
from uds.core.services import ServiceProvider
from uds.core.ui import gui
from uds.core.util.decorators import cached
from uds.core.util import fields

from .service import XenLinkedService
from .service_fixed import XenFixedService
from .xen_client import XenServer

# from uds.core.util import validators


# from xen_client import XenFailure, XenFault


logger = logging.getLogger(__name__)

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import environment


class XenProvider(ServiceProvider):  # pylint: disable=too-many-public-methods
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
    offers = [XenLinkedService, XenFixedService]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('Xenserver/XCP-NG Platforms Provider')
    # : Type used internally to identify this provider
    type_type = 'XenPlatform'
    # : Description shown at administration interface for this provider
    type_description = _('XenServer and XCP-NG platforms service provider')
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
        length=64,
        label=_('Host'),
        order=1,
        tooltip=_('XenServer Server IP or Hostname'),
        required=True,
    )
    username = gui.TextField(
        length=32,
        label=_('Username'),
        order=2,
        tooltip=_('User with valid privileges on XenServer'),
        required=True,
        default='root',
    )
    password = gui.PasswordField(
        length=32,
        label=_('Password'),
        order=3,
        tooltip=_('Password of the user of XenServer'),
        required=True,
    )
    concurrent_creation_limit = fields.concurrent_creation_limit_field()
    concurrent_removal_limit = fields.concurrent_removal_limit_field()

    macs_range = fields.macs_range_field(default='02:46:00:00:00:00-02:46:00:FF:FF:FF')
    verify_ssl = fields.verify_ssl_field(old_field_name='verifySSL')

    host_backup = gui.TextField(
        length=64,
        label=_('Backup Host'),
        order=92,
        tooltip=_('XenServer BACKUP IP or Hostname (used on connection failure to main server)'),
        tab=types.ui.Tab.ADVANCED,
        required=False,
        old_field_name='hostBackup',
    )

    _api: typing.Optional[XenServer]

    # XenServer engine, right now, only permits a connection to one server and only one per instance
    # If we want to connect to more than one server, we need keep locked access to api, change api server, etc..
    # We have implemented an "exclusive access" client that will only connect to one server at a time (using locks)
    # and this way all will be fine
    def _get_api(self, force: bool = False) -> XenServer:
        """
        Returns the connection API object for XenServer (using XenServersdk)
        """
        if not self._api or force:
            self._api = XenServer(
                self.host.value,
                self.host_backup.value,
                443,
                self.username.value,
                self.password.value,
                True,
                self.verify_ssl.as_bool(),
            )

        return self._api

    # There is more fields type, but not here the best place to cover it
    def initialize(self, values: 'types.core.ValuesType') -> None:
        """
        We will use the "autosave" feature for form fields
        """

        # Just reset _api connection variable
        self._api = None

    def test_connection(self) -> None:
        """
        Test that conection to XenServer server is fine

        Returns

            True if all went fine, false if id didn't
        """
        self._get_api().test()

    def check_task_finished(self, task: typing.Optional[str]) -> tuple[bool, str]:
        """
        Checks a task state.
        Returns None if task is Finished
        Returns a number indicating % of completion if running
        Raises an exception with status else ('cancelled', 'unknown', 'failure')
        """
        if not task:
            return True, ''

        ts = self._get_api().get_task_info(task)
        logger.debug('Task status: %s', ts)
        if ts['status'] == 'running':
            return False, ts['progress']
        if ts['status'] == 'success':
            return True, ts['result']

        # Any other state, raises an exception
        raise Exception(ts)  # Should be error message

    def list_machines(self, force: bool = False) -> list[collections.abc.MutableMapping[str, typing.Any]]:
        """
        Obtains the list of machines inside XenServer.
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

        return [m for m in self._get_api().list_machines() if m['name'][:3] != 'UDS']

    def list_storages(self, force: bool = False) -> list[dict[str, typing.Any]]:
        """
        Obtains the list of storages inside XenServer.

        Args:
            force: If true, force to update the cache, if false, tries to first
            get data from cache and, if valid, return this.

        Returns
            An array of dictionaries, containing:
                'name'
                'id'
                'size'
                'used'
        """
        return self._get_api().list_srs()

    def get_storage_info(
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
        return self._get_api().get_sr_info(storageId)

    def get_networks(
        self, force: bool = False
    ) -> collections.abc.Iterable[collections.abc.MutableMapping[str, typing.Any]]:
        return self._get_api().list_networks()

    def clone_for_template(self, name: str, comments: str, machineId: str, sr: str) -> str:
        task = self._get_api().clone_machine(machineId, name, sr)
        logger.debug('Task for cloneForTemplate: %s', task)
        return task

    def convert_to_template(self, machine_id: str, shadow_multiplier: int = 4) -> None:
        """
        Publish the machine (makes a template from it so we can create COWs) and returns the template id of
        the creating machine

        Args:
            name: Name of the machine (care, only ascii characters and no spaces!!!)
            machineId: id of the machine to be published
            clusterId: id of the cluster that will hold the machine
            storageId: id of the storage tuat will contain the publication AND linked clones
            displayType: type of display (for XenServer admin interface only)

        Returns
            Raises an exception if operation could not be acomplished, or returns the id of the template being created.
        """
        self._get_api().convert_to_template(machine_id, shadow_multiplier)

    def remove_template(self, templateId: str) -> None:
        """
        Removes a template from XenServer server

        Returns nothing, and raises an Exception if it fails
        """
        self._get_api().remove_template(templateId)

    def start_deploy_from_template(self, name: str, comments: str, template_id: str) -> str:
        """
        Deploys a virtual machine on selected cluster from selected template

        Args:
            name: Name (sanitized) of the machine
            comments: Comments for machine
            templateId: Id of the template to deploy from
            clusterId: Id of the cluster to deploy to
            displayType: 'vnc' or 'spice'. Display to use ad XenServer admin interface
            memoryMB: Memory requested for machine, in MB
            guaranteedMB: Minimum memory guaranteed for this machine

        Returns:
            Id of the machine being created form template
        """
        return self._get_api().start_deploy_from_template(template_id, name)

    def get_machine_power_state(self, machine_id: str) -> str:
        """
        Returns current machine power state
        """
        return self._get_api().get_machine_power_state(machine_id)

    def get_machine_name(self, machine_id: str) -> str:
        return self._get_api().get_machine_info(machine_id).get('name_label', '')

    def list_folders(self) -> list[str]:
        return self._get_api().list_folders()

    def get_machine_folder(self, machine_id: str) -> str:
        return self._get_api().get_machine_folder(machine_id)

    def get_machines_from_folder(
        self, folder: str, retrieve_names: bool = False
    ) -> list[dict[str, typing.Any]]:
        return self._get_api().get_machines_from_folder(folder, retrieve_names)

    def start_machine(self, machine_id: str, as_async: bool = True) -> typing.Optional[str]:
        """
        Tries to start a machine. No check is done, it is simply requested to XenServer.

        This start also "resume" suspended/paused machines

        Args:
            machineId: Id of the machine

        Returns:
        """
        return self._get_api().start_machine(machine_id, as_async)

    def stop_machine(self, machine_id: str, as_async: bool = True) -> typing.Optional[str]:
        """
        Tries to start a machine. No check is done, it is simply requested to XenServer

        Args:
            machineId: Id of the machine

        Returns:
        """
        return self._get_api().stop_machine(machine_id, as_async)

    def reset_machine(self, machine_id: str, as_async: bool = True) -> typing.Optional[str]:
        """
        Tries to start a machine. No check is done, it is simply requested to XenServer

        Args:
            machineId: Id of the machine

        Returns:
        """
        return self._get_api().reset_machine(machine_id, as_async)

    def can_suspend_machine(self, machine_id: str) -> bool:
        """
        The machine can be suspended only when "suspend" is in their operations list (mush have xentools installed)

        Args:
            machineId: Id of the machine

        Returns:
            True if the machien can be suspended
        """
        return self._get_api().can_suspend_machine(machine_id)

    def suspend_machine(self, machine_id: str, as_async: bool = True) -> typing.Optional[str]:
        """
        Tries to start a machine. No check is done, it is simply requested to XenServer

        Args:
            machineId: Id of the machine

        Returns:
        """
        return self._get_api().suspend_machine(machine_id, as_async)

    def resume_machine(self, machine_id: str, as_async: bool = True) -> typing.Optional[str]:
        """
        Tries to start a machine. No check is done, it is simply requested to XenServer

        Args:
            machineId: Id of the machine

        Returns:
        """
        return self._get_api().resume_machine(machine_id, as_async)

    def shutdown_machine(self, machine_id: str, as_async: bool = True) -> typing.Optional[str]:
        """
        Tries to start a machine. No check is done, it is simply requested to XenServer

        Args:
            machineId: Id of the machine

        Returns:
        """
        return self._get_api().shutdown_machine(machine_id, as_async)

    def remove_machine(self, machine_id: str) -> None:
        """
        Tries to delete a machine. No check is done, it is simply requested to XenServer

        Args:
            machineId: Id of the machine

        Returns:
        """
        self._get_api().remove_machine(machine_id)

    def configure_machine(self, machine_id: str, netId: str, mac: str, memory: int) -> None:
        self._get_api().configure_machine(machine_id, mac={'network': netId, 'mac': mac}, memory=memory)

    def provision_machine(self, machine_id: str, as_async: bool = True) -> str:
        return self._get_api().provision_machine(machine_id, as_async=as_async)

    def get_first_ip(self, machine_id: str) -> str:
        return self._get_api().get_first_ip(machine_id)

    def get_first_mac(self, machine_id: str) -> str:
        return self._get_api().get_first_mac(machine_id)

    def create_snapshot(self, machine_id: str, name: str) -> str:
        return self._get_api().create_snapshot(machine_id, name)

    def restore_snapshot(self, snapshot_id: str) -> str:
        return self._get_api().restore_snapshot(snapshot_id)

    def remove_snapshot(self, snapshot_id: str) -> str:
        return self._get_api().remove_snapshot(snapshot_id)

    def list_snapshots(self, machine_id: str, full_info: bool = False) -> list[dict[str, typing.Any]]:
        return self._get_api().list_snapshots(machine_id)

    def get_macs_range(self) -> str:
        return self.macs_range.value

    @cached('reachable', consts.cache.SHORT_CACHE_TIMEOUT, key_helper=lambda x: x.host.as_str())
    def is_available(self) -> bool:
        try:
            self.test_connection()
            return True
        except Exception:
            return False

    @staticmethod
    def test(env: 'environment.Environment', data: 'types.core.ValuesType') -> 'types.core.TestResult':
        """
        Test XenServer Connectivity

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
        xe = XenProvider(env, data)
        try:
            xe.test_connection()
            return types.core.TestResult(True, _('Connection test successful'))
        except Exception as e:
            return types.core.TestResult(False, _('Connection failed: {}').format(str(e)))
