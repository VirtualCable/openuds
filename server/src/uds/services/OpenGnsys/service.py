# -*- coding: utf-8 -*-
#
# Copyright (c) 2017-2021 Virtual Cable S.L.U.
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
import collections.abc

from django.utils.translation import gettext_noop as _

from uds.core import types, services, consts
from uds.core.ui import gui
from uds.core.util import fields

from . import helpers
from .deployment import OpenGnsysUserService
from .publication import OpenGnsysPublication

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from .provider import OGProvider
    from uds.core.module import Module

logger = logging.getLogger(__name__)


class OGService(services.Service):
    """
    OpenGnsys Service
    """

    # : Name to show the administrator. This string will be translated BEFORE
    # : sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    type_name = _('OpenGnsys Machines Service')
    # : Type used internally to identify this provider
    type_type = 'openGnsysMachine'
    # : Description shown at administration interface for this provider
    type_description = _('OpenGnsys physical machines')
    # : Icon file used as icon for this provider. This string will be translated
    # : BEFORE sending it to administration interface, so don't forget to
    # : mark it as _ (using gettext_noop)
    icon_file = 'provider.png'

    # Functional related data

    # : If we need to generate "cache" for this service, so users can access the
    # : provided services faster. Is uses_cache is True, you will need also
    # : set publication_type, do take care about that!
    uses_cache = True
    # : Tooltip shown to user when this item is pointed at admin interface, none
    # : because we don't use it
    cache_tooltip = _('Number of desired machines to keep running waiting for an user')

    # : If the service needs a s.o. manager (managers are related to agents
    # : provided by services itselfs, i.e. virtual machines with actors)
    needs_osmanager = False
    # : If true, the system can't do an automatic assignation of a deployed user
    # : service from this service
    must_assign_manually = False

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publication_type = OpenGnsysPublication
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = OpenGnsysUserService

    allowed_protocols = types.transports.Protocol.generic_vdi()
    services_type_provided = types.services.ServiceType.VDI

    # Now the form part
    ou = gui.ChoiceField(
        label=_("OU"),
        order=100,
        fills={
            'callback_name': 'OgFillOuData',
            'function': helpers.get_resources,
            'parameters': ['parent_uuid', 'ou'],
        },
        tooltip=_('Organizational Unit'),
        required=True,
    )

    # Lab is not required, but maybe used as filter
    lab = gui.ChoiceField(
        label=_("lab"),
        order=101,
        tooltip=_('Laboratory'),
        required=False,
    )

    # Required, this is the base image
    image = gui.ChoiceField(
        label=_("OS Image"),
        order=102,
        tooltip=_('OpenGnsys Operating System Image'),
        required=True,
    )

    max_reserve_hours = gui.NumericField(
        length=3,
        label=_("Max. reservation time"),
        order=110,
        tooltip=_(
            'Security parameter for OpenGnsys to keep reservations at most this hours. Handle with care!'
        ),
        default=2400,  # 1 hundred days
        min_value=24,
        tab=_('Advanced'),
        required=False,
        old_field_name='maxReservationTime',
    )

    start_if_unavailable = gui.CheckBoxField(
        label=_('Start if unavailable'),
        default=True,
        order=111,
        tooltip=_(
            'If active, machines that are not available on user connect (on some OS) will try to power on through OpenGnsys.'
        ),
        old_field_name='startIfUnavailable',
    )

    services_limit = fields.services_limit_field()

    parent_uuid = gui.HiddenField(value=None)

    def init_gui(self) -> None:
        """
        Loads required values inside
        """
        ous = [gui.choice_item(r['id'], r['name']) for r in self.parent().api.list_of_ous()]
        self.ou.set_choices(ous)

        self.parent_uuid.value = self.parent().db_obj().uuid

    def parent(self) -> 'OGProvider':
        return typing.cast('OGProvider', super().parent())

    def status(self, machine_id: str) -> typing.Any:
        return self.parent().status(machine_id)

    def reserve(self) -> typing.Any:
        return self.parent().reserve(
            self.ou.value,
            self.image.value,
            self.lab.value,
            self.max_reserve_hours.as_int(),
        )

    def unreserve(self, machine_id: str) -> None:
        self.parent().unreserve(machine_id)

    def notify_endpoints(self, machine_id: str, token: str, uuid: str) -> None:
        self.parent().notify_endpoints(
            machine_id,
            self.get_login_notify_url(uuid, token),
            self.get_logout_notify_url(uuid, token),
            self.get_relase_url(uuid, token),
        )

    def notify_deadline(self, machine_id: str, deadLine: typing.Optional[int]) -> None:
        self.parent().notify_deadline(machine_id, deadLine)

    def power_on(self, machine_id: str) -> None:
        self.parent().power_on(machine_id, self.image.value)

    def _notify_url(self, uuid: str, token: str, message: str) -> str:
        # The URL is "GET messages URL".
        return f'{self.parent().get_uds_endpoint()}uds/ognotify/{message}/{token}/{uuid}'

    def get_login_notify_url(self, uuid: str, token: str) -> str:
        return self._notify_url(uuid, token, 'login')

    def get_logout_notify_url(self, uuid: str, token: str) -> str:
        return self._notify_url(uuid, token, 'logout')

    def get_relase_url(self, uuid: str, token: str) -> str:
        return self._notify_url(uuid, token, 'release')

    def try_start_if_unavailable(self):
        return self.start_if_unavailable.as_bool()

    def is_avaliable(self) -> bool:
        return self.parent().is_available()
