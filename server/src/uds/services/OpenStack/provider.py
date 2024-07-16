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
#      and/or other materials provided with the distributiopenStack.
#    * Neither the name of Virtual Cable S.L.U. nor the names of its contributors
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

"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds.core import exceptions, types
from uds.core.services import ServiceProvider
from uds.core.ui import gui
from uds.core.util import validators, fields

from .openstack import client, sanitized_name, types as openstack_types
from .service import OpenStackLiveService
from .service_fixed import OpenStackServiceFixed

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import environment

logger = logging.getLogger(__name__)

INTERFACE_VALUES: typing.Final[list[types.ui.ChoiceItem]] = [
    gui.choice_item('public', 'public'),
    gui.choice_item('private', 'private'),
    gui.choice_item('admin', 'admin'),
]


class OpenStackProvider(ServiceProvider):
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
    offers = [OpenStackLiveService, OpenStackServiceFixed]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('OpenStack Platform Provider')
    # : Type used internally to identify this provider
    type_type = 'openStackPlatformNew'
    # : Description shown at administration interface for this provider
    type_description = _('OpenStack platform service provider')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    icon_file = 'openstack.png'

    # now comes the form fields
    # There is always two fields that are requested to the admin, that are:
    # Service Name, that is a name that the admin uses to name this provider
    # Description, that is a short description that the admin gives to this provider
    # Now we are going to add a few fields that we need to use this provider
    # Remember that these are "dummy" fields, that in fact are not required
    # but used for sample purposes
    # If we don't indicate an order, the output order of fields will be
    # "random"
    endpoint = gui.TextField(
        length=128,
        label=_('Identity endpoint'),
        order=1,
        tooltip=_(
            'OpenStack identity endpoint API Access (for example, https://10.0.0.1/identity). Do not include /v3.'
        ),
        required=True,
    )

    auth_method = gui.ChoiceField(
        label=_('Authentication method'),
        order=2,
        tooltip=_('Authentication method to be used'),
        choices=[
            gui.choice_item(str(openstack_types.AuthMethod.PASSWORD), 'Password'),
            gui.choice_item(str(openstack_types.AuthMethod.APPLICATION_CREDENTIAL), 'Application Credential'),
        ],
        default='password',
    )

    access = gui.ChoiceField(
        label=_('Access interface'),
        order=5,
        tooltip=_('Access interface to be used'),
        choices=INTERFACE_VALUES,
        default='public',
    )

    domain = gui.TextField(
        length=64,
        label=_('Domain'),
        order=8,
        tooltip=_('Domain name (default is Default)'),
        required=True,
        default='Default',
    )
    username = gui.TextField(
        length=64,
        label=_('Username/Application Credential ID'),
        order=9,
        tooltip=_('User with valid privileges on OpenStack/Application Credential ID with valid privileges'),
        required=True,
        default='admin',
    )
    password = gui.PasswordField(
        length=32,
        label=_('Password/Application Credential Secret'),
        order=10,
        tooltip=_('Password of the user of OpenStack/Application Credential Secret'),
        required=True,
    )

    concurrent_creation_limit = fields.concurrent_creation_limit_field()
    concurrent_removal_limit = fields.concurrent_removal_limit_field()
    timeout = fields.timeout_field(default=10)

    tenant = gui.TextField(
        length=64,
        label=_('Project Id'),
        order=40,
        tooltip=_('Project (tenant) for this provider. Set only if required by server.'),
        required=False,
        default='',
        tab=types.ui.Tab.ADVANCED,
    )
    region = gui.TextField(
        length=64,
        label=_('Region'),
        order=41,
        tooltip=_('Region for this provider. Set only if required by server.'),
        required=False,
        default='',
        tab=types.ui.Tab.ADVANCED,
    )

    use_subnets_name = gui.CheckBoxField(
        label=_('Subnets names'),
        order=42,
        tooltip=_('If checked, the name of the subnets will be used instead of the names of networks'),
        default=False,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='useSubnetsName',
    )

    verify_ssl = fields.verify_ssl_field(order=91)

    https_proxy = gui.TextField(
        length=96,
        label=_('Proxy'),
        order=92,
        tooltip=_(
            'Proxy used on server connections for HTTPS connections (use PROTOCOL://host:port, i.e. http://10.10.0.1:8080)'
        ),
        required=False,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='httpsProxy',
    )

    legacy = False

    # Own variables
    _api: typing.Optional[client.OpenStackClient] = None

    def initialize(self, values: 'types.core.ValuesType' = None) -> None:
        """
        We will use the "autosave" feature for form fields
        """
        self._api = None

        if values is not None:
            self.timeout.value = validators.validate_timeout(self.timeout.value)
            if self.auth_method.value == openstack_types.AuthMethod.APPLICATION_CREDENTIAL:
                # Ensure that the project_id is provided, so it's bound to the application credential
                if not self.tenant.value:
                    raise exceptions.ui.ValidationError(
                        _('Project Id is required when using Application Credential')
                    )

    def api(
        self, projectid: typing.Optional[str] = None, region: typing.Optional[str] = None
    ) -> client.OpenStackClient:
        projectid = projectid or self.tenant.value or None
        region = region or self.region.value or None
        if self._api is None:
            proxies: 'dict[str, str]|None' = None
            if self.https_proxy.value.strip():
                proxies = {'https': self.https_proxy.value}
            self._api = client.OpenStackClient(
                self.endpoint.value,
                self.domain.value,
                self.username.value,
                self.password.value,
                projectid=projectid,
                region=region,
                access=openstack_types.AccessType.from_str(self.access.value),
                proxies=proxies,
                timeout=self.timeout.value,
                auth_method=openstack_types.AuthMethod.from_str(self.auth_method.value),
                verify_ssl=self.verify_ssl.value,
            )
        return self._api

    def sanitized_name(self, name: str) -> str:
        return sanitized_name(name)

    def test_connection(self) -> types.core.TestResult:
        """
        Test that conection to OpenStack server is fine

        Returns

            True if all went fine, false if id didn't
        """
        logger.debug('Testing connection to OpenStack')
        try:
            if self.api().test_connection() is False:
                raise Exception('Check connection credentials, server, etc.')
        except Exception as e:
            logger.exception('Error')
            return types.core.TestResult(False, _('Error: {}').format(e))

        return types.core.TestResult(True)

    @staticmethod
    def test(env: 'environment.Environment', data: 'types.core.ValuesType') -> 'types.core.TestResult':
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
        return OpenStackProvider(env, data).test_connection()

    def is_available(self) -> bool:
        """
        Check if openstack provider is reachable
        """
        return self.api().is_available()
