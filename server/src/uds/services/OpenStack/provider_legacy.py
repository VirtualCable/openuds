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

'''
Created on Jun 22, 2012

Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds.core import environment, types, consts
from uds.core.services import ServiceProvider
from uds.core.ui import gui
from uds.core.util import validators, fields
from uds.core.util.decorators import cached

from . import openstack
from .service import OpenStackLiveService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)

INTERFACE_VALUES = [
    gui.choice_item('public', 'public'),
    gui.choice_item('private', 'private'),
    gui.choice_item('admin', 'admin'),
]


class OpenStackProviderLegacy(ServiceProvider):
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
    offers = [OpenStackLiveService]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('OpenStack LEGACY Platform Provider')
    # : Type used internally to identify this provider
    type_type = 'openStackPlatform'
    # : Description shown at administration interface for this provider
    type_description = _(
        'OpenStack LEGACY platform service provider (for older Openstack Releases, previous to OCATA)'
    )
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
        length=64, label=_('Host'), order=1, tooltip=_('OpenStack Host'), required=True
    )
    port = gui.NumericField(
        length=5,
        label=_('Port'),
        default=5000,
        order=2,
        tooltip=_(
            '5000 for older releases, 80/443 (ssl) for releases newer than OCATA'
        ),
        required=True,
    )
    ssl = gui.CheckBoxField(
        label=_('Use SSL'),
        order=4,
        tooltip=_(
            'If checked, the connection will be forced to be ssl (will not work if server is not providing ssl)'
        ),
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
        label=_('Username'),
        order=9,
        tooltip=_('User with valid privileges on OpenStack'),
        required=True,
        default='admin',
    )
    password = gui.PasswordField(
        length=32,
        label=_('Password'),
        order=10,
        tooltip=_('Password of the user of OpenStack'),
        required=True,
    )

    concurrent_creation_limit = fields.concurrent_creation_limit_field()
    concurrent_removal_limit = fields.concurrent_removal_limit_field()
    timeout = fields.timeout_field(default=10)

    https_proxy = gui.TextField(
        length=96,
        label=_('Proxy'),
        order=91,
        tooltip=_(
            'Proxy used for connection to azure for HTTPS connections (use PROTOCOL://host:port, i.e. http://10.10.0.1:8080)'
        ),
        required=False,
        tab=types.ui.Tab.ADVANCED,
        old_field_name='httpsProxy',
    )

    # tenant = gui.TextField(length=64, label=_('Project'), order=6, tooltip=_('Project (tenant) for this provider'), required=True, default='')
    # -region = gui.TextField(length=64, label=_('Region'), order=7, tooltip=_('Region for this provider'), required=True, default='RegionOne')

    legacy = True

    # Own variables
    _api: typing.Optional[openstack.Client] = None

    def initialize(self, values: 'types.core.ValuesType') -> None:
        """
        We will use the "autosave" feature for form fields
        """
        # Just reset _api connection variable

        if values is not None:
            self.timeout.value = validators.validate_timeout(self.timeout.value)

    def api(self, projectid: typing.Optional[str]=None, region: typing.Optional[str]=None) -> openstack.Client:
        proxies: typing.Optional[dict[str, str]] = None
        if self.https_proxy.value.strip():
            proxies = {'https': self.https_proxy.value}
        return openstack.Client(
            self.host.value,
            self.port.value,
            self.domain.value,
            self.username.value,
            self.password.value,
            is_legacy=True,
            use_ssl=self.ssl.as_bool(),
            projectid=projectid,
            region=region,
            access=self.access.value,
            proxies=proxies,
        )

    def sanitized_name(self, name: str) -> str:
        return openstack.sanitized_name(name)

    def test_connection(self) -> types.core.TestResult:
        """
        Test that conection to OpenStack server is fine

        Returns

            True if all went fine, false if id didn't
        """

        try:
            if self.api().test_connection() is False:
                raise Exception('Check connection credentials, server, etc.')
        except Exception as e:
            return types.core.TestResult(False, '{}'.format(e))

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
        return OpenStackProviderLegacy(env, data).test_connection()

    @cached('reachable', consts.cache.SHORT_CACHE_TIMEOUT)
    def is_available(self) -> bool:
        """
        Check if aws provider is reachable
        """
        return self.test_connection().success

        