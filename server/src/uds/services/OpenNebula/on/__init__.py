# -*- coding: utf-8 -*-

#
# Copyright (c) 2012 Virtual Cable S.L.
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

"""
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""

# pylint: disable=maybe-no-member

import six

from uds.core.util import xml2dict
from . import storage
from . import template
from . import vm
# Import submodules
from .common import *
import types

__updated__ = '2017-03-28'

logger = logging.getLogger(__name__)

module = sys.modules[__name__]
VmState = types.ModuleType('VmState')
ImageState = types.ModuleType('ImageState')

for i in enumerate(['INIT', 'PENDING', 'HOLD', 'ACTIVE', 'STOPPED', 'SUSPENDED', 'DONE', 'FAILED', 'POWEROFF', 'UNDEPLOYED']):
    setattr(VmState, i[1], i[0])

for i in enumerate(['INIT', 'READY', 'USED', 'DISABLED', 'LOCKED', 'ERROR', 'CLONE', 'DELETE', 'USED_PERS', 'LOCKED_USED', 'LOCKED_USED_PERS']):
    setattr(ImageState, i[1], i[0])


# Decorator
def ensureConnected(fnc):
    def inner(*args, **kwargs):
        args[0].connect()
        return fnc(*args, **kwargs)
    return inner


# Result checker
def checkResult(lst, parseResult=True):
    if not lst[0]:
        raise Exception('OpenNebula error {}: "{}"'.format(lst[2], lst[1]))
    if parseResult:
        return xml2dict.parse(lst[1])
    else:
        return lst[1]


def asList(element):
    if isinstance(element, (tuple, list)):
        return element
    return element,


class OpenNebulaClient(object):
    def __init__(self, username, password, endpoint):
        self.username = username
        self.password = password
        self.endpoint = endpoint
        self.connection = None
        self.cachedVersion = None

    @property
    def sessionString(self):
        return '{}:{}'.format(self.username, self.password)

    @property
    @ensureConnected
    def version(self):
        if self.cachedVersion is None:
            # Retrieve Version & keep it
            result = self.connection.one.system.version(self.sessionString)
            self.cachedVersion = checkResult(result, parseResult=False).split('.')
        return self.cachedVersion

    def connect(self):
        if self.connection is not None:
            return

        self.connection = six.moves.xmlrpc_client.ServerProxy(self.endpoint)  # @UndefinedVariable

    @ensureConnected
    def enumStorage(self, storageType=0):
        storageType = six.text_type(storageType)  # Ensure it is an string
        # Invoke datastore pools info, no parameters except connection string
        result = self.connection.one.datastorepool.info(self.sessionString)
        result = checkResult(result)
        for ds in asList(result['DATASTORE_POOL']['DATASTORE']):
            if ds['TYPE'] == storageType:
                yield(ds['ID'], ds['NAME'], ds['TOTAL_MB'], ds['FREE_MB'])

    @ensureConnected
    def enumTemplates(self):
        """
        Invoke templates pools info, with this parameters:
        1.- Session string
        2.- Filter flag - < = -3: Connected user’s resources - -2: All resources - -1: Connected user’s and his group’s resources - > = 0: UID User’s Resources
        3.- When the next parameter is >= -1 this is the Range start ID. Can be -1. For smaller values this is the offset used for pagination.
        4.- For values >= -1 this is the Range end ID. Can be -1 to get until the last ID. For values < -1 this is the page size used for pagination.
        """
        result = self.connection.one.templatepool.info(self.sessionString, -1, -1, -1)
        result = checkResult(result)
        for ds in asList(result['VMTEMPLATE_POOL']['VMTEMPLATE']):
            try:
                yield(ds['ID'], ds['NAME'], ds['TEMPLATE']['MEMORY'])
            except Exception:  # Maybe no memory? (then template is not usable)
                pass

    @ensureConnected
    def enumImages(self):
        """
        Invoke images pools info, with this parameters:
        1.- Session string
        2.- Filter flag - < = -3: Connected user’s resources - -2: All resources - -1: Connected user’s and his group’s resources - > = 0: UID User’s Resources
        3.- When the next parameter is >= -1 this is the Range start ID. Can be -1. For smaller values this is the offset used for pagination.
        4.- For values >= -1 this is the Range end ID. Can be -1 to get until the last ID. For values < -1 this is the page size used for pagination.
        """
        result = self.connection.one.imagepool.info(self.sessionString, -1, -1, -1)
        result = checkResult(result)
        for ds in asList(result['IMAGE_POOL']['IMAGE']):
            yield(ds['ID'], ds['NAME'])

    @ensureConnected
    def templateInfo(self, templateId, extraInfo=False):
        """
        Returns a list
        first element is a dictionary (built from XML)
        second is original XML
        """
        result = self.connection.one.template.info(self.sessionString, int(templateId), extraInfo)
        res = checkResult(result)
        return res, result[1]

    @ensureConnected
    def instantiateTemplate(self, templateId, vmName, createHold=False, templateToMerge='', privatePersistent=False):
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
        if self.version[0] == '4':  # Version 4 has one less parameter than version 5
            result = self.connection.one.template.instantiate(self.sessionString, int(templateId), vmName, createHold, templateToMerge)
        else:
            result = self.connection.one.template.instantiate(self.sessionString, int(templateId), vmName, createHold, templateToMerge, privatePersistent)

        return checkResult(result, parseResult=False)

    @ensureConnected
    def updateTemplate(self, templateId, template, updateType=0):
        """
        Updates the template with the templateXml
        1.- Session string
        2.- Object ID (integer)
        3.- The new template contents. Syntax can be the usual attribute=value or XML.
        4.- Update type. 0 replace the whole template, 1 merge with the existing one
        """
        result = self.connection.one.template.update(self.sessionString, int(templateId), template, int(updateType))
        return checkResult(result, parseResult=False)

    @ensureConnected
    def cloneTemplate(self, templateId, name):
        """
        Clones the template
        """
        if self.version[0] == '4':
            result = self.connection.one.template.clone(self.sessionString, int(templateId), name)
        else:
            result = self.connection.one.template.clone(self.sessionString, int(templateId), name, False)  # This works as previous version clone

        return checkResult(result, parseResult=False)

    @ensureConnected
    def deleteTemplate(self, templateId):
        """
        """
        result = self.connection.one.template.delete(self.sessionString, int(templateId))
        return checkResult(result, parseResult=False)

    @ensureConnected
    def cloneImage(self, srcId, name, datastoreId=-1):
        """
        Clones the image.
        """
        result = self.connection.one.image.clone(self.sessionString, int(srcId), name, int(datastoreId))
        return checkResult(result, parseResult=False)

    @ensureConnected
    def makePersistentImage(self, imageId, persistent=False):
        """
        Clones the image.
        """
        result = self.connection.one.image.persistent(self.sessionString, int(imageId), persistent)
        return checkResult(result, parseResult=False)

    @ensureConnected
    def deleteImage(self, imageId):
        """
        Deletes an image
        """
        result = self.connection.one.image.delete(self.sessionString, int(imageId))
        return checkResult(result, parseResult=False)

    @ensureConnected
    def imageInfo(self, imageInfo):
        """
        Returns a list
        first element is a dictionary (built from XML)
        second is original XML
        """
        result = self.connection.one.image.info(self.sessionString, int(imageInfo))
        res = checkResult(result)
        return res, result[1]

    @ensureConnected
    def enumVMs(self):
        """
        Invoke vm pools info, with this parameters:
        1.- Session string
        2.- Filter flag - < = -3: Connected user’s resources - -2: All resources - -1: Connected user’s and his group’s resources - > = 0: UID User’s Resources
        3.- When the next parameter is >= -1 this is the Range start ID. Can be -1. For smaller values this is the offset used for pagination.
        4.- For values >= -1 this is the Range end ID. Can be -1 to get until the last ID. For values < -1 this is the page size used for pagination.
        5.- VM state to filter by. (-2 = any state including DONE, -1 = any state EXCEPT DONE)
        """
        result = self.connection.one.vmpool.info(self.sessionString, -1, -1, -1, -1)
        result = checkResult(result)
        for ds in asList(result['VM_POOL']['VM']):
            yield(ds['ID'], ds['NAME'])

    @ensureConnected
    def VMInfo(self, vmId):
        """
        Returns a list
        first element is a dictionary (built from XML)
        second is original XML
        """
        result = self.connection.one.vm.info(self.sessionString, int(vmId))
        res = checkResult(result)
        return res, result[1]

    @ensureConnected
    def deleteVM(self, vmId):
        """
        Deletes an vm
        """
        if self.version[0] == '4':
            return self.VMAction(vmId, 'delete')
        else:
            # Version 5
            return self.VMAction(vmId, 'terminate-hard')

    @ensureConnected
    def getVMState(self, vmId):
        """
        Returns the VM State
        """
        result = self.connection.one.vm.info(self.sessionString, int(vmId))
        return int(checkResult(result)['VM']['STATE'])

    @ensureConnected
    def getVMSubstate(self, vmId):
        """
        Returns the VM State
        """
        result = self.connection.one.vm.info(self.sessionString, int(vmId))
        r = checkResult(result)
        try:
            if int(r['VM']['STATE']) == VmState.ACTIVE:
                return int(r['VM']['LCM_STATE'])
            # Substate is not available if VM state is not active
            return -1
        except Exception:
            logger.exception('getVMSubstate')
            return -1

    @ensureConnected
    def VMAction(self, vmId, action):
        result = self.connection.one.vm.action(self.sessionString, action, int(vmId))
        return checkResult(result, parseResult=False)
