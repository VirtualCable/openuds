# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2019 Virtual Cable S.L.U.
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

from django.utils.translation import gettext_noop as _

from uds.core import services, types, consts
from uds.core.ui import gui
from uds.core.util import validators, fields
from uds.core.util.decorators import cached

from .ovirt import client
from .service_linked import OVirtLinkedService

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import environment

logger = logging.getLogger(__name__)


class OVirtProvider(services.ServiceProvider):  # pylint: disable=too-many-public-methods
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
    offers = [OVirtLinkedService]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('oVirt/OLVM Platform Provider')
    # : Type used internally to identify this provider
    type_type = 'oVirtPlatform'
    # : Description shown at administration interface for this provider
    type_description = _('oVirt platform service provider')
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
    ovirt_version = gui.ChoiceField(
        order=1,
        label=_('Server Version'),
        tooltip=_('oVirt/OVLM Server Version'),
        # In this case, the choice can have none value selected by default
        required=True,
        readonly=False,
        choices=[
            gui.choice_item('4', '4.x'),
        ],
        default='4',  # Default value is the ID of the choicefield
        old_field_name='ovirtVersion',
    )

    host = gui.TextField(
        length=64,
        label=_('Host'),
        order=2,
        tooltip=_('oVirt Server IP or Hostname'),
        required=True,
    )
    port = gui.NumericField(
        length=5,
        label=_('Port'),
        order=2,
        tooltip=_('oVirt Server Port'),
        required=True,
        default=443,
    )
    username = gui.TextField(
        length=32,
        label=_('Username'),
        order=3,
        tooltip=_(
            (
                'User with valid privileges on oVirt.'
                ' Use "user@domain" if using AAA, or "user@domain@provider" if using keycloak.'
                ' I.e. "admin@ovirt@internalsso" or "admin@internal")'
            )
        ),
        required=True,
        default='admin@internal',
    )
    password = gui.PasswordField(
        length=32,
        label=_('Password'),
        order=4,
        tooltip=_('Password of the user of oVirt'),
        required=True,
    )

    concurrent_creation_limit = fields.concurrent_creation_limit_field()
    concurrent_removal_limit = fields.concurrent_removal_limit_field()
    timeout = fields.timeout_field(default=10, order=90)
    macs_range = fields.macs_range_field(default='52:54:00:00:00:00-52:54:00:FF:FF:FF', order=91)

    # Own variables
    _api: typing.Optional[client.Client] = None

    # oVirt engine, right now, only permits a connection to one server and only one per instance
    # If we want to connect to more than one server, we need keep locked access to api, change api server, etc..
    # We have implemented an "exclusive access" client that will only connect to one server at a time (using locks)
    # and this way all will be fine
    @property
    def api(self) -> client.Client:
        """
        Returns the connection API object for oVirt (using ovirtsdk)
        """
        if self._api is None:
            self._api = client.Client(
                self.host.value,
                self.port.value,
                self.username.value,
                self.password.value,
                self.timeout.value,
                self.cache,
            )

        return self._api

    # There is more fields type, but not here the best place to cover it
    def initialize(self, values: 'types.core.ValuesType') -> None:
        """
        We will use the "autosave" feature for form fields
        """

        # Just reset _api connection variable
        self._api = None

        if values is not None:
            self.macs_range.value = validators.validate_mac_range(self.macs_range.value)
            self.timeout.value = validators.validate_timeout(self.timeout.value)
            logger.debug(self.host.value)

    def test_connection(self) -> bool:
        """
        Test that conection to oVirt server is fine

        Returns

            True if all went fine, false if id didn't
        """

        return self.api.test()

    def get_macs_range(self) -> str:
        return self.macs_range.value

    @cached('reachable', consts.cache.SHORT_CACHE_TIMEOUT)
    def is_available(self) -> bool:
        """
        Check if aws provider is reachable
        """
        return self.test_connection()

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
        ov = OVirtProvider(env, data)
        if ov.test_connection() is True:
            return types.core.TestResult(True, _('Connection to oVirt server is ok'))

        return types.core.TestResult(False, _('Connection failed. Check connection params'))
