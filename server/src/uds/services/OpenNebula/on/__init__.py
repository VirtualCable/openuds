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

'''
.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''

import sys
import imp
import re

import logging
import six

import xmlrpclib
from uds.core.util import xml2dict

__updated__ = '2016-07-11'

logger = logging.getLogger(__name__)


module = sys.modules[__name__]
VmState = imp.new_module('VmState')

for i in enumerate(['INIT', 'PENDING', 'HOLD', 'ACTIVE', 'STOPPED', 'SUSPENDED', 'DONE', 'FAILED', 'POWEROFF', 'UNDEPLOYED']):
    setattr(VmState, i[1], i[0])


# Import submodules
from .common import *
from . import template
from . import vm
from . import storage

# Decorator
def ensureConnected(fnc):
    def inner(*args, **kwargs):
        args[0].connect()
        return fnc(*args, **kwargs)
    return inner

# Result checker
def checkResult(lst, parseResult=True):
    if lst[0] == False:
        raise Exception('OpenNebula error {}: "{}"'.format(lst[2], lst[1]))
    if parseResult:
        return xml2dict.parse(lst[1])
    else:
        return lst[1]

def asList(element):
    if isinstance(element, (tuple, list)):
        return element
    return (element,)

class OpenNebulaClient(object):
    def __init__(self, username, password, endpoint):
        self.username = username
        self.password = password
        self.endpoint = endpoint
        self.connection = None

    @property
    def sessionString(self):
        return '{}:{}'.format(self.username, self.password)


    def connect(self):
        if self.connection is not None:
            return

        self.connection = xmlrpclib.ServerProxy(self.endpoint)

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
        # Invoke templates pools info, with this parameters:
        # 1.- Session string
        # 2.- Filter flag - < = -3: Connected user’s resources - -2: All resources - -1: Connected user’s and his group’s resources - > = 0: UID User’s Resources
        # 3.- When the next parameter is >= -1 this is the Range start ID. Can be -1. For smaller values this is the offset used for pagination.
        # 4.- For values >= -1 this is the Range end ID. Can be -1 to get until the last ID. For values < -1 this is the page size used for pagination.
        result = self.connection.one.templatepool.info(self.sessionString, -3, -1, -1)
        result = checkResult(result)
        for ds in asList(result['VMTEMPLATE_POOL']['VMTEMPLATE']):
            yield(ds['ID'], ds['NAME'], ds['TEMPLATE']['MEMORY'])

    @ensureConnected
    def templateInfo(self, templateId, extraInfo=False):
        '''
        Returns a list
        first element is a dictionary (built from XML)
        second is original XML
        '''
        result = self.connection.one.template.info(self.sessionString, int(templateId), extraInfo)
        res = checkResult(result)
        return (res, result[1])

    @ensureConnected
    def cloneImage(self, srcId, name, datastoreId=-1):
        result = self.connection.one.image.clone(self.sessionString, int(srcId), name, int(datastoreId))
        return checkResult(result, parseResult=False)
