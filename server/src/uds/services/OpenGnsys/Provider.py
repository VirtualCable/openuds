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
#      and/or other materials provided with the distributiog.
#    * Neither the name of Virtual Cable S.L. nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permissiog.
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
Created on Jun 22, 2012

.. moduleauthor:: Adolfo Gómez, dkmaster at dkmon dot com
"""
from __future__ import unicode_literals

from django.utils.translation import ugettext_noop as _
from uds.core.services import ServiceProvider
from uds.core.ui import gui
from uds.core.util import validators
from defusedxml import minidom

from .OGService import OGService
from . import og


import logging
import six


__updated__ = '2017-10-16'

logger = logging.getLogger(__name__)

class OGProvider(ServiceProvider):
    """
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

    """
    # : What kind of services we offer, this are classes inherited from Service
    offers = [OGService]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using ugettext_noop)
    typeName = _('OpenGnsys Platform Provider')
    # : Type used internally to identify this provider
    typeType = 'openGnsysPlatform'
    # : Description shown at administration interface for this provider
    typeDescription = _('OpenGnsys platform service provider (experimental)')
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
    host = gui.TextField(length=64, label=_('Host'), order=1, tooltip=_('OpenGnsys Host'), required=True)
    port = gui.NumericField(length=5, label=_('Port'), defvalue='443', order=2, tooltip=_('OpenGnsys Port (default is 443, and only ssl connection is allowed)'), required=True)
    checkCert = gui.CheckBoxField(label=_('Check Cert.'), order=3, tooltip=_('If checked, ssl certificate of OpenGnsys server must be valid (not self signed)'))
    username = gui.TextField(length=32, label=_('Username'), order=4, tooltip=_('User with valid privileges on OpenGnsys'), required=True)
    password = gui.PasswordField(lenth=32, label=_('Password'), order=5, tooltip=_('Password of the user of OpenGnsys'), required=True)
    udsServerAccessUrl = gui.TextField(length=32, label=_('UDS Server URL'), order=6, tooltip=_('URL used by OpenGnsys to access UDS. If empty, UDS will guess it.'), required=False, tab=gui.PARAMETERS_TAB)

    maxPreparingServices = gui.NumericField(length=3, label=_('Creation concurrency'), defvalue='10', minValue=1, maxValue=65536, order=50, tooltip=_('Maximum number of concurrently creating VMs'), required=True, tab=gui.ADVANCED_TAB)
    maxRemovingServices = gui.NumericField(length=3, label=_('Removal concurrency'), defvalue='5', minValue=1, maxValue=65536, order=51, tooltip=_('Maximum number of concurrently removing VMs'), required=True, tab=gui.ADVANCED_TAB)

    timeout = gui.NumericField(length=3, label=_('Timeout'), defvalue='10', order=90, tooltip=_('Timeout in seconds of connection to OpenGnsys'), required=True, tab=gui.ADVANCED_TAB)

    # Own variables
    _api = None

    def initialize(self, values=None):
        """
        We will use the "autosave" feature for form fields
        """

        # Just reset _api connection variable
        self._api = None

        if values is not None:
            self.timeout.value = validators.validateTimeout(self.timeout.value, returnAsInteger=False)
            logger.debug('Endpoint: {}'.format(self.endpoint))

            try:
                request = values['_request']

                if self.udsServerAccessUrl.value.strip() == '':
                    self.udsServerAccessUrl.value = request.build_absolute_uri('/')

                if self.udsServerAccessUrl.value[-1] != '/':
                    self.udsServerAccessUrl.value += '/'
            except Exception:
                pass

    @property
    def endpoint(self):
        return 'https://{}:{}/opengnsys/rest'.format(self.host.value, self.port.value)

    @property
    def api(self):
        if self._api is None:
            self._api = og.OpenGnsysClient(self.username.value, self.password.value, self.endpoint, self.cache, self.checkCert.isTrue())

        logger.debug('Api: {}'.format(self._api))
        return self._api

    def resetApi(self):
        self._api = None

    def testConnection(self):
        """
        Test that conection to OpenGnsys server is fine

        Returns

            True if all went fine, false if id didn't
        """
        try:
            if self.api.version[0:5] < '1.1.0':
                return [False, 'OpenGnsys version is not supported (required version 1.1.0 or newer and found {})'.format(self.api.version)]
        except Exception as e:
            logger.exception('Error')
            return [False, '{}'.format(e)]

        return [True, _('OpenGnsys test connection passed')]

    @staticmethod
    def test(env, data):
        """
        Test ovirt Connectivity

        Args:
            env: environment passed for testing (temporal environment passed)

            data: data passed for testing (data obtained from the form
            definition)

        Returns:
            Array of two elements, first is True of False, depending on test
            (True is all right, false is error),
            second is an String with error, preferably i18n..

        """
        return OGProvider(env, data).testConnection()

    def getUDSServerAccessUrl(self):
        return self.udsServerAccessUrl.value

    def reserve(self, ou, image, lab=0, maxtime=0):
        return self.api.reserve(ou, image, lab, maxtime)

    def unreserve(self, machineId):
        return self.api.unreserve(machineId)

    def notifyEvents(self, machineId, loginURL, logoutURL):
        return self.api.notifyURLs(machineId, loginURL, logoutURL)

    def notifyDeadline(self, machineId, deadLine):
        return self.api.notifyDeadline(machineId, deadLine)

    def status(self, machineId):
        return self.api.status(machineId)
