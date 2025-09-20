# -*- coding: utf-8 -*-

#
# Copyright (c) 2014-2021 Virtual Cable S.L.U.
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

'''
@Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import dataclasses
import logging
import re
import typing
import collections.abc

from django.utils.translation import gettext, gettext_lazy as _
from django.db.models import Model

from uds.core import consts, exceptions, transports, types, ui
from uds.core.environment import Environment
from uds.core.util import ensure, permissions, ui as ui_utils
from uds.models import Network, ServicePool, Transport
from uds.REST.model import ModelHandler


logger = logging.getLogger(__name__)

# Enclosed methods under /item path


@dataclasses.dataclass
class TransportItem(types.rest.ManagedObjectItem[Transport]):
    id: str
    name: str
    tags: list[str]
    comments: str
    priority: int
    label: str
    net_filtering: str
    networks: list[str]
    allowed_oss: list[str]
    pools: list[str]
    pools_count: int
    deployed_count: int
    protocol: str
    permission: int


class Transports(ModelHandler[TransportItem]):

    MODEL = Transport
    FIELDS_TO_SAVE = [
        'name',
        'comments',
        'tags',
        'priority',
        'net_filtering',
        'allowed_oss',
        'label',
    ]

    TABLE = (
        ui_utils.TableBuilder(_('Transports'))
        .numeric_column(name='priority', title=_('Priority'), width='6em')
        .icon(name='name', title=_('Name'))
        .text_column(name='type_name', title=_('Type'))
        .text_column(name='comments', title=_('Comments'))
        .numeric_column(name='pools_count', title=_('Service Pools'), width='6em')
        .text_column(name='allowed_oss', title=_('Devices'), width='8em')
        .text_column(name='tags', title=_('tags'), visible=False)
    ).build()

    # Rest api related information to complete the auto-generated API
    REST_API_INFO = types.rest.api.RestApiInfo(
        gui_type=types.rest.api.RestApiInfoGuiType.TYPED,
    )

    @classmethod
    def possible_types(cls: type[typing.Self]) -> collections.abc.Iterable[type[transports.Transport]]:
        return transports.factory().providers().values()

    def get_gui(self, for_type: str) -> list[types.ui.GuiElement]:
        transport_type = transports.factory().lookup(for_type)

        if not transport_type:
            raise exceptions.rest.NotFound(_('Transport type not found: {}').format(for_type))

        with Environment.temporary_environment() as env:
            transport = transport_type(env, None)

            return (
                ui_utils.GuiBuilder()
                .add_stock_field(types.rest.stock.StockField.NAME)
                .add_stock_field(types.rest.stock.StockField.COMMENTS)
                .add_stock_field(types.rest.stock.StockField.TAGS)
                .add_stock_field(types.rest.stock.StockField.PRIORITY)
                .add_stock_field(types.rest.stock.StockField.NETWORKS)
                .add_fields(transport.gui_description())
                .add_multichoice(
                    name='pools',
                    label=gettext('Service Pools'),
                    choices=[
                        ui.gui.choice_item(x.uuid, x.name)
                        for x in ServicePool.objects.filter(service__isnull=False)
                        .order_by('name')
                        .prefetch_related('service')
                        if transport_type.PROTOCOL in x.service.get_type().allowed_protocols
                    ],
                    tooltip=gettext(
                        'Currently assigned services pools. If empty, no service pool is assigned to this transport'
                    ),
                )
                .new_tab(types.ui.Tab.ADVANCED)
                .add_multichoice(
                    name='allowed_oss',
                    label=gettext('Allowed Devices'),
                    choices=[
                        ui.gui.choice_item(x.db_value(), x.os_name().title()) for x in consts.os.KNOWN_OS_LIST
                    ],
                    tooltip=gettext(
                        'If empty, any kind of device compatible with this transport will be allowed. Else, only devices compatible with selected values will be allowed'
                    ),
                )
                .add_text(
                    name='label',
                    label=gettext('Label'),
                    tooltip=gettext('Metapool transport label (only used on metapool transports grouping)'),
                )
                .build()
            )

    def get_item(self, item: 'Model') -> TransportItem:
        item = ensure.is_instance(item, Transport)
        type_ = item.get_type()
        pools = list(item.deployedServices.all().values_list('uuid', flat=True))
        return TransportItem(
            id=item.uuid,
            name=item.name,
            tags=[tag.tag for tag in item.tags.all()],
            comments=item.comments,
            priority=item.priority,
            label=item.label,
            net_filtering=item.net_filtering,
            networks=list(item.networks.all().values_list('uuid', flat=True)),
            allowed_oss=[x for x in item.allowed_oss.split(',')] if item.allowed_oss != '' else [],
            pools=pools,
            pools_count=len(pools),
            deployed_count=item.deployedServices.count(),
            protocol=type_.PROTOCOL,
            permission=permissions.effective_permissions(self._user, item),
            item=item,
        )

    def pre_save(self, fields: dict[str, typing.Any]) -> None:
        fields['allowed_oss'] = ','.join(fields['allowed_oss'])
        # If label has spaces, replace them with underscores
        fields['label'] = fields['label'].strip().replace(' ', '-')
        # And ensure small_name chars are valid [ a-zA-Z0-9:-]+
        if fields['label'] and not re.match(r'^[a-zA-Z0-9:-]+$', fields['label']):
            raise exceptions.rest.ValidationError(
                gettext('Label must contain only letters, numbers, ":" and "-"')
            )

    def post_save(self, item: 'Model') -> None:
        item = ensure.is_instance(item, Transport)
        try:
            networks = self._params['networks']
        except Exception:  # No networks passed in, this is ok
            logger.debug('No networks')
            return
        if networks is None:  # None is not provided, empty list is ok and means no networks
            return
        from uds.models import ServicePool  # Add the import statement for the ServicePool class

        logger.debug('Networks: %s', networks)
        item.networks.set(Network.objects.filter(uuid__in=networks))

        try:
            pools = self._params['pools']
        except Exception:
            logger.debug('No pools')
            pools = None

        if pools is None:
            return

        logger.debug('Pools: %s', pools)
        item.deployedServices.set(ServicePool.objects.filter(uuid__in=pools))

        # try:
        #    oss = ','.join(self._params['allowed_oss'])
        # except:
        #    oss = ''
        # logger.debug('Devices: {0}'.format(oss))
        # item.allowed_oss = oss
        # item.save()  # Store correctly the allowed_oss
