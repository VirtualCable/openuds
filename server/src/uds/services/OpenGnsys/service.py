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

from . import helpers
from .deployment import OGDeployment
from .publication import OGPublication

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
    needs_manager = False
    # : If true, the system can't do an automatic assignation of a deployed user
    # : service from this service
    must_assign_manually = False

    # : Types of publications (preparated data for deploys)
    # : In our case, we do no need a publication, so this is None
    publication_type = OGPublication
    # : Types of deploys (services in cache and/or assigned to users)
    user_service_type = OGDeployment

    allowed_protocols = types.transports.Protocol.generic_vdi()
    services_type_provided = types.services.ServiceType.VDI



    # Now the form part
    ou = gui.ChoiceField(
        label=_("OU"),
        order=100,
        fills={
            'callback_name': 'osFillData',
            'function': helpers.get_resources,
            'parameters': ['ov', 'ev', 'ou'],
        },
        tooltip=_('Organizational Unit'),
        required=True,
    )

    # Lab is not required, but maybe used as filter
    lab = gui.ChoiceField(
        label=_("lab"), order=101, tooltip=_('Laboratory'), required=False
    )

    # Required, this is the base image
    image = gui.ChoiceField(
        label=_("OS Image"),
        order=102,
        tooltip=_('OpenGnsys Operating System Image'),
        required=True,
    )

    maxReservationTime = gui.NumericField(
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
    )

    startIfUnavailable = gui.CheckBoxField(
        label=_('Start if unavailable'),
        default=True,
        order=111,
        tooltip=_(
            'If active, machines that are not available on user connect (on some OS) will try to power on through OpenGnsys.'
        ),
    )

    maxServices = gui.NumericField(
        order=4,
        label=_("Max. Allowed services"),
        min_value=0,
        max_value=99999,
        default=0,
        readonly=False,
        tooltip=_('Maximum number of allowed services (0 or less means no limit)'),
        required=True,
        tab=types.ui.Tab.ADVANCED
    )

    ov = gui.HiddenField(value=None)
    ev = gui.HiddenField(
        value=None
    )  # We need to keep the env so we can instantiate the Provider

    def init_gui(self) -> None:
        """
        Loads required values inside
        """
        ous = [gui.choice_item(r['id'], r['name']) for r in self.parent().api.getOus()]
        self.ou.set_choices(ous)

        self.ov.value = self.parent().serialize()
        self.ev.value = self.parent().env.key

    def parent(self) -> 'OGProvider':
        return typing.cast('OGProvider', super().parent())

    def status(self, machineId: str) -> typing.Any:
        return self.parent().status(machineId)

    def reserve(self) -> typing.Any:
        return self.parent().reserve(
            self.ou.value,
            self.image.value,
            self.lab.value,
            self.maxReservationTime.as_int(),
        )

    def unreserve(self, machineId: str) -> typing.Any:
        return self.parent().unreserve(machineId)

    def notifyEvents(self, machineId: str, token: str, uuid: str) -> typing.Any:
        return self.parent().notifyEvents(
            machineId,
            self.getLoginNotifyURL(uuid, token),
            self.getLogoutNotifyURL(uuid, token),
            self.getReleaseURL(uuid, token),
        )

    def notifyDeadline(
        self, machineId: str, deadLine: typing.Optional[int]
    ) -> typing.Any:
        return self.parent().notifyDeadline(machineId, deadLine)

    def powerOn(self, machineId: str) -> typing.Any:
        return self.parent().powerOn(machineId, self.image.value)

    def _notifyURL(self, uuid: str, token: str, message: str) -> str:
        # The URL is "GET messages URL".
        return '{accessURL}uds/ognotify/{message}/{token}/{uuid}'.format(
            accessURL=self.parent().getUDSServerAccessUrl(),
            uuid=uuid,
            token=token,
            message=message,
        )

    def getLoginNotifyURL(self, uuid: str, token: str) -> str:
        return self._notifyURL(uuid, token, 'login')

    def getLogoutNotifyURL(self, uuid: str, token: str) -> str:
        return self._notifyURL(uuid, token, 'logout')

    def getReleaseURL(self, uuid: str, token: str) -> str:
        return self._notifyURL(uuid, token, 'release')

    def is_removableIfUnavailable(self):
        return self.startIfUnavailable.as_bool()

    def is_avaliable(self) -> bool:
        return self.parent().is_available()
