# -*- coding: utf-8 -*-
#
# Copyright (c) 2013-2023 Virtual Cable S.L.U.
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
import typing
import functools

from django.utils.translation import gettext as _
from django.db.models import Q

from uds import models
from uds.core import types, ui


# ******************************************************
# Tunnel related common use fields and related functions
# ******************************************************


def _serverGroupValues(
    types_: typing.Iterable[types.servers.ServerType], subtype: typing.Optional[str] = None
) -> typing.List[ui.gui.ChoiceType]:
    fltr = models.RegisteredServerGroup.objects.filter(
        functools.reduce(lambda x, y: x | y, [Q(type=type_) for type_ in types_])
    )
    if subtype is not None:
        fltr = fltr.filter(subtype=subtype)
    return [ui.gui.choiceItem(v.uuid, f'{v.name} ({v.pretty_host})') for v in fltr.all()]


def _serverGrpFromField(
    fld: ui.gui.ChoiceField
) -> models.RegisteredServerGroup:
    try:
        return models.RegisteredServerGroup.objects.get(uuid=fld.value)
    except Exception:
        return models.RegisteredServerGroup()


# Tunnel server field
def tunnelField() -> ui.gui.ChoiceField:
    """Returns a field to select a tunnel server"""
    return ui.gui.ChoiceField(
        label=_('Tunnel server'),
        order=1,
        tooltip=_('Tunnel server to use'),
        required=True,
        values=functools.partial(_serverGroupValues, [types.servers.ServerType.TUNNEL]),
        tab=ui.gui.Tab.TUNNEL,
    )


def getTunnelFromField(fld: ui.gui.ChoiceField) -> models.RegisteredServerGroup:
    """Returns a tunnel server from a field"""
    return _serverGrpFromField(fld)


# Server group field
def serverGroupField(
    type: typing.Optional[typing.List[types.servers.ServerType]] = None, subtype: typing.Optional[str] = None,
    tab: typing.Optional[ui.gui.Tab] = None
) -> ui.gui.ChoiceField:
    """Returns a field to select a server group

    Args:
        type: Type of server group to select
        subktype: Subtype of server group to select (if any)

    Returns:
        A ChoiceField with the server group selection
    """
    type = type or [types.servers.ServerType.UNMANAGED]
    return ui.gui.ChoiceField(
        label=_('Server group'),
        order=2,
        tooltip=_('Server group to use'),
        required=True,
        values=functools.partial(_serverGroupValues, type, subtype),  # So it gets evaluated at runtime
        tab=tab,
    )


def getServerGroupFromField(
    fld: ui.gui.ChoiceField
) -> models.RegisteredServerGroup:
    """Returns a server group from a field

    Args:
        fld: Field to get server group from
    """
    return _serverGrpFromField(fld)


def getServersFromServerGroupField(
    fld: ui.gui.ChoiceField, type_: types.servers.ServerType = types.servers.ServerType.UNMANAGED
) -> typing.List[models.RegisteredServer]:
    """Returns a list of servers from a server group field

    Args:
        fld: Field to get server group from
    """
    grp = _serverGrpFromField(fld)
    return list(grp.servers.all())


# Ticket validity time field (for http related tunnels)
def tunnelTicketValidityField() -> ui.gui.NumericField:
    return ui.gui.NumericField(
        length=3,
        label=_('Ticket Validity'),
        defvalue='60',
        order=90,
        tooltip=_(
            'Allowed time, in seconds, for HTML5 client to reload data from UDS Broker. The default value of 60 is recommended.'
        ),
        required=True,
        minValue=60,
        tab=ui.gui.Tab.ADVANCED,
    )


# Tunnel wait time (for uds client related tunnels)
def tunnelTunnelWait(order: int = 2) -> ui.gui.NumericField:
    return ui.gui.NumericField(
        length=3,
        label=_('Tunnel wait time'),
        defvalue='30',
        minValue=5,
        maxValue=3600 * 24,
        order=order,
        tooltip=_('Maximum time, in seconds, to wait before disable new connections on client tunnel listener'),
        required=True,
        tab=ui.gui.Tab.TUNNEL,
    )
