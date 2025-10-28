# -*- coding: utf-8 -*-
#
# Copyright (c) 2019-2024 Virtual Cable S.L.U.
# All rights reserved.
#
"""
Author: Adolfo Gómez, dkmaster at dkmon dot com
"""

import logging
import typing
<<<<<<< HEAD
=======
import re
>>>>>>> origin/dev/janier/master

from django.utils.translation import gettext_noop as _

from uds.core import types as core_types, consts
from uds.core.services import ServiceProvider
from uds.core.ui import gui
from uds.core.util import fields
from uds.core.util.decorators import cached

from .openshift import client

from .service import OpenshiftService
from .service_fixed import OpenshiftServiceFixed

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core import environment

logger = logging.getLogger(__name__)


class OpenshiftProvider(ServiceProvider):
    offers = [OpenshiftService, OpenshiftServiceFixed]
    type_name = _('Openshift Provider')
    type_type = 'OpenshiftProvider'
<<<<<<< HEAD
    type_description = _('Openshift based instances provider')
=======
    type_description = _('Openshift based VMs provider')
>>>>>>> origin/dev/janier/master
    icon_file = 'provider.png'

    # Gui
    cluster_url = gui.TextField(
        order=1,
        length=128,
        label=_('Cluster OAuth URL'),
        tooltip=_('Openshift OAuth URL, e.g. https://oauth-openshift.apps-crc.testing'),
        required=True,
        default='https://oauth-openshift.apps-crc.testing',
    )
    api_url = gui.TextField(
        order=2,
        length=128,
        label=_('API URL'),
        tooltip=_('Openshift API URL, e.g. https://localhost:6443'),
        required=True,
        default='https://localhost:6443',
    )
    username = gui.TextField(
        order=3,
        length=64,
        label=_('Username'),
        tooltip=_('User with valid privileges on Openshift Server'),
        required=True,
        default='kubeadmin',
    )
    password = gui.PasswordField(
        order=4,
        length=64,
        label=_('Password'),
        tooltip=_('Password of the user of Openshift Server'),
        required=True,
        default='Tn5u8-9k9I9-6WF3Y-q5hSB',
    )
    namespace = gui.TextField(
        order=5,
        length=64,
        label=_('Namespace'),
        tooltip=_('Openshift namespace to use (default: "default")'),
        required=True,
        default='default',
    )
    verify_ssl = fields.verify_ssl_field(order=6)
    concurrent_creation_limit = fields.concurrent_creation_limit_field()
    concurrent_removal_limit = fields.concurrent_removal_limit_field()
    timeout = fields.timeout_field()

<<<<<<< HEAD
    _cached_api: typing.Optional['client.OpenshiftClient'] = None
=======
    _cached_api: typing.Optional['client.OpenshiftClient'] = None #! DUDA
>>>>>>> origin/dev/janier/master

    def initialize(self, values: 'core_types.core.ValuesType') -> None:
        # No port validation needed, URLs are used
        pass

    @property
    def api(self) -> 'client.OpenshiftClient':
        if self._cached_api is None:
            self._cached_api = client.OpenshiftClient(
                cluster_url=self.cluster_url.value,
                api_url=self.api_url.value,
                username=self.username.value,
                password=self.password.value,
                namespace=self.namespace.value or 'default',
                cache=self.cache,
                timeout=self.timeout.as_int(),
                verify_ssl=self.verify_ssl.as_bool(),
            )
        return self._cached_api

    def test_connection(self) -> bool:
        return self.api.test()

    @cached('reachable', consts.cache.SHORT_CACHE_TIMEOUT)
    def is_available(self) -> bool:
        return self.api.test()

    @staticmethod
    def test(
        env: 'environment.Environment', data: 'core_types.core.ValuesType'
    ) -> 'core_types.core.TestResult':
        ov = OpenshiftProvider(env, data)
        if ov.test_connection() is True:
            return core_types.core.TestResult(True, _('Connection works fine'))

        return core_types.core.TestResult(False, _('Connection failed. Check connection params'))
<<<<<<< HEAD
=======
    
    # Utility
    def sanitized_name(self, name: str) -> str:
        """
        Sanitizes the VM name to comply with RFC 1123:
        - Lowercase
        - Alphanumeric, '-', '.'
        - Starts/ends with alphanumeric
        - Max length 63 chars
        """
        name = re.sub(r'^[^a-z0-9]+|[^a-z0-9.-]|-{2,}|[^a-z0-9]+$', '-', name.lower())
        return name[:63]
>>>>>>> origin/dev/janier/master
