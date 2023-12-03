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
@author: Adolfo Gómez, dkmaster at dkmon dot com
'''
import logging
import typing
import collections.abc

from django.urls import reverse
from django.utils import formats
from django.utils.translation import gettext

from uds.core import types
from uds.core.auths.auth import webPassword
from uds.core.managers.crypto import CryptoManager
from uds.core.managers.user_service import UserServiceManager
from uds.core.services.exceptions import (
    MaxServicesReachedError,
    ServiceAccessDeniedByCalendar,
    ServiceNotReadyError,
)
from uds.core.util import html
from uds.core.util.config import GlobalConfig
from uds.core.util.model import getSqlDatetime
from uds.models import MetaPool, Network, ServicePool, ServicePoolGroup, TicketStore, Transport
from uds.web.util import errors

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.types.request import ExtendedHttpRequestWithUser
    from uds.models import Image


logger = logging.getLogger(__name__)


# pylint: disable=too-many-arguments
def _serviceInfo(
    uuid: str,
    is_meta: bool,
    name: str,
    visual_name: str,
    description: str,
    group: typing.Mapping[str, typing.Any],
    transports: list[typing.Mapping[str, typing.Any]],
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
):
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
    }


# pylint: disable=too-many-locals, too-many-branches, too-many-statements
def getServicesData(
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
            'transports': validTrans,
            'autorun': autorun

    """
    # We look for services for this authenticator groups. User is logged in in just 1 authenticator, so his groups must coincide with those assigned to ds
    groups = list(request.user.getGroups())
    availServicePools = list(
        ServicePool.getDeployedServicesForGroups(groups, request.user)
    )  # Pass in user to get "number_assigned" to optimize
    availMetaPools = list(
        MetaPool.getForGroups(groups, request.user)
    )  # Pass in user to get "number_assigned" to optimize
    now = getSqlDatetime()

    # Information for administrators
    nets = ''
    validTrans = ''

    osType: 'types.os.KnownOS' = request.os.os
    logger.debug('OS: %s', osType)

    if request.user.isStaff():
        nets = ','.join([n.name for n in Network.networksFor(request.ip)])
        tt = []
        t: Transport
        for t in Transport.objects.all().prefetch_related('networks'):
            if t.isValidForIp(request.ip):
                tt.append(t.name)
        validTrans = ','.join(tt)

    logger.debug('Checking meta pools: %s', availMetaPools)
    services = []

    # Metapool helpers
    def transportIterator(member) -> typing.Iterable[Transport]:
        for t in member.pool.transports.all().order_by('priority'):
            try:
                typeTrans = t.getType()
                if (
                    typeTrans
                    and t.validForIp(request.ip)
                    and typeTrans.supportsOs(osType)
                    and t.validForOs(osType)
                ):
                    yield t
            except Exception as e:
                logger.warning('Transport %s of %s not found. Ignoring. (%s)', t, member.pool, e)

    def buildMetaTransports(
        transports: typing.Iterable[Transport], isLabel: bool, meta: 'MetaPool'
    ) -> list[typing.Mapping[str, typing.Any]]:
        def idd(i):
            return i.uuid if not isLabel else 'LABEL:' + i.label

        return [
            {
                'id': idd(i),
                'name': i.name,
                'link': html.udsAccessLink(request, 'M' + meta.uuid, idd(i)),  # type: ignore
                'priority': i.priority,
            }
            for i in transports
        ]

    # Preload all assigned user services for this user
    # Add meta pools data first
    for meta in availMetaPools:
        # Check that we have access to at least one transport on some of its children
        metaTransports: list[typing.Mapping[str, typing.Any]] = []
        in_use = meta.number_in_use > 0  # type: ignore # anotated value

        inAll: typing.Optional[typing.Set[str]] = None
        tmpSet: typing.Set[str]

        # If no macro on names, skip calculation (and set to empty)
        if '{' in meta.name or '{' in meta.visual_name:
            poolUsageInfo = meta.usage()
            use_percent = str(poolUsageInfo.percent) + '%'
            use_count = str(poolUsageInfo.used)
            left_count = str(poolUsageInfo.total - poolUsageInfo.used)
            max_srvs = str(poolUsageInfo.total)
        else:
            max_srvs = ''
            use_percent = ''
            use_count = ''
            left_count = ''

        # pylint: disable=cell-var-from-loop
        def macro_info(x: str) -> str:
            return (
                x.replace('{use}', use_percent)
                .replace('{total}', max_srvs)
                .replace('{usec}', use_count)
                .replace('{left}', left_count)
            )

        if meta.transport_grouping == types.pools.TransportSelectionPolicy.COMMON:
            # only keep transports that are in ALL members
            for member in meta.members.all().order_by('priority'):
                tmpSet = set()
                # if first pool, get all its transports and check that are valid
                for t in transportIterator(member):
                    if inAll is None:
                        tmpSet.add(t.uuid)  # type: ignore
                    elif t.uuid in inAll:  # For subsequent, reduce...
                        tmpSet.add(t.uuid)  # type: ignore

                inAll = tmpSet
            # tmpSet has ALL common transports
            metaTransports = buildMetaTransports(
                Transport.objects.filter(uuid__in=inAll or []), isLabel=False, meta=meta
            )
        elif meta.transport_grouping == types.pools.TransportSelectionPolicy.LABEL:
            ltrans: typing.MutableMapping[str, Transport] = {}
            for member in meta.members.all().order_by('priority'):
                tmpSet = set()
                # if first pool, get all its transports and check that are valid
                for t in transportIterator(member):
                    if not t.label:
                        continue
                    if t.label not in ltrans or ltrans[t.label].priority > t.priority:
                        ltrans[t.label] = t
                    if inAll is None:
                        tmpSet.add(t.label)
                    elif t.label in inAll:  # For subsequent, reduce...
                        tmpSet.add(t.label)

                inAll = tmpSet
            # tmpSet has ALL common transports
            metaTransports = buildMetaTransports(
                (v for k, v in ltrans.items() if k in (inAll or set())), isLabel=True, meta=meta
            )
        else:
            for member in meta.members.all():
                # if pool.isInMaintenance():
                #    continue
                for t in member.pool.transports.all():
                    typeTrans = t.getType()
                    if (
                        typeTrans
                        and t.isValidForIp(request.ip)
                        and typeTrans.supportsOs(osType)
                        and t.isValidForOs(osType)
                    ):
                        metaTransports = [
                            {
                                'id': 'meta',
                                'name': 'meta',
                                'link': html.udsAccessLink(request, 'M' + meta.uuid, None),  # type: ignore
                                'priority': 0,
                            }
                        ]
                        break

                # if not in_use and meta.number_in_use:  # Only look for assignation on possible used
                #     assignedUserService = UserServiceManager().getExistingAssignationForUser(pool, request.user)
                #     if assignedUserService:
                #         in_use = assignedUserService.in_use

                # Stop when 1 usable pool is found (metaTransports is filled)
                if metaTransports:
                    break

        # If no usable pools, this is not visible
        if metaTransports:
            group: typing.MutableMapping[str, typing.Any] = (
                meta.servicesPoolGroup.as_dict if meta.servicesPoolGroup else ServicePoolGroup.default().as_dict
            )

            services.append(
                _serviceInfo(
                    uuid=meta.uuid,
                    is_meta=True,
                    name=macro_info(meta.name),
                    visual_name=macro_info(meta.visual_name),
                    description=meta.comments,
                    group=group,
                    transports=metaTransports,
                    image=meta.image,
                    show_transports=len(metaTransports) > 1,
                    allow_users_remove=meta.allow_users_remove,
                    allow_users_reset=meta.allow_users_remove,
                    maintenance=meta.isInMaintenance(),
                    not_accesible=not meta.isAccessAllowed(now),
                    in_use=in_use,
                    to_be_replaced=None,
                    to_be_replaced_text='',
                    custom_calendar_text=meta.calendar_message,
                )
            )

    # Now generic user service
    for sPool in availServicePools:
        # Skip pools that are part of meta pools
        if sPool.owned_by_meta:
            continue

        # If no macro on names, skip calculation
        if '{' in sPool.name or '{' in sPool.visual_name:
            poolUsageInfo = sPool.usage(
                sPool.usage_count,  # type: ignore # anotated value
            )
            use_percent = str(poolUsageInfo.percent) + '%'
            use_count = str(poolUsageInfo.used)
            left_count = str(poolUsageInfo.total - poolUsageInfo.used)
            max_srvs = str(poolUsageInfo.total)
        else:
            max_srvs = ''
            use_percent = ''
            use_count = ''
            left_count = ''

        # pylint: disable=cell-var-from-loop
        def macro_info(x: str) -> str:
            return (
                x.replace('{use}', use_percent)
                .replace('{total}', max_srvs)
                .replace('{usec}', use_count)
                .replace('{left}', left_count)
            )

        trans: list[typing.Mapping[str, typing.Any]] = []
        for t in sorted(
            sPool.transports.all(), key=lambda x: x.priority
        ):  # In memory sort, allows reuse prefetched and not too big array
            typeTrans = t.getType()
            if (
                typeTrans
                and t.isValidForIp(request.ip)
                and typeTrans.supportsOs(osType)
                and t.isValidForOs(osType)
            ):
                if typeTrans.ownLink:
                    link = reverse('TransportOwnLink', args=('F' + sPool.uuid, t.uuid))  # type: ignore
                else:
                    link = html.udsAccessLink(request, 'F' + sPool.uuid, t.uuid)  # type: ignore
                trans.append({'id': t.uuid, 'name': t.name, 'link': link, 'priority': t.priority})

        # If empty transports, do not include it on list
        if not trans:
            continue

        # Locate if user service has any already assigned user service for this. Use "pre cached" number of assignations in this pool to optimize
        in_use = typing.cast(typing.Any, sPool).number_in_use > 0
        # if svr.number_in_use:  # Anotated value got from getDeployedServicesForGroups(...). If 0, no assignation for this user
        #     ads = UserServiceManager().getExistingAssignationForUser(svr, request.user)
        #     if ads:
        #         in_use = ads.in_use

        group = (
            sPool.servicesPoolGroup.as_dict if sPool.servicesPoolGroup else ServicePoolGroup.default().as_dict
        )

        # Only add toBeReplaced info in case we allow it. This will generate some "overload" on the services
        toBeReplacedDate = (
            sPool.toBeReplaced(request.user)
            if typing.cast(typing.Any, sPool).pubs_active > 0
            and GlobalConfig.NOTIFY_REMOVAL_BY_PUB.getBool(False)
            else None
        )
        # tbr = False
        if toBeReplacedDate:
            toBeReplaced = formats.date_format(toBeReplacedDate, 'SHORT_DATETIME_FORMAT')
            toBeReplacedTxt = gettext(
                'This service is about to be replaced by a new version. Please, close the session before {} and save all your work to avoid loosing it.'
            ).format(toBeReplacedDate)
        else:
            toBeReplaced = None
            toBeReplacedTxt = ''

        services.append(
            _serviceInfo(
                uuid=sPool.uuid,
                is_meta=False,
                name=macro_info(sPool.name),
                visual_name=macro_info(sPool.visual_name),
                description=sPool.comments,
                group=group,
                transports=trans,
                image=sPool.image,
                show_transports=sPool.show_transports,
                allow_users_remove=sPool.allow_users_remove,
                allow_users_reset=sPool.allow_users_reset,
                maintenance=sPool.isInMaintenance(),
                not_accesible=not sPool.isAccessAllowed(now),
                in_use=in_use,
                to_be_replaced=toBeReplaced,
                to_be_replaced_text=toBeReplacedTxt,
                custom_calendar_text=sPool.calendar_message,
            )
        )

    # logger.debug('Services: %s', services)

    # Sort services and remove services with no transports...
    services = [s for s in sorted(services, key=lambda s: s['name'].upper()) if s['transports']]

    autorun = False
    if (
        hasattr(request, 'session')
        and len(services) == 1
        and GlobalConfig.AUTORUN_SERVICE.getBool(False)
        and services[0]['transports']
    ):
        if request.session.get('autorunDone', '0') == '0':
            request.session['autorunDone'] = '1'
            autorun = True

    return {
        'services': services,
        'ip': request.ip,
        'nets': nets,
        'transports': validTrans,
        'autorun': autorun,
    }


def enableService(
    request: 'ExtendedHttpRequestWithUser', idService: str, idTransport: str
) -> typing.Mapping[str, typing.Any]:
    # Maybe we could even protect this even more by limiting referer to own server /? (just a meditation..)
    logger.debug('idService: %s, idTransport: %s', idService, idTransport)
    url = ''
    error = gettext('Service not ready. Please, try again in a while.')

    # If meta service, process and rebuild idService & idTransport

    try:
        res = UserServiceManager().getService(
            request.user, request.os, request.ip, idService, idTransport, doTest=False
        )
        scrambler = CryptoManager().randomString(32)
        password = CryptoManager().symCrypt(webPassword(request), scrambler)

        userService, trans = res[1], res[3]

        userService.properties['accessed_by_client'] = False  # Reset accesed property to

        typeTrans = trans.getType()

        error = ''  # No error

        if typeTrans.ownLink:
            url = reverse('TransportOwnLink', args=('A' + userService.uuid, trans.uuid))  # type: ignore
        else:
            data = {
                'service': 'A' + userService.uuid,  # type: ignore
                'transport': trans.uuid,
                'user': request.user.uuid,
                'password': password,
            }

            ticket = TicketStore.create(data)
            url = html.udsLink(request, ticket, scrambler)
    except ServiceNotReadyError as e:
        logger.debug('Service not ready')
        # Not ready, show message and return to this page in a while
        # error += ' (code {0:04X})'.format(e.code)
        error = (
            gettext('Your service is being created, please, wait for a few seconds while we complete it.)')
            + f'({e.code*25}%)'
        )
    except MaxServicesReachedError:
        logger.info('Number of service reached MAX for service pool "%s"', idService)
        error = errors.errorString(errors.MAX_SERVICES_REACHED)
    except ServiceAccessDeniedByCalendar:
        logger.info('Access tried to a calendar limited access pool "%s"', idService)
        error = errors.errorString(errors.SERVICE_CALENDAR_DENIED)
    except Exception as e:
        logger.exception('Error')
        error = str(e)

    return {'url': str(url), 'error': str(error)}
