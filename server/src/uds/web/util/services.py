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

from django.utils.translation import ugettext
from django.utils import formats
from django.urls import reverse

from uds.models import (
    ServicePool,
    Transport,
    Network,
    ServicePoolGroup,
    MetaPool,
    TicketStore,
    getSqlDatetime,
)
from uds.core.util.config import GlobalConfig
from uds.core.util import html
from uds.core.managers import cryptoManager, userServiceManager
from uds.core.services.exceptions import (
    ServiceNotReadyError,
    MaxServicesReachedError,
    ServiceAccessDeniedByCalendar,
)

from uds.web.util import errors
from uds.core.auths.auth import webPassword

# Not imported at runtime, just for type checking
if typing.TYPE_CHECKING:
    from uds.core.util.request import ExtendedHttpRequestWithUser


logger = logging.getLogger(__name__)


def getServicesData(
    request: 'ExtendedHttpRequestWithUser',
) -> typing.Dict[
    str, typing.Any
]:  # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    """Obtains the service data dictionary will all available services for this request

    Arguments:
        request {ExtendedHttpRequest} -- request from where to xtract credentials

    Returns:
        typing.Dict[str, typing.Any] --  Keys has this:
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

    osType = request.os['OS']
    logger.debug('OS: %s', osType)

    if request.user.isStaff():
        nets = ','.join([n.name for n in Network.networksFor(request.ip)])
        tt = []
        t: Transport
        for t in Transport.objects.all().prefetch_related('networks'):
            if t.validForIp(request.ip):
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
                logger.warning(
                    'Transport %s of %s not found. Ignoring. (%s)', t, member.pool, e
                )

    def buildMetaTransports(
        transports: typing.Iterable[Transport],
        isLabel: bool,
    ) -> typing.List[typing.Mapping[str, typing.Any]]:
        idd = lambda i: i.uuid if not isLabel else 'LABEL:' + i.label
        return [
            {
                'id': idd(i),
                'name': i.name,
                'link': html.udsAccessLink(request, 'M' + meta.uuid, idd(i)),
                'priority': i.priority,
            }
            for i in transports
        ]

    # Preload all assigned user services for this user
    # Add meta pools data first
    for meta in availMetaPools:
        # Check that we have access to at least one transport on some of its children
        metaTransports: typing.List[typing.Mapping[str, typing.Any]] = []
        in_use = meta.number_in_use > 0  # type: ignore # anotated value

        inAll: typing.Optional[typing.Set[str]] = None
        tmpSet: typing.Set[str]
        if (
            meta.transport_grouping == MetaPool.COMMON_TRANSPORT_SELECT
        ):  # If meta.use_common_transports
            # only keep transports that are in ALL members
            for member in meta.members.all().order_by('priority'):
                tmpSet = set()
                # if first pool, get all its transports and check that are valid
                for t in transportIterator(member):
                    if inAll is None:
                        tmpSet.add(t.uuid)
                    elif t.uuid in inAll:  # For subsequent, reduce...
                        tmpSet.add(t.uuid)

                inAll = tmpSet
            # tmpSet has ALL common transports
            metaTransports = buildMetaTransports(
                Transport.objects.filter(uuid__in=inAll or []), isLabel=False
            )
        elif meta.transport_grouping == MetaPool.LABEL_TRANSPORT_SELECT:
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
                (v for k, v in ltrans.items() if k in (inAll or set())), isLabel=True
            )
        else:
            for member in meta.members.all():
                # if pool.isInMaintenance():
                #    continue
                for t in member.pool.transports.all():
                    typeTrans = t.getType()
                    if (
                        typeTrans
                        and t.validForIp(request.ip)
                        and typeTrans.supportsOs(osType)
                        and t.validForOs(osType)
                    ):
                        metaTransports = [
                            {
                                'id': 'meta',
                                'name': 'meta',
                                'link': html.udsAccessLink(
                                    request, 'M' + meta.uuid, None
                                ),
                                'priority': 0,
                            }
                        ]
                        break

                # if not in_use and meta.number_in_use:  # Only look for assignation on possible used
                #     assignedUserService = userServiceManager().getExistingAssignationForUser(pool, request.user)
                #     if assignedUserService:
                #         in_use = assignedUserService.in_use

                # Stop when 1 usable pool is found (metaTransports is filled)
                if metaTransports:
                    break

        # If no usable pools, this is not visible
        if metaTransports:
            group: typing.MutableMapping[str, typing.Any] = (
                meta.servicesPoolGroup.as_dict
                if meta.servicesPoolGroup
                else ServicePoolGroup.default().as_dict
            )

            services.append(
                {
                    'id': 'M' + meta.uuid,
                    'is_meta': True,
                    'name': meta.name,
                    'visual_name': meta.visual_name,
                    'description': meta.comments,
                    'group': group,
                    'transports': metaTransports,
                    'imageId': meta.image and meta.image.uuid or 'x',
                    'show_transports': len(metaTransports) > 1,
                    'allow_users_remove': False,
                    'allow_users_reset': False,
                    'maintenance': meta.isInMaintenance(),
                    'not_accesible': not meta.isAccessAllowed(now),
                    'in_use': in_use,
                    'to_be_replaced': None,
                    'to_be_replaced_text': '',
                    'custom_calendar_text': meta.calendar_message,
                }
            )

    # Now generic user service
    for sPool in availServicePools:
        # Skip pools that are part of meta pools
        if sPool.owned_by_meta:
            continue

        use_percent = str(sPool.usage(sPool.usage_count)) + '%'  # type: ignore # anotated value
        use_count = str(sPool.usage_count)  # type: ignore # anotated value
        left_count = str(sPool.max_srvs - sPool.usage_count)  # type: ignore # anotated value

        trans: typing.List[typing.MutableMapping[str, typing.Any]] = []
        for t in sorted(
            sPool.transports.all(), key=lambda x: x.priority
        ):  # In memory sort, allows reuse prefetched and not too big array
            typeTrans = t.getType()
            if (
                typeTrans
                and t.validForIp(request.ip)
                and typeTrans.supportsOs(osType)
                and t.validForOs(osType)
            ):
                if typeTrans.ownLink:
                    link = reverse('TransportOwnLink', args=('F' + sPool.uuid, t.uuid))
                else:
                    link = html.udsAccessLink(request, 'F' + sPool.uuid, t.uuid)
                trans.append(
                    {'id': t.uuid, 'name': t.name, 'link': link, 'priority': t.priority}
                )

        # If empty transports, do not include it on list
        if not trans:
            continue

        if sPool.image:
            imageId = sPool.image.uuid
        else:
            imageId = 'x'

        # Locate if user service has any already assigned user service for this. Use "pre cached" number of assignations in this pool to optimize
        in_use = typing.cast(typing.Any, sPool).number_in_use > 0
        # if svr.number_in_use:  # Anotated value got from getDeployedServicesForGroups(...). If 0, no assignation for this user
        #     ads = userServiceManager().getExistingAssignationForUser(svr, request.user)
        #     if ads:
        #         in_use = ads.in_use

        group = (
            sPool.servicesPoolGroup.as_dict
            if sPool.servicesPoolGroup
            else ServicePoolGroup.default().as_dict
        )

        # Only add toBeReplaced info in case we allow it. This will generate some "overload" on the services
        toBeReplaced = (
            sPool.toBeReplaced(request.user)
            if typing.cast(typing.Any, sPool).pubs_active > 0
            and GlobalConfig.NOTIFY_REMOVAL_BY_PUB.getBool(False)
            else None
        )
        # tbr = False
        if toBeReplaced:
            toBeReplaced = formats.date_format(toBeReplaced, 'SHORT_DATETIME_FORMAT')
            toBeReplacedTxt = ugettext(
                'This service is about to be replaced by a new version. Please, close the session before {} and save all your work to avoid loosing it.'
            ).format(toBeReplaced)
        else:
            toBeReplacedTxt = ''

        # Calculate max deployed
        maxDeployed = str(sPool.max_srvs)
        # if sPool.service.getType().usesCache is False:
        #    maxDeployed = sPool.service.getInstance().maxDeployed

        def datator(x) -> str:
            return (
                x.replace('{use}', use_percent)
                .replace('{total}', str(sPool.max_srvs))
                .replace('{usec}', use_count)
                .replace('{left}', left_count)
            )

        services.append(
            {
                'id': 'F' + sPool.uuid,
                'is_meta': False,
                'name': datator(sPool.name),
                'visual_name': datator(
                    sPool.visual_name.replace('{use}', use_percent).replace(
                        '{total}', maxDeployed
                    )
                ),
                'description': sPool.comments,
                'group': group,
                'transports': trans,
                'imageId': imageId,
                'show_transports': sPool.show_transports,
                'allow_users_remove': sPool.allow_users_remove,
                'allow_users_reset': sPool.allow_users_reset,
                'maintenance': sPool.isInMaintenance(),
                'not_accesible': not sPool.isAccessAllowed(now),
                'in_use': in_use,
                'to_be_replaced': toBeReplaced,
                'to_be_replaced_text': toBeReplacedTxt,
                'custom_calendar_text': sPool.calendar_message,
            }
        )

    # logger.debug('Services: %s', services)

    # Sort services and remove services with no transports...
    services = [
        s for s in sorted(services, key=lambda s: s['name'].upper()) if s['transports']
    ]

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
    error = ugettext('Service not ready. Please, try again in a while.')

    # If meta service, process and rebuild idService & idTransport

    try:
        res = userServiceManager().getService(
            request.user, request.os, request.ip, idService, idTransport, doTest=False
        )
        scrambler = cryptoManager().randomString(32)
        password = cryptoManager().symCrypt(webPassword(request), scrambler)

        userService, trans = res[1], res[3]

        userService.setProperty('accessedByClient', '0')  # Reset accesed property to

        typeTrans = trans.getType()
        if not typeTrans:
            raise Exception('Transport not found')

        error = ''  # No error

        if typeTrans.ownLink:
            url = reverse('TransportOwnLink', args=('A' + userService.uuid, trans.uuid))
        else:
            data = {
                'service': 'A' + userService.uuid,
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
        error = ugettext(
            'Your service is being created, please, wait for a few seconds while we complete it.)'
        ) + '({}%)'.format(int(e.code * 25))
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
