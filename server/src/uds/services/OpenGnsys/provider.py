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
#      and/or other materials provided with the distributiog.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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

Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds.core import types, consts
from uds.core.services import ServiceProvider
from uds.core.ui import gui
from uds.core.util import fields, validators
from uds.core.util.decorators import cached

from . import og
from .service import OGService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.environment import Environment

logger = logging.getLogger(__name__)

MIN_VERSION = '1.1.0'


class OGProvider(ServiceProvider):
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
    offers = [OGService]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('OpenGnsys Platform Provider')
    # : Type used internally to identify this provider
    type_type = 'openGnsysPlatform'
    # : Description shown at administration interface for this provider
    type_description = _('OpenGnsys platform service provider (experimental)')
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
    host = gui.TextField(length=64, label=_('Host'), order=1, tooltip=_('OpenGnsys Host'), required=True)
    port = gui.NumericField(
        length=5,
        label=_('Port'),
        default=443,
        order=2,
        tooltip=_('OpenGnsys Port (default is 443, and only ssl connection is allowed)'),
        required=True,
    )
    verify_ssl = fields.verify_ssl_field(order=3, old_field_name='checkCert')
    username = gui.TextField(
        length=32,
        label=_('Username'),
        order=4,
        tooltip=_('User with valid privileges on OpenGnsys'),
        required=True,
    )
    password = gui.PasswordField(
        length=32,
        label=_('Password'),
        order=5,
        tooltip=_('Password of the user of OpenGnsys'),
        required=True,
    )
    uds_endpoint = gui.TextField(
        length=32,
        label=_('UDS Server endpoint'),
        order=6,
        tooltip=_('URL used by OpenGnsys to access UDS. If empty, UDS will try to guess it.'),
        required=False,
        tab=types.ui.Tab.PARAMETERS,
        old_field_name='udsServerAccessUrl',
    )

    concurrent_creation_limit = fields.concurrent_creation_limit_field()
    concurrent_removal_limit = fields.concurrent_removal_limit_field()

    timeout = gui.NumericField(
        length=3,
        label=_('Timeout'),
        default=10,
        order=90,
        tooltip=_('Timeout in seconds of connection to OpenGnsys'),
        required=True,
        tab=types.ui.Tab.ADVANCED,
    )

    # Own variables
    _api: typing.Optional[og.OpenGnsysClient] = None

    def initialize(self, values: 'types.core.ValuesType') -> None:
        """
        We will use the "autosave" feature for form fields
        """

        # Just reset _api connection variable
        self._api = None

        if values:
            self.timeout.value = validators.validate_timeout(self.timeout.value)
            logger.debug('Endpoint: %s', self.endpoint)

            try:
                request = values['_request']

                if self.uds_endpoint.value.strip() == '':
                    self.uds_endpoint.value = request.build_absolute_uri('/')

                # Ensure that url ends with /
                self.uds_endpoint.value = self.uds_endpoint.as_str().strip('/') + '/'
            except Exception as e:
                logger.error('Error while trying to get UDS endpoint: %s', e)
                self.uds_endpoint.value = ''

    @property
    def endpoint(self) -> str:
        return 'https://{}:{}/opengnsys/rest'.format(self.host.value, self.port.value)

    @property
    def api(self) -> og.OpenGnsysClient:
        if not self._api:
            self._api = og.OpenGnsysClient(
                self.username.value,
                self.password.value,
                self.endpoint,
                self.cache,
                self.verify_ssl.as_bool(),
            )

        logger.debug('Api: %s', self._api)
        return self._api

    def clear_api(self) -> None:
        self._api = None

    def test_connection(self) -> types.core.TestResult:
        """
        Test that conection to OpenGnsys server is fine

        Returns

            True if all went fine, false if id didn't
        """
        try:
            if self.api.version[0:5] < MIN_VERSION:
                return types.core.TestResult(
                    False,
                    _(
                        'OpenGnsys version is not supported (required version 1.1.0 or newer and found {})'
                    ).format(self.api.version),
                )
        except Exception as e:
            logger.exception('Error')
            return types.core.TestResult(False, _('Error testing OpenGnsys connection: {}').format(e))

        return types.core.TestResult(True, _('OpenGnsys test connection passed'))

    @staticmethod
    def test(env: 'Environment', data: 'types.core.ValuesType') -> 'types.core.TestResult':
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
        return OGProvider(env, data).test_connection()

    def get_uds_endpoint(self) -> str:
        return self.uds_endpoint.value

    def reserve(self, ou: str, image: str, lab: int = 0, maxtime: int = 0) -> typing.Any:
        return self.api.reserve(ou, image, lab, maxtime)

    def unreserve(self, vmid: str) -> None:
        self.api.unreserve(vmid)

    def power_on(self, vmid: str, image: str) -> None:
        self.api.power_on(vmid, image)

    def notify_endpoints(self, vmid: str, login_url: str, logout_url: str, release_url: str) -> None:
        self.api.notify_endpoints(vmid, login_url, logout_url, release_url)

    def notify_deadline(self, machineId: str, deadLine: typing.Optional[int]) -> None:
        self.api.notify_deadline(machineId, deadLine)

    def status(self, machineId: str) -> typing.Any:
        return self.api.status(machineId)

    @cached('reachable', consts.cache.SHORT_CACHE_TIMEOUT)
    def is_available(self) -> bool:
        """
        Check if aws provider is reachable
        """
        try:
            if self.api.version[0:5] < MIN_VERSION:
                return False
            return True
        except Exception:
            return False
