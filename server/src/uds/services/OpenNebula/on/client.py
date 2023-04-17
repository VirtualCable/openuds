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

from uds.core.util import xml2dict

from . import types

logger = logging.getLogger(__name__)

RT = typing.TypeVar('RT')

# Decorator
def ensureConnected(fnc: typing.Callable[..., RT]) -> typing.Callable[..., RT]:
    def inner(*args, **kwargs) -> RT:
        args[0].connect()
        return fnc(*args, **kwargs)

    return inner


# Result checker
def checkResultRaw(lst: typing.Any) -> str:
    # Openebula response is always this way:
    # [Boolean, String, ErrorCode]
    # First is True if ok, False if not
    # Second is Result String if was ok
    # Third is error code if first is False
    if not lst[0]:
        raise Exception('OpenNebula error {}: "{}"'.format(lst[2], lst[1]))

    return str(lst[1])


def checkResult(lst: typing.Any) -> typing.Tuple[typing.Mapping[str, typing.Any], str]:
    return xml2dict.parse(checkResultRaw(lst)), lst[1]


def asIterable(element: RT) -> typing.Iterable[RT]:
    if isinstance(element, (tuple, list)):
        return element
    return (element,)


class OpenNebulaClient:  # pylint: disable=too-many-public-methods
    username: str
    password: str
    endpoint: str
    connection: xmlrpc.client.ServerProxy
    cachedVersion: typing.Optional[typing.List[str]]

    def __init__(self, username: str, password: str, endpoint: str) -> None:
        self.username = username
        self.password = password
        self.endpoint = endpoint
        # Connection "None" will be treated on ensureConnected, ignore its assignement here
        self.connection = None  # type: ignore
        self.cachedVersion = None

    @property
    def sessionString(self):
        return '{}:{}'.format(self.username, self.password)

    @property  # type: ignore
    @ensureConnected
    def version(self) -> typing.List[str]:
        if self.cachedVersion is None:
            # Retrieve Version & keep it
            result = self.connection.one.system.version(self.sessionString)
            self.cachedVersion = checkResultRaw(result).split('.')
        return self.cachedVersion

    def connect(self) -> None:
        if self.connection is not None:
            return

        self.connection = xmlrpc.client.ServerProxy(self.endpoint)

    @ensureConnected
    def enumStorage(self, storageType: int = 0) -> typing.Iterable[types.StorageType]:
        sstorageType = str(storageType)  # Ensure it is an string
        # Invoke datastore pools info, no parameters except connection string
        result, _ = checkResult(
            self.connection.one.datastorepool.info(self.sessionString)
        )
        for ds in asIterable(result['DATASTORE_POOL']['DATASTORE']):
            if ds['TYPE'] == sstorageType:
                yield types.StorageType(
                    ds['ID'], ds['NAME'], int(ds['TOTAL_MB']), int(ds['FREE_MB']), None
                )

    @ensureConnected
    def enumTemplates(self) -> typing.Iterable[types.TemplateType]:
        """
        Invoke templates pools info, with this parameters:
        1.- Session string
        2.- Filter flag - < = -3: Connected user’s resources - -2: All resources - -1: Connected user’s and his group’s resources - > = 0: UID User’s Resources
        3.- When the next parameter is >= -1 this is the Range start ID. Can be -1. For smaller values this is the offset used for pagination.
        4.- For values >= -1 this is the Range end ID. Can be -1 to get until the last ID. For values < -1 this is the page size used for pagination.
        """
        result, _ = checkResult(
            self.connection.one.templatepool.info(self.sessionString, -1, -1, -1)
        )
        for ds in asIterable(result['VMTEMPLATE_POOL']['VMTEMPLATE']):
            try:
                yield types.TemplateType(
                    ds['ID'], ds['NAME'], int(ds['TEMPLATE']['MEMORY']), None
                )
            except Exception:  # Maybe no memory? (then template is not usable)
                pass

    @ensureConnected
    def enumImages(self) -> typing.Iterable[types.ImageType]:
        """
        Invoke images pools info, with this parameters:
        1.- Session string
        2.- Filter flag - < = -3: Connected user’s resources - -2: All resources - -1: Connected user’s and his group’s resources - > = 0: UID User’s Resources
        3.- When the next parameter is >= -1 this is the Range start ID. Can be -1. For smaller values this is the offset used for pagination.
        4.- For values >= -1 this is the Range end ID. Can be -1 to get until the last ID. For values < -1 this is the page size used for pagination.
        """
        result, _ = checkResult(
            self.connection.one.imagepool.info(self.sessionString, -1, -1, -1)
        )
        for ds in asIterable(result['IMAGE_POOL']['IMAGE']):
            yield types.ImageType(
                ds['ID'],
                ds['NAME'],
                int(ds.get('SIZE', -1)),
                ds.get('PERSISTENT', '0') != '0',
                int(ds.get('RUNNING_VMS', '0')),
                types.ImageState.fromState(ds['STATE']),
                None,
            )

    @ensureConnected
    def templateInfo(
        self, templateId: str, extraInfo: bool = False
    ) -> types.TemplateType:
        """
        Returns a list
        first element is a dictionary (built from XML)
        second is original XML
        """
        result = self.connection.one.template.info(
            self.sessionString, int(templateId), extraInfo
        )
        ds, xml = checkResult(result)
        return types.TemplateType(
            ds['VMTEMPLATE']['ID'],
            ds['VMTEMPLATE']['NAME'],
            int(ds['VMTEMPLATE']['TEMPLATE']['MEMORY']),
            xml,
        )

    @ensureConnected
    def instantiateTemplate(
        self,
        templateId: str,
        vmName: str,
        createHold: bool = False,
        templateToMerge: str = '',
        privatePersistent: bool = False,
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
        if self.version[0] == '4':  # type: ignore  # Version 4 has one less parameter than version 5
            result = self.connection.one.template.instantiate(
                self.sessionString, int(templateId), vmName, createHold, templateToMerge
            )
        else:
            result = self.connection.one.template.instantiate(
                self.sessionString,
                int(templateId),
                vmName,
                createHold,
                templateToMerge,
                privatePersistent,
            )

        return checkResultRaw(result)

    @ensureConnected
    def updateTemplate(
        self, templateId: str, templateData: str, updateType: int = 0
    ) -> str:
        """
        Updates the template with the templateXml
        1.- Session string
        2.- Object ID (integer)
        3.- The new template contents. Syntax can be the usual attribute=value or XML.
        4.- Update type. 0 replace the whole template, 1 merge with the existing one
        """
        result = self.connection.one.template.update(
            self.sessionString, int(templateId), templateData, int(updateType)
        )
        return checkResultRaw(result)

    @ensureConnected
    def cloneTemplate(self, templateId: str, name: str) -> str:
        """
        Clones the template
        """
        if self.version[0] == '4':  # type: ignore
            result = self.connection.one.template.clone(
                self.sessionString, int(templateId), name
            )
        else:
            result = self.connection.one.template.clone(
                self.sessionString, int(templateId), name, False
            )  # This works as previous version clone

        return checkResultRaw(result)

    @ensureConnected
    def deleteTemplate(self, templateId: str) -> str:
        """
        Deletes the template (not images)
        """
        result = self.connection.one.template.delete(
            self.sessionString, int(templateId)
        )
        return checkResultRaw(result)

    @ensureConnected
    def cloneImage(
        self, srcId: str, name: str, datastoreId: typing.Union[str, int] = -1
    ) -> str:
        """
        Clones the image.
        """
        result = self.connection.one.image.clone(
            self.sessionString, int(srcId), name, int(datastoreId)
        )
        return checkResultRaw(result)

    @ensureConnected
    def makePersistentImage(self, imageId: str, persistent: bool = False) -> str:
        """
        Clones the image.
        """
        result = self.connection.one.image.persistent(
            self.sessionString, int(imageId), persistent
        )
        return checkResultRaw(result)

    @ensureConnected
    def deleteImage(self, imageId: str) -> str:
        """
        Deletes an image
        """
        result = self.connection.one.image.delete(self.sessionString, int(imageId))
        return checkResultRaw(result)

    @ensureConnected
    def imageInfo(self, imageInfo) -> types.ImageType:
        """
        Returns a list
        first element is a dictionary (built from XML)
        second is original XML
        """
        result, xml = checkResult(
            self.connection.one.image.info(self.sessionString, int(imageInfo))
        )
        ds = result['IMAGE']
        return types.ImageType(
            ds['ID'],
            ds['NAME'],
            int(ds.get('SIZE', -1)),
            ds.get('PERSISTENT', '0') != '0',
            int(ds.get('RUNNING_VMS', '0')),
            types.ImageState.fromState(ds['STATE']),
            xml,
        )

    @ensureConnected
    def enumVMs(self) -> typing.Iterable[types.VirtualMachineType]:
        """
        Invoke vm pools info, with this parameters:
        1.- Session string
        2.- Filter flag - < = -3: Connected user’s resources - -2: All resources - -1: Connected user’s and his group’s resources - > = 0: UID User’s Resources
        3.- When the next parameter is >= -1 this is the Range start ID. Can be -1. For smaller values this is the offset used for pagination.
        4.- For values >= -1 this is the Range end ID. Can be -1 to get until the last ID. For values < -1 this is the page size used for pagination.
        5.- VM state to filter by. (-2 = any state including DONE, -1 = any state EXCEPT DONE)
        """
        result, _ = checkResult(
            self.connection.one.vmpool.info(self.sessionString, -1, -1, -1, -1)
        )
        if result['VM_POOL']:
            for ds in asIterable(result['VM_POOL'].get('VM', [])):
                yield types.VirtualMachineType(
                    ds['ID'],
                    ds['NAME'],
                    int(ds.get('MEMORY', '0')),
                    types.VmState.fromState(ds['STATE']),
                    None,
                )

    @ensureConnected
    def VMInfo(self, vmId: str) -> types.VirtualMachineType:
        """
        Returns a list
        first element is a dictionary (built from XML)
        second is original XML
        """
        result, xml = checkResult(
            self.connection.one.vm.info(self.sessionString, int(vmId))
        )
        ds = result['VM']
        return types.VirtualMachineType(
            ds['ID'],
            ds['NAME'],
            int(ds.get('MEMORY', '0')),
            types.VmState.fromState(ds['STATE']),
            xml,
        )

    @ensureConnected
    def deleteVM(self, vmId: str) -> str:
        """
        Deletes an vm
        """
        if self.version[0] == '4':  # type: ignore
            return self.VMAction(vmId, 'delete')

        # Version 5
        return self.VMAction(vmId, 'terminate-hard')

    @ensureConnected
    def getVMState(self, vmId: str) -> types.VmState:
        """
        Returns the VM State
        """
        return self.VMInfo(vmId).state

    @ensureConnected
    def getVMSubstate(self, vmId: str) -> int:
        """
        Returns the VM State
        """
        result = self.connection.one.vm.info(self.sessionString, int(vmId))
        r, _ = checkResult(result)
        try:
            if int(r['VM']['STATE']) == types.VmState.ACTIVE.value:
                return int(r['VM']['LCM_STATE'])
            # Substate is not available if VM state is not active
            return -1
        except Exception:
            logger.exception('getVMSubstate')
            return -1

    @ensureConnected
    def VMAction(self, vmId: str, action: str) -> str:
        result = self.connection.one.vm.action(self.sessionString, action, int(vmId))
        return checkResultRaw(result)
