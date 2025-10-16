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

from django.utils.translation import gettext_noop as _

from uds.core import types as core_types, consts
from uds.core.services import ServiceProvider
from uds.core.ui import gui
from uds.core.util import validators, fields
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
    type_description = _('Openshift based instances provider')
    icon_file = 'provider.png'

    # Gui
    host = gui.TextField(
        order=1,
        length=64,
        label=_('Host'),
        tooltip=_('Openshift Server IP or Hostname'),
        required=True,
    )
    port = gui.NumericField(
        order=2,
        length=3,
        label=_('Port'),
        default=443,
        tooltip=_('Openshift Server Port (default 443)'),
        required=True,
    )
    verify_ssl = fields.verify_ssl_field(order=3)

    username = gui.TextField(
        order=4,
        length=32,
        label=_('Username'),
        tooltip=_('User with valid privileges on Openshift Server'),
        required=True,
    )
    password = gui.PasswordField(
        order=5,
        length=32,
        label=_('Password'),
        tooltip=_('Password of the user of Openshift Server'),
        required=True,
    )

    concurrent_creation_limit = fields.concurrent_creation_limit_field()
    concurrent_removal_limit = fields.concurrent_removal_limit_field()
    timeout = fields.timeout_field()

    _cached_api: typing.Optional['client.OpenshiftClient'] = None

    # There is more fields type, but not here the best place to cover it
    def initialize(self, values: 'core_types.core.ValuesType') -> None:
        if values:
            self.port.value = validators.validate_port(self.port.value)

    @property
    def api(
        self,
    ) -> 'client.OpenshiftClient':
        if self._cached_api is None:
            self._cached_api = client.OpenshiftClient(
                host=self.host.value,
                port=self.port.as_int(),
                username=self.username.value,
                password=self.password.value,
                cache=self.cache,
                timeout=self.timeout.as_int(),
                verify_ssl=self.verify_ssl.as_bool(),
            )
        return self._cached_api

    def test_connection(self) -> bool:
        return self.api.test()

    # def test_connection(self) -> bool:
    #     return self.api.test()

    # def get_task_info(self, task_id: str) -> nu_types.TaskInfo:
    #     try:
    #         return self.api.get_task_info(task_id)
    #     except nu_exceptions.AcropolisConnectionError:
    #         raise
    #     except Exception as e:
    #         logger.error('Exception obtaining Openshift task info: %s', e)
    #         return nu_types.TaskInfo(
    #             state=nu_types.TaskState.UNKNOWN, error={'error': str(e)}, entities=[]
    #         )

    # def get_macs_range(self) -> str:
    #     return self.macs_range.value

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
