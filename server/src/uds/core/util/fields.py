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
import functools
import logging
import typing
import collections.abc

from django.utils.translation import gettext as _
from django.db.models import Q

from cryptography.x509 import load_pem_x509_certificate

from uds import models
from uds.core import types, ui

if typing.TYPE_CHECKING:
    from cryptography.x509 import Certificate

logger = logging.getLogger(__name__)

# ******************************************************
# Tunnel related common use fields and related functions
# ******************************************************


def _server_group_values(
    types_: collections.abc.Iterable[types.servers.ServerType], subtype: typing.Optional[str] = None
) -> list[types.ui.ChoiceItem]:
    fltr = models.ServerGroup.objects.filter(
        functools.reduce(lambda x, y: x | y, [Q(type=type_) for type_ in types_])
    )
    if subtype is not None:
        fltr = fltr.filter(subtype=subtype)

    return [
        ui.gui.choice_item(v.uuid, f'{v.name} {("("+ v.pretty_host + ")") if v.pretty_host else ""}')
        for v in fltr.all()
    ]


def _server_group_from_field(fld: ui.gui.ChoiceField) -> models.ServerGroup:
    try:
        return models.ServerGroup.objects.get(uuid=fld.value)
    except Exception:
        return models.ServerGroup()


# Tunnel server field
def tunnel_field() -> ui.gui.ChoiceField:
    """Returns a field to select a tunnel server"""
    return ui.gui.ChoiceField(
        label=_('Tunnel server'),
        order=1,
        tooltip=_('Tunnel server to use'),
        required=True,
        choices=functools.partial(_server_group_values, [types.servers.ServerType.TUNNEL]),
        tab=types.ui.Tab.TUNNEL,
    )


def get_tunnel_from_field(fld: ui.gui.ChoiceField) -> models.ServerGroup:
    """Returns a tunnel server from a field"""
    return _server_group_from_field(fld)


# Server group field
def server_group_field(
    type: typing.Optional[list[types.servers.ServerType]] = None,
    subtype: typing.Optional[str] = None,
    tab: typing.Optional[types.ui.Tab] = None,
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
        choices=functools.partial(_server_group_values, type, subtype),  # So it gets evaluated at runtime
        tab=tab,
    )


def get_server_group_from_field(fld: ui.gui.ChoiceField) -> models.ServerGroup:
    """Returns a server group from a field

    Args:
        fld: Field to get server group from
    """
    return _server_group_from_field(fld)


# Ticket validity time field (for http related tunnels)
def tunnel_ricket_validity_field() -> ui.gui.NumericField:
    return ui.gui.NumericField(
        length=3,
        label=_('Ticket Validity'),
        default=60,
        order=90,
        tooltip=_(
            'Allowed time, in seconds, for HTML5 client to reload data from UDS Broker. The default value of 60 is recommended.'
        ),
        required=True,
        minValue=60,
        tab=types.ui.Tab.ADVANCED,
    )


# Tunnel wait time (for uds client related tunnels)
def tunnel_runnel_wait(order: int = 2) -> ui.gui.NumericField:
    return ui.gui.NumericField(
        length=3,
        label=_('Tunnel wait time'),
        default=30,
        minValue=5,
        maxValue=3600 * 24,
        order=order,
        tooltip=_('Maximum time, in seconds, to wait before disable new connections on client tunnel listener'),
        required=True,
        tab=types.ui.Tab.TUNNEL,
    )


# Get certificates from field
def get_vertificates_from_field(
    field: ui.gui.TextField, field_value: typing.Optional[str] = None
) -> list['Certificate']:
    # Get certificates in self.publicKey.value, encoded as PEM
    # Return a list of certificates in DER format
    value = (field_value or field.value).strip()
    if value == '':
        return []

    # Get certificates in PEM format
    pemCerts = value.split('-----END CERTIFICATE-----')
    # Remove empty strings
    pemCerts = [cert for cert in pemCerts if cert.strip() != '']
    # Add back the "-----END CERTIFICATE-----" part
    pemCerts = [cert + '-----END CERTIFICATE-----' for cert in pemCerts]

    # Convert to DER format
    certs: list['Certificate'] = []  # PublicKey...
    for pemCert in pemCerts:
        certs.append(load_pem_x509_certificate(pemCert.encode('ascii'), None))

    return certs
