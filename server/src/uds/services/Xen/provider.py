# -*- coding: utf-8 -*-
#
# Copyright (c) 2014-2019 Virtual Cable S.L.
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
import contextlib
import logging
import typing

from django.utils.translation import gettext_noop as _

from uds.core import types, consts
from uds.core.services import ServiceProvider
from uds.core.ui import gui
from uds.core.util.decorators import cached
from uds.core.util import fields

from .service import XenLinkedService
from .service_fixed import XenFixedService
from .xen import client

# from uds.core.util import validators


# from xen_client import XenFailure, XenFault


logger = logging.getLogger(__name__)

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import environment


class XenProvider(ServiceProvider):  # pylint: disable=too-many-public-methods
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
    offers = [XenLinkedService, XenFixedService]
    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('Xenserver/XCP-NG Platforms Provider')
    # : Type used internally to identify this provider
    type_type = 'XenPlatform'
    # : Description shown at administration interface for this provider
    type_description = _('XenServer and XCP-NG platforms service provider')
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
        length=64,
        label=_('Host'),
        order=1,
        tooltip=_('XenServer Server IP or Hostname'),
        required=True,
    )
    username = gui.TextField(
        length=32,
        label=_('Username'),
        order=2,
        tooltip=_('User with valid privileges on XenServer'),
        required=True,
        default='root',
    )
    password = gui.PasswordField(
        length=32,
        label=_('Password'),
        order=3,
        tooltip=_('Password of the user of XenServer'),
        required=True,
    )
    concurrent_creation_limit = fields.concurrent_creation_limit_field()
    concurrent_removal_limit = fields.concurrent_removal_limit_field()

    macs_range = fields.macs_range_field(default='02:46:00:00:00:00-02:46:00:FF:FF:FF')
    verify_ssl = fields.verify_ssl_field(old_field_name='verifySSL')

    host_backup = gui.TextField(
        length=64,
        label=_('Backup Host'),
        order=92,
        tooltip=_('XenServer BACKUP IP or Hostname (used on connection failure to main server)'),
        tab=types.ui.Tab.ADVANCED,
        required=False,
        old_field_name='hostBackup',
    )

    _cached_api: typing.Optional[client.XenServer]
    _use_count: int = 0

    # XenServer engine, right now, only permits a connection to one server and only one per instance
    # If we want to connect to more than one server, we need keep locked access to api, change api server, etc..
    # We have implemented an "exclusive access" client that will only connect to one server at a time (using locks)
    # and this way all will be fine
    def _api(self) -> client.XenServer:
        """
        Returns the connection API object for XenServer (using XenServersdk)
        """
        if not self._cached_api:
            self._cached_api = client.XenServer(
                self.host.value,
                self.host_backup.value,
                443,
                self.username.value,
                self.password.value,
                True,
                self.verify_ssl.as_bool(),
            )

        return self._cached_api
    
    @contextlib.contextmanager
    def get_connection(self) -> typing.Iterator[client.XenServer]:
        """
        Context manager for XenServer API
        """
        self._use_count += 1
        try:
            yield self._api()
        finally:
            self._use_count -= 1
            if self._use_count == 0 and self._cached_api:
                self._cached_api.logout()
                self._cached_api = None

    # There is more fields type, but not here the best place to cover it
    def initialize(self, values: 'types.core.ValuesType') -> None:
        """
        We will use the "autosave" feature for form fields
        """

        # Just reset _api connection variable
        self._cached_api = None

    def test_connection(self) -> None:
        """
        Test that conection to XenServer server is fine

        Returns

            True if all went fine, false if id didn't
        """
        self._api().test()

    def get_macs_range(self) -> str:
        return self.macs_range.value

    @cached('reachable', consts.cache.SHORT_CACHE_TIMEOUT, key_helper=lambda x: x.host.as_str())
    def is_available(self) -> bool:
        try:
            self.test_connection()
            return True
        except Exception:
            return False

    @staticmethod
    def test(env: 'environment.Environment', data: 'types.core.ValuesType') -> 'types.core.TestResult':
        """
        Test XenServer Connectivity

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
        xe = XenProvider(env, data)
        try:
            xe.test_connection()
            return types.core.TestResult(True, _('Connection test successful'))
        except Exception as e:
            return types.core.TestResult(False, _('Connection failed: {}').format(str(e)))
