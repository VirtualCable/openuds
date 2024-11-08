# -*- coding: utf-8 -*-
#
# Copyright (c) 2012-2021 Virtual Cable S.L.U.
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
Author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import collections.abc
import logging
import typing
from functools import reduce

from django.urls import reverse
from django.utils import formats
from django.utils.translation import gettext

from uds.core import types
from uds.core.auths.auth import web_password
from uds.core.managers.crypto import CryptoManager
from uds.core.managers.userservice import UserServiceManager
from uds.core.exceptions.services import (
    MaxServicesReachedError,
    ServiceAccessDeniedByCalendar,
    ServiceNotReadyError,
)
from uds.core.util import html
from uds.core.util.config import GlobalConfig
from uds.core.util.model import sql_now
from uds.models import MetaPool, Network, ServicePool, ServicePoolGroup, TicketStore, Transport

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.requests import ExtendedHttpRequestWithUser
    from uds.models import Image, MetaPoolMember


logger = logging.getLogger(__name__)


# pylint: disable=too-many-arguments
def _service_info(
    uuid: str,
    is_meta: bool,
    name: str,
    visual_name: str,
    description: str,
    group: collections.abc.Mapping[str, typing.Any],
    transports: list[collections.abc.Mapping[str, typing.Any]],
    image: typing.Optional['Image'],
    show_transports: bool,
    allow_users_remove: bool,
    allow_users_reset: bool,
    maintenance: bool,
    not_accesible: bool,
    in_use: bool,
    to_be_replaced: typing.Optional[str],
    to_be_replaced_text: str,
    custom_calendar_text: str,
    custom_message_text: typing.Optional[str],
) -> collections.abc.Mapping[str, typing.Any]:
    return {
        'id': ('M' if is_meta else 'F') + uuid,
        'is_meta': is_meta,
        'name': name,
        'visual_name': visual_name,
        'description': description,
        'group': group,
        'transports': transports,
        'imageId': image and image.uuid or 'x',
        'show_transports': show_transports,
        'allow_users_remove': allow_users_remove,
        'allow_users_reset': allow_users_reset,
        'maintenance': maintenance,
        'not_accesible': not_accesible,
        'in_use': in_use,
        'to_be_replaced': to_be_replaced,
        'to_be_replaced_text': to_be_replaced_text,
        'custom_calendar_text': custom_calendar_text,
        'custom_message_text': custom_message_text,
    }


# pylint: disable=too-many-locals, too-many-branches, too-many-statements
def get_services_info_dict(
    request: 'ExtendedHttpRequestWithUser',
) -> dict[str, typing.Any]:  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    """Obtains the service data dictionary will all available services for this request

    Arguments:
        request {ExtendedHttpRequest} -- request from where to xtract credentials

    Returns:
        dict[str, typing.Any] --  Keys has this:
            'services': services,
            'ip': request.ip,
            'nets': nets,
            'transports': valid_trans,
            'autorun': autorun

    """
    # We look for services for this authenticator groups. User is logged in in just 1 authenticator, so his groups must coincide with those assigned to ds
    groups = list(request.user.get_groups())
    available_service_pools = list(
        ServicePool.get_pools_for_groups(groups, request.user)
    )  # Pass in user to get "number_assigned" to optimize
    available_metapools = list(
        MetaPool.metapools_for_groups(groups, request.user)
    )  # Pass in user to get "number_assigned" to optimize
    now = sql_now()

    # Information for administrators
    nets = ''
    valid_transports = ''

    os_type: 'types.os.KnownOS' = request.os.os
    logger.debug('OS: %s', os_type)

    def _is_valid_transport(t: Transport) -> bool:
        transport_type = t.get_type()
        return (
            bool(transport_type)
            and t.is_ip_allowed(request.ip)
            and transport_type.supports_os(os_type)
            and t.is_os_allowed(os_type)
        )

    # Metapool helpers
    def _valid_transports(member: 'MetaPoolMember') -> collections.abc.Iterable[Transport]:
        t: Transport
        for t in member.pool.transports.all().order_by('priority'):
            try:
                if _is_valid_transport(t):
                    yield t
            except Exception as e:
                logger.warning('Transport %s of %s not found. Ignoring. (%s)', t, member.pool, e)

    def _build_transports_for_meta(
        transports: collections.abc.Iterable[Transport], is_by_label: bool, meta: 'MetaPool'
    ) -> list[collections.abc.Mapping[str, typing.Any]]:
        def idd(i: 'Transport') -> str:
            return i.uuid if not is_by_label else 'LABEL:' + i.label

        return [
            {
                'id': idd(i),
                'name': i.name,
                'link': html.uds_access_link(request, 'M' + meta.uuid, idd(i)),
                'priority': i.priority,
            }
            for i in sorted(transports, key=lambda x: x.priority)  # Sorted by priority
        ]

    if request.user.is_staff():
        nets = ','.join([n.name for n in Network.get_networks_for_ip(request.ip)])
        valid_transports = ','.join(
            t.name for t in Transport.objects.all().prefetch_related('networks') if t.is_ip_allowed(request.ip)
        )

    logger.debug('Checking meta pools: %s', available_metapools)
    services: list[collections.abc.Mapping[str, typing.Any]] = []

    # Preload all assigned user services for this user
    # Add meta pools data first
    for meta in available_metapools:
        # Check that we have access to at least one transport on some of its children
        transports_in_meta: list[collections.abc.Mapping[str, typing.Any]] = []
        in_use: bool = typing.cast(typing.Any, meta).number_in_use > 0  # Anotated value
        custom_message: typing.Optional[str] = None

        # Fist member of the pool that has a custom message, and is enabled, will be used
        # Ordered by priority, using internal sort, to take advantage of prefetched data
        sorted_members = sorted(meta.members.filter(enabled=True), key=lambda x: x.priority)

        # Get first member with custom message visible and enabled for metapools
        for member in sorted_members:
            if member.pool.display_custom_message and member.pool.visible and member.pool.custom_message.strip():
                custom_message = member.pool.custom_message
                break

        # Calculate info variable macros content if needed
        info_vars = (
            types.pools.UsageInfoVars(meta.usage())
            if (
                types.pools.UsageInfoVars.has_macros(meta.name)
                or types.pools.UsageInfoVars.has_macros(meta.visual_name)
            )
            else types.pools.UsageInfoVars()
        )

        if meta.transport_grouping == types.pools.TransportSelectionPolicy.COMMON:
            # Keep only transports that are in all pools
            # This will be done by getting all transports from all pools and then intersecting them
            # using reduce
            reducer: collections.abc.Callable[[set[Transport], set[Transport]], set[Transport]] = (
                lambda x, y: x & y
            )
            transports_in_all_pools = reduce(
                reducer,
                [{t for t in _valid_transports(member)} for member in sorted_members],
            )
            transports_in_meta = _build_transports_for_meta(
                transports_in_all_pools,
                is_by_label=False,
                meta=meta,
            )
        elif meta.transport_grouping == types.pools.TransportSelectionPolicy.LABEL:
            ltrans: collections.abc.MutableMapping[str, Transport] = {}
            transports_in_all_pools_by_label: typing.Optional[typing.Set[str]] = None
            temporary_transport_set_by_label: typing.Set[str]

            for member in sorted_members:
                temporary_transport_set_by_label = set()
                # if first pool, get all its transports and check that are valid
                for t in _valid_transports(member):
                    if not t.label:
                        continue
                    if t.label not in ltrans or ltrans[t.label].priority > t.priority:
                        ltrans[t.label] = t
                    if transports_in_all_pools_by_label is None:
                        temporary_transport_set_by_label.add(t.label)
                    elif t.label in transports_in_all_pools_by_label:  # For subsequent, reduce...
                        temporary_transport_set_by_label.add(t.label)

                transports_in_all_pools_by_label = temporary_transport_set_by_label
            # tmpSet has ALL common transports
            transports_in_meta = _build_transports_for_meta(
                (v for k, v in ltrans.items() if k in (transports_in_all_pools_by_label or set())),
                is_by_label=True,
                meta=meta,
            )
        else:
            # If we have at least one valid transport,
            # mark as "meta" transport and add it to the list
            transports_in_meta = [
                (
                    {
                        'id': 'meta',
                        'name': 'meta',
                        'link': html.uds_access_link(request, 'M' + meta.uuid, None),
                        'priority': 0,
                    }
                    if any(_valid_transports(member) for member in meta.members.filter(enabled=True))
                    else {}
                )
            ]

        # If no usable pools, this is not visible
        if transports_in_meta:
            group: collections.abc.MutableMapping[str, typing.Any] = (
                meta.servicesPoolGroup.as_dict if meta.servicesPoolGroup else ServicePoolGroup.default().as_dict
            )

            services.append(
                _service_info(
                    uuid=meta.uuid,
                    is_meta=True,
                    name=info_vars.replace(meta.name),
                    visual_name=info_vars.replace(meta.visual_name),
                    description=meta.comments,
                    group=group,
                    transports=transports_in_meta,
                    image=meta.image,
                    show_transports=len(transports_in_meta) > 1,
                    allow_users_remove=meta.allow_users_remove,
                    allow_users_reset=meta.allow_users_remove,
                    maintenance=meta.is_in_maintenance(),
                    not_accesible=not meta.is_access_allowed(now),
                    in_use=in_use,
                    to_be_replaced=None,
                    to_be_replaced_text='',
                    custom_calendar_text=meta.calendar_message,
                    custom_message_text=custom_message,
                )
            )

    # Now generic user service
    for service_pool in available_service_pools:
        # Skip pools that are part of meta pools
        if service_pool.owned_by_meta:
            continue

        # If no macro on names, skip calculation
        if '{' in service_pool.name or '{' in service_pool.visual_name:
            pool_usage_info = service_pool.usage(
                typing.cast(typing.Any, service_pool).usage_count,  # anotated value
            )
            use_percent = str(pool_usage_info.percent) + '%'
            use_count = str(pool_usage_info.used)
            left_count = str(pool_usage_info.total - pool_usage_info.used)
            max_srvs = str(pool_usage_info.total)
        else:
            max_srvs = ''
            use_percent = ''
            use_count = ''
            left_count = ''

        # pylint: disable=cell-var-from-loop
        def _replace_macro_vars(x: str) -> str:
            return (
                x.replace('{use}', use_percent)
                .replace('{total}', max_srvs)
                .replace('{usec}', use_count)
                .replace('{left}', left_count)
            )

        trans: list[collections.abc.Mapping[str, typing.Any]] = []
        for t in sorted(
            service_pool.transports.all(), key=lambda x: x.priority
        ):  # In memory sort, allows reuse prefetched and not too big array
            transport_type = t.get_type()
            if _is_valid_transport(t):
                if transport_type.own_link:
                    link = reverse('webapi.transport_own_link', args=('F' + service_pool.uuid, t.uuid))
                else:
                    link = html.uds_access_link(request, 'F' + service_pool.uuid, t.uuid)
                trans.append({'id': t.uuid, 'name': t.name, 'link': link, 'priority': t.priority})

        # If empty transports, do not include it on list
        if not trans:
            continue

        # Locate if user service has any already assigned user service for this. Use "pre cached" number of assignations in this pool to optimize
        in_use = typing.cast(typing.Any, service_pool).number_in_use > 0  # number_in_use is anotated value

        group = (
            service_pool.servicesPoolGroup.as_dict
            if service_pool.servicesPoolGroup
            else ServicePoolGroup.default().as_dict
        )

        # Only add toBeReplaced info in case we allow it. This will generate some "overload" on the services
        when_will_be_replaced = (
            service_pool.when_will_be_replaced(request.user)
            if typing.cast(typing.Any, service_pool).pubs_active > 0
            and GlobalConfig.NOTIFY_REMOVAL_BY_PUB.as_bool(False)
            else None
        )
        # tbr = False
        if when_will_be_replaced:
            replace_date_as_str = formats.date_format(when_will_be_replaced, 'SHORT_DATETIME_FORMAT')
            replace_date_info_text = gettext(
                'This service is about to be replaced by a new version. Please, close the session before {} and save all your work to avoid loosing it.'
            ).format(when_will_be_replaced)
        else:
            replace_date_as_str = None
            replace_date_info_text = ''

        services.append(
            _service_info(
                uuid=service_pool.uuid,
                is_meta=False,
                name=_replace_macro_vars(service_pool.name),
                visual_name=_replace_macro_vars(service_pool.visual_name),
                description=service_pool.comments,
                group=group,
                transports=trans,
                image=service_pool.image,
                show_transports=service_pool.show_transports,
                allow_users_remove=service_pool.allow_users_remove,
                allow_users_reset=service_pool.allow_users_reset,
                maintenance=service_pool.is_in_maintenance(),
                not_accesible=not service_pool.is_access_allowed(now),
                in_use=in_use,
                to_be_replaced=replace_date_as_str,
                to_be_replaced_text=replace_date_info_text,
                custom_calendar_text=service_pool.calendar_message,
                # Only add custom message if it's enabled and has a message
                custom_message_text=service_pool.custom_message if service_pool.display_custom_message and service_pool.custom_message.strip() else None,
            )
        )

    # logger.debug('Services: %s', services)

    # Sort services and remove services with no transports...
    services = [s for s in sorted(services, key=lambda s: s['name'].upper()) if s['transports']]

    autorun = False
    if (
        hasattr(request, 'session')
        and len(services) == 1
        and GlobalConfig.AUTORUN_SERVICE.as_bool(False)
        and services[0]['transports']
    ):
        if request.session.get('autorunDone', '0') == '0':
            request.session['autorunDone'] = '1'
            autorun = True

    return {
        'services': services,
        'ip': request.ip,
        'nets': nets,
        'transports': valid_transports,
        'autorun': autorun,
    }


def enable_service(
    request: 'ExtendedHttpRequestWithUser', service_id: str, transport_id: str
) -> collections.abc.Mapping[str, typing.Any]:
    # Maybe we could even protect this even more by limiting referer to own server /? (just a meditation..)
    logger.debug('idService: %s, idTransport: %s', service_id, transport_id)
    url = ''
    error = gettext('Service not ready. Please, try again in a while.')

    # If meta service, process and rebuild idService & idTransport

    try:
        info = UserServiceManager.manager().get_user_service_info(
            request.user, request.os, request.ip, service_id, transport_id, test_userservice_status=False
        )
        scrambler = CryptoManager().random_string(32)
        password = CryptoManager().symmetric_encrypt(web_password(request), scrambler)

        info.userservice.properties['accessed_by_client'] = False  # Reset accesed property to

        transport_type = info.transport.get_type()

        error = ''  # No error

        if transport_type.own_link:
            url = reverse('webapi.transport_own_link', args=('A' + info.userservice.uuid, info.transport.uuid))
        else:
            data = {
                'service': 'A' + info.userservice.uuid,
                'transport': info.transport.uuid,
                'user': request.user.uuid,
                'password': password,
            }

            ticket = TicketStore.create(data)
            url = html.uds_link(request, ticket, scrambler)
    except ServiceNotReadyError as e:
        logger.debug('Service not ready')
        # Not ready, show message and return to this page in a while
        # error += ' (code {0:04X})'.format(e.code)
        error = (
            gettext('Your service is being created, please, wait for a few seconds while we complete it.)')
            + f'({e.code.as_percent()}%)'
        )
    except MaxServicesReachedError:
        logger.info('Number of service reached MAX for service pool "%s"', service_id)
        error = types.errors.Error.MAX_SERVICES_REACHED.message
    except ServiceAccessDeniedByCalendar:
        logger.info('Access tried to a calendar limited access pool "%s"', service_id)
        error = types.errors.Error.SERVICE_CALENDAR_DENIED.message
    except Exception as e:
        logger.exception('Error')
        error = str(e)

    return {'url': str(url), 'error': str(error)}
