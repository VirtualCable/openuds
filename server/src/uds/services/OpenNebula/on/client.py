# -*- coding: utf-8 -*-

#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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

# pylint: disable=maybe-no-member
import xmlrpc.client
import logging
import typing
import collections.abc

from uds.core.util import ensure, xml2dict

from . import types

logger = logging.getLogger(__name__)

RT = typing.TypeVar('RT')


# Decorator
def ensure_connected(fnc: collections.abc.Callable[..., RT]) -> collections.abc.Callable[..., RT]:
    def inner(obj: 'OpenNebulaClient', *args: typing.Any, **kwargs: typing.Any) -> RT:
        obj.connect()
        return fnc(obj, *args, **kwargs)

    return inner


# Result checker
def check_result_raw(lst: typing.Any) -> str:
    # Openebula response is always this way:
    # [Boolean, String, ErrorCode]
    # First is True if ok, False if not
    # Second is Result String if was ok
    # Third is error code if first is False
    if not lst[0]:
        raise Exception('OpenNebula error {}: "{}"'.format(lst[2], lst[1]))

    return str(lst[1])


def check_result(lst: typing.Any) -> tuple[collections.abc.Mapping[str, typing.Any], str]:
    return xml2dict.parse(check_result_raw(lst)), lst[1]


as_iterable = ensure.as_iterable


class OpenNebulaClient:  # pylint: disable=too-many-public-methods
    username: str
    password: str
    endpoint: str
    connection: xmlrpc.client.ServerProxy
    cached_version: typing.Optional[list[str]]

    def __init__(self, username: str, password: str, endpoint: str) -> None:
        self.username = username
        self.password = password
        self.endpoint = endpoint
        # Connection "None" will be treated on ensureConnected, ignore its assignement here
        self.connection = None  # type: ignore
        self.cached_version = None

    @property
    def session_string(self) -> str:
        return '{}:{}'.format(self.username, self.password)

    @property
    @ensure_connected
    def version(self) -> list[str]:
        if self.cached_version is None:
            # Retrieve Version & keep it
            result = self.connection.one.system.version(self.session_string)
            self.cached_version = check_result_raw(result).split('.')
        return self.cached_version

    def connect(self) -> None:
        if self.connection:
            return

        self.connection = xmlrpc.client.ServerProxy(self.endpoint)

    @ensure_connected
    def enum_storage(self, storage_type: int = 0) -> collections.abc.Iterable[types.StorageType]:
        sstorage_type = str(storage_type)  # Ensure it is an string
        # Invoke datastore pools info, no parameters except connection string
        result, _ = check_result(self.connection.one.datastorepool.info(self.session_string))
        for ds in as_iterable(result['DATASTORE_POOL']['DATASTORE']):
            if ds['TYPE'] == sstorage_type:
                yield types.StorageType(ds['ID'], ds['NAME'], int(ds['TOTAL_MB']), int(ds['FREE_MB']), None)

    @ensure_connected
    def enum_templates(self) -> collections.abc.Iterable[types.TemplateType]:
        """
        Invoke templates pools info, with this parameters:
        1.- Session string
        2.- Filter flag - < = -3: Connected user’s resources - -2: All resources - -1: Connected user’s and his group’s resources - > = 0: UID User’s Resources
        3.- When the next parameter is >= -1 this is the Range start ID. Can be -1. For smaller values this is the offset used for pagination.
        4.- For values >= -1 this is the Range end ID. Can be -1 to get until the last ID. For values < -1 this is the page size used for pagination.
        """
        result, _ = check_result(self.connection.one.templatepool.info(self.session_string, -1, -1, -1))
        for ds in as_iterable(result['VMTEMPLATE_POOL']['VMTEMPLATE']):
            try:
                yield types.TemplateType(ds['ID'], ds['NAME'], int(ds['TEMPLATE']['MEMORY']), None)
            except Exception:  # Maybe no memory? (then template is not usable)
                pass

    @ensure_connected
    def enum_images(self) -> collections.abc.Iterable[types.ImageType]:
        """
        Invoke images pools info, with this parameters:
        1.- Session string
        2.- Filter flag - < = -3: Connected user’s resources - -2: All resources - -1: Connected user’s and his group’s resources - > = 0: UID User’s Resources
        3.- When the next parameter is >= -1 this is the Range start ID. Can be -1. For smaller values this is the offset used for pagination.
        4.- For values >= -1 this is the Range end ID. Can be -1 to get until the last ID. For values < -1 this is the page size used for pagination.
        """
        result, _ = check_result(self.connection.one.imagepool.info(self.session_string, -1, -1, -1))
        for ds in as_iterable(result['IMAGE_POOL']['IMAGE']):
            yield types.ImageType(
                ds['ID'],
                ds['NAME'],
                int(ds.get('SIZE', -1)),
                ds.get('PERSISTENT', '0') != '0',
                int(ds.get('RUNNING_VMS', '0')),
                types.ImageState.from_str(ds['STATE']),
                None,
            )

    @ensure_connected
    def template_info(self, template_id: str, extra_info: bool = False) -> types.TemplateType:
        """
        Returns a list
        first element is a dictionary (built from XML)
        second is original XML
        """
        result = self.connection.one.template.info(self.session_string, int(template_id), extra_info)
        ds, xml = check_result(result)
        return types.TemplateType(
            ds['VMTEMPLATE']['ID'],
            ds['VMTEMPLATE']['NAME'],
            int(ds['VMTEMPLATE']['TEMPLATE']['MEMORY']),
            xml,
        )

    @ensure_connected
    def instantiate_template(
        self,
        template_id: str,
        vm_name: str,
        create_hold: bool = False,
        template_to_merge: str = '',
        private_persistent: bool = False,
    ) -> str:
        """
        Instantiates a template (compatible with open nebula 4 & 5)
        1.- Session string
        2.- ID Of the template to instantiate
        3.- Name of the vm. If empty, open nebula will assign one
        4.- False to create machine on pending (default), True to create it on hold
        5.- A string containing an extra template to be merged with the one being instantiated. It can be empty. Syntax can be the usual attribute=value or XML.
        6.- true to create a private persistent copy of the template plus any image defined in DISK, and instantiate that copy.
            Note: This parameter is ignored on version 4, it is new for version 5.
        """
        if self.version[0] == '4':
            result = self.connection.one.template.instantiate(
                self.session_string, int(template_id), vm_name, create_hold, template_to_merge
            )
        else:
            result = self.connection.one.template.instantiate(
                self.session_string,
                int(template_id),
                vm_name,
                create_hold,
                template_to_merge,
                private_persistent,
            )

        return check_result_raw(result)

    @ensure_connected
    def update_template(self, template_id: str, template_data: str, update_type: int = 0) -> str:
        """
        Updates the template with the templateXml
        1.- Session string
        2.- Object ID (integer)
        3.- The new template contents. Syntax can be the usual attribute=value or XML.
        4.- Update type. 0 replace the whole template, 1 merge with the existing one
        """
        result = self.connection.one.template.update(
            self.session_string, int(template_id), template_data, int(update_type)
        )
        return check_result_raw(result)

    @ensure_connected
    def clone_template(self, template_id: str, name: str) -> str:
        """
        Clones the template
        """
        if self.version[0] == '4':
            result = self.connection.one.template.clone(self.session_string, int(template_id), name)
        else:
            result = self.connection.one.template.clone(
                self.session_string, int(template_id), name, False
            )  # This works as previous version clone

        return check_result_raw(result)

    @ensure_connected
    def delete_template(self, template_id: str) -> str:
        """
        Deletes the template (not images)
        """
        result = self.connection.one.template.delete(self.session_string, int(template_id))
        return check_result_raw(result)

    @ensure_connected
    def clone_image(self, src_id: str, name: str, datastore_id: typing.Union[str, int] = -1) -> str:
        """
        Clones the image.
        """
        result = self.connection.one.image.clone(self.session_string, int(src_id), name, int(datastore_id))
        return check_result_raw(result)

    @ensure_connected
    def make_persistent_image(self, image_id: str, persistent: bool = False) -> str:
        """
        Clones the image.
        """
        result = self.connection.one.image.persistent(self.session_string, int(image_id), persistent)
        return check_result_raw(result)

    @ensure_connected
    def delete_image(self, image_id: str) -> str:
        """
        Deletes an image
        """
        result = self.connection.one.image.delete(self.session_string, int(image_id))
        return check_result_raw(result)

    @ensure_connected
    def image_info(self, imginfo: str) -> types.ImageType:
        """
        Returns a list
        first element is a dictionary (built from XML)
        second is original XML
        """
        result, xml = check_result(self.connection.one.image.info(self.session_string, int(imginfo)))
        ds = result['IMAGE']
        return types.ImageType(
            ds['ID'],
            ds['NAME'],
            int(ds.get('SIZE', -1)),
            ds.get('PERSISTENT', '0') != '0',
            int(ds.get('RUNNING_VMS', '0')),
            types.ImageState.from_str(ds['STATE']),
            xml,
        )

    @ensure_connected
    def enumerate_machines(self) -> collections.abc.Iterable[types.VirtualMachineType]:
        """
        Invoke vm pools info, with this parameters:
        1.- Session string
        2.- Filter flag - < = -3: Connected user’s resources - -2: All resources - -1: Connected user’s and his group’s resources - > = 0: UID User’s Resources
        3.- When the next parameter is >= -1 this is the Range start ID. Can be -1. For smaller values this is the offset used for pagination.
        4.- For values >= -1 this is the Range end ID. Can be -1 to get until the last ID. For values < -1 this is the page size used for pagination.
        5.- VM state to filter by. (-2 = any state including DONE, -1 = any state EXCEPT DONE)
        """
        result, _ = check_result(self.connection.one.vmpool.info(self.session_string, -1, -1, -1, -1))
        if result['VM_POOL']:
            for ds in as_iterable(result['VM_POOL'].get('VM', [])):
                yield types.VirtualMachineType(
                    ds['ID'],
                    ds['NAME'],
                    int(ds.get('MEMORY', '0')),
                    types.VmState.from_str(ds['STATE']),
                    None,
                )

    @ensure_connected
    def vm_info(self, vmid: str) -> types.VirtualMachineType:
        """
        Returns a list
        first element is a dictionary (built from XML)
        second is original XML
        """
        result, xml = check_result(self.connection.one.vm.info(self.session_string, int(vmid)))
        ds = result['VM']
        return types.VirtualMachineType(
            ds['ID'],
            ds['NAME'],
            int(ds.get('MEMORY', '0')),
            types.VmState.from_str(ds['STATE']),
            xml,
        )

    @ensure_connected
    def remove_machine(self, vmid: str) -> str:
        """
        Deletes an vm
        """
        if self.version[0] == '4':
            return self.set_machine_state(vmid, 'delete')

        # Version 5
        return self.set_machine_state(vmid, 'terminate-hard')

    @ensure_connected
    def get_machine_state(self, vmid: str) -> types.VmState:
        """
        Returns the VM State
        """
        return self.vm_info(vmid).state

    @ensure_connected
    def get_machine_substate(self, vmid: str) -> int:
        """
        Returns the VM State
        """
        result = self.connection.one.vm.info(self.session_string, int(vmid))
        r, _ = check_result(result)
        try:
            if int(r['VM']['STATE']) == types.VmState.ACTIVE.value:
                return int(r['VM']['LCM_STATE'])
            # Substate is not available if VM state is not active
            return -1
        except Exception:
            logger.exception('getVMSubstate')
            return -1

    @ensure_connected
    def set_machine_state(self, vmid: str, action: str) -> str:
        result = self.connection.one.vm.action(self.session_string, action, int(vmid))
        return check_result_raw(result)
