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
#      and/or other materials provided with the distributiopenStack.
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permissiopenStack.
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
Created on Jun 22, 2012

.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
'''
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _
from uds.core.services import ServiceProvider
from uds.core.ui import gui
from uds.core.util import validators

from .LiveService import LiveService
from . import openStack

import logging

__updated__ = '2016-04-25'

logger = logging.getLogger(__name__)

INTERFACE_VALUES = [
    gui.choiceItem('public', 'public'),
    gui.choiceItem('private', 'private'),
    gui.choiceItem('admin', 'admin'),
]

class Provider(ServiceProvider):
    '''
    This class represents the sample services provider

    In this class we provide:
       * The Provider functionality
       * The basic configuration parameters for the provider
       * The form fields needed by administrators to configure this provider

       :note: At class level, the translation must be simply marked as so
       using ugettext_noop. This is so cause we will translate the string when
       sent to the administration client.

    For this class to get visible at administration client as a provider type,
    we MUST register it at package __init__.

    '''
    # : What kind of services we offer, this are classes inherited from Service
    offers = [LiveService]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    typeName = _('OpenStack Platform Provider')
    # : Type used internally to identify this provider
    typeType = 'openStackPlatform'
    # : Description shown at administration interface for this provider
    typeDescription = _('OpenStack platform service provider')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    iconFile = 'provider.png'

    # now comes the form fields
    # There is always two fields that are requested to the admin, that are:
    # Service Name, that is a name that the admin uses to name this provider
    # Description, that is a short description that the admin gives to this provider
    # Now we are going to add a few fields that we need to use this provider
    # Remember that these are "dummy" fields, that in fact are not required
    # but used for sample purposes
    # If we don't indicate an order, the output order of fields will be
    # "random"
    host = gui.TextField(length=64, label=_('Host'), order=1, tooltip=_('OpenStack Host'), required=True)
    port = gui.NumericField(length=5, label=_('Port'), defvalue='5000', order=2, tooltip=_('OpenStack Port'), required=True)
    ssl = gui.CheckBoxField(label=_('Use SSL'), order=3, tooltip=_('If checked, the connection will be forced to be ssl (will not work if server is not providing ssl)'))

    access = gui.ChoiceField(label=_('Access interface'), order=4, tooltip=_('Access interface to be used'), values=INTERFACE_VALUES, defvalue='public')

    domain = gui.TextField(length=64, label=_('Domain'), order=8, tooltip=_('Domain name (default is Default)'), required=True, defvalue='Default')
    username = gui.TextField(length=64, label=_('Username'), order=9, tooltip=_('User with valid privileges on OpenStack'), required=True, defvalue='admin')
    password = gui.PasswordField(lenth=32, label=_('Password'), order=10, tooltip=_('Password of the user of OpenStack'), required=True)

    maxPreparingServices = gui.NumericField(length=3, label=_('Creation concurrency'), defvalue='10', minValue=1, maxValue=65536, order=50, tooltip=_('Maximum number of concurrently creating VMs'), required=True, tab=gui.ADVANCED_TAB)
    maxRemovingServices = gui.NumericField(length=3, label=_('Removal concurrency'), defvalue='5', minValue=1, maxValue=65536, order=51, tooltip=_('Maximum number of concurrently removing VMs'), required=True, tab=gui.ADVANCED_TAB)

    timeout = gui.NumericField(length=3, label=_('Timeout'), defvalue='10', minValue=1, maxValue=128, order=99, tooltip=_('Timeout in seconds of connection to OpenStack'), required=True, tab=gui.ADVANCED_TAB)


    # tenant = gui.TextField(length=64, label=_('Project'), order=6, tooltip=_('Project (tenant) for this provider'), required=True, defvalue='')
    # region = gui.TextField(length=64, label=_('Region'), order=7, tooltip=_('Region for this provider'), required=True, defvalue='RegionOne')

    # Own variables
    _api = None

    def initialize(self, values=None):
        '''
        We will use the "autosave" feature for form fields
        '''
        # Just reset _api connection variable

        if values is not None:
            self.timeout.value = validators.validateTimeout(self.timeout.value, returnAsInteger=False)

    def api(self, projectId=None, region=None):
        return openStack.Client(self.host.value, self.port.value,
                                     self.domain.value, self.username.value, self.password.value,
                                     useSSL=self.ssl.isTrue(),
                                     projectId=projectId,
                                     region=region,
                                     access=self.access.value)

    def sanitizeVmName(self, name):
        return openStack.sanitizeName(name)

    def testConnection(self):
        '''
        Test that conection to OpenStack server is fine

        Returns

            True if all went fine, false if id didn't
        '''

        try:
            if self.api().testConnection() is False:
                raise Exception('Check connection credentials, server, etc.')
        except Exception as e:
            return [False, '{}'.format(e)]

        return [True, _('OpenStack test connection passed')]

    @staticmethod
    def test(env, data):
        '''
        Test ovirt Connectivity

        Args:
            env: environment passed for testing (temporal environment passed)

            data: data passed for testing (data obtained from the form
            definition)

        Returns:
            Array of two elements, first is True of False, depending on test
            (True is all right, false is error),
            second is an String with error, preferably internacionalizated..

        '''
        return Provider(env, data).testConnection()
